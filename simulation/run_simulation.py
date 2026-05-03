"""
Simulated Preference Learning Experiment (revamped to match the 3 final
experimental conditions, with checkpoint-based learning curves).

Two complementary outputs:
  1. End-of-experiment predicted DV — does the participant prefer the K-dim
     summary over the standard summary? (predicted_dv.png, summary.md)
  2. Learning curves — held-out test accuracy and log-likelihood as a
     function of how many trials have been collected (learning_curves.png,
     learning_curves.csv). Lets you verify the system actually learns from
     more data, and read off "trials-to-X% accuracy" for power calcs.

Three conditions × three fits, evaluated identically:
  Conditions:
    1. choice_only            — binary choice, no per-dim feedback.
    2. inference_affirm       — top-K=5 visible dims, Affirm/Moderate/Remove.
    3. inference_categories   — top-K=5 visible dims, 5-category picker.

  Fits (computed for every condition, so we can compare apples-to-apples):
    A. standard   — kernel logistic regression in full d-dim space (MLE).
    B. projected  — K-dim primal logistic regression on plain U
                    (MLE projected onto the interpretable basis; ignores
                    feedback). λ_partial regularization.
    C. partial    — K-dim primal logistic regression on Ũ = Λ ⊙ U with
                    β₀ = 0 (matches `index.html` web-experiment fit; the
                    feedback re-weights the design matrix per-trial
                    per-dimension). λ_partial regularization.

  For choice_only, Λ ≡ 1, so projected and partial are identical fits
  (we still compute both for plotting consistency).

Pipeline per simulated user × condition:
  1. Sample T trials (idx_a, idx_b); user chooses by their true K-vec w*.
  2. For inference conditions: pick top-5 dims by |V·φ_chosen|, compute the
     model's pre-selected category via per-dim quintile bucketing of the
     trial-pool projections, simulate the participant's per-dim feedback
     (with calibrated noise) → λ_t (K-vec, 1.0 for invisible dims).
  3. Refit at every checkpoint t ∈ checkpoints (default: every trial) using
     prefix data [0:t] for ALL THREE fits.
     Compute: held-out test accuracy + log-likelihood + summary quality
     (Spearman/sign-agreement vs. ground-truth w*) at each checkpoint.
  4. Final-T metrics roll up into predicted_dv.png + summary.md;
     all checkpoints × all fits roll into learning_curves.{csv,png}.
"""

import argparse
import json
import math
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr, wilcoxon


CONDITIONS = ["choice_only", "inference_affirm", "inference_categories"]
DEFAULT_MULTS = np.array([-1.5, -1.0, 0.0, 1.0, 1.5])


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_predefined_pairs(json_path, option_ids):
    """Load predefined pairs (e.g., dilemma pairs from predefined_pairs.json)
    and convert option_ids to embedding indices.
    """
    with open(json_path) as f:
        pairs_raw = json.load(f)
    id_to_idx = {oid: i for i, oid in enumerate(option_ids)}
    pairs = []
    dropped = 0
    for p in pairs_raw:
        a, b = str(p["option_a_id"]), str(p["option_b_id"])
        if a in id_to_idx and b in id_to_idx:
            pairs.append((id_to_idx[a], id_to_idx[b]))
        else:
            dropped += 1
    if dropped:
        print(f"  [predefined-pairs] dropped {dropped} pairs missing from pool")
    print(f"  [predefined-pairs] using {len(pairs)} pairs from {json_path}")
    return pairs


def load_data(embeddings_parquet, bt_scores_csv, directions_npz, option_id_column):
    parquet_df = pd.read_parquet(embeddings_parquet)
    parquet_df["option_id"] = parquet_df[option_id_column].astype(str)
    parquet_df = parquet_df.sort_values("option_id").reset_index(drop=True)
    option_ids = parquet_df["option_id"].tolist()
    embeddings = np.stack(parquet_df["embedding"].apply(np.array).values).astype(np.float64)

    bt_df = pd.read_csv(bt_scores_csv)
    bt_df["option_id"] = bt_df["option_id"].astype(str)
    dim_info = (bt_df[["dimension_id", "dimension_name"]]
                .drop_duplicates().sort_values("dimension_id"))
    dim_names = dim_info["dimension_name"].tolist()
    dim_ids = dim_info["dimension_id"].tolist()
    bt_pivot = bt_df.pivot(index="option_id", columns="dimension_id", values="bt_score")
    bt_pivot = bt_pivot[dim_ids].loc[option_ids]
    bt_scores = bt_pivot.values.astype(np.float64)

    npz = np.load(directions_npz)
    V_raw = npz["directions_raw"].astype(np.float64)
    mu = npz["mean_embedding"].astype(np.float64)
    norms = np.linalg.norm(V_raw, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    V = V_raw / norms

    G = V @ V.T

    print(f"  Gram matrix condition number: {np.linalg.cond(G):.1f}")
    print(f"  Max inter-dimension correlation: {np.abs(G - np.eye(G.shape[0])).max():.3f}")

    return embeddings, bt_scores, V, G, mu, option_ids, dim_names


# ---------------------------------------------------------------------------
# Synthetic users (domain-agnostic sparse weights)
# ---------------------------------------------------------------------------

def generate_users(num_users, K, rng, sparsity=0.5):
    """Sparse random users. Each gets ±0.7 to ±1.0 weights on a random
    subset of dimensions, 0 elsewhere — emulates a person who cares about
    a few specific qualities and is indifferent to the rest."""
    users = []
    n_active_target = max(2, int(round(sparsity * K)))
    for i in range(num_users):
        n_active = max(2, int(rng.normal(n_active_target, max(1, sparsity * K * 0.3))))
        n_active = min(n_active, K)
        active = rng.choice(K, size=n_active, replace=False)
        weights = np.zeros(K)
        magnitudes = rng.uniform(0.7, 1.0, size=n_active)
        signs = rng.choice([-1.0, 1.0], size=n_active)
        weights[active] = magnitudes * signs
        users.append({"id": i, "archetype": f"sparse_{n_active}", "weights": weights})
    return users


# ---------------------------------------------------------------------------
# Choice and bucketing
# ---------------------------------------------------------------------------

def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -50, 50)))


def user_chooses(u_a, u_b, beta, rng):
    return int(rng.random() < sigmoid(beta * (u_a - u_b)))


def perdim_quintile_boundaries(values_pool, n_cats=5):
    """For each column k, return n_cats-1 boundaries that split a symmetric
    {value, -value} version of values_pool[:,k] into n_cats equal-mass bins.

    Symmetrizing keeps the middle bucket centered on 0.
    """
    T, K = values_pool.shape
    n_bounds = n_cats - 1
    quantiles = np.linspace(0, 1, n_cats + 1)[1:-1]
    boundaries = np.zeros((n_bounds, K))
    for k in range(K):
        v = values_pool[:, k]
        symm = np.concatenate([v, -v])
        boundaries[:, k] = np.quantile(symm, quantiles)
    return boundaries


def value_to_mult(value, boundaries_k, mults):
    """Bucket a single value (one dim) into one of len(mults) multipliers."""
    bucket = np.searchsorted(boundaries_k, value)
    return float(mults[bucket])


def w_star_to_mult(w_star_k, w_star_max, mults):
    """Map a user's true weight on dim k onto the nearest multiplier.

    Normalize w_star[k] by max(|w_star|) so the user's strongest dim hits
    ±1.5 and indifferent dims (≈0) map to 0.
    """
    if w_star_max <= 0:
        return 0.0
    target = mults.max() * (w_star_k / w_star_max)
    return float(mults[np.argmin(np.abs(mults - target))])


# ---------------------------------------------------------------------------
# UI logic per condition
# ---------------------------------------------------------------------------

def moderated_mult(mult, mults):
    """Move one step toward 0 in the mults list. Indifferent stays at 0."""
    idx = int(np.argmin(np.abs(mults - mult)))
    center = int(np.argmin(np.abs(mults)))
    if idx == center:
        return float(mults[center])
    if idx < center:
        return float(mults[idx + 1])
    return float(mults[idx - 1])


def affirm_decision(pre_mult, true_mult, mults, affirm_bonus=1.5):
    """Simulate the participant's affirm/moderate/remove decision.

    Returns (action_label, applied_multiplier)."""
    eps = 1e-9
    if abs(pre_mult) < eps and abs(true_mult) < eps:
        return "affirm", 0.0  # both indifferent → trivially affirm
    if abs(pre_mult) < eps:
        # Model said indifferent; user disagrees. UI has no "strengthen
        # from zero" action — best they can do is leave it (affirm 0).
        return "affirm", 0.0
    if abs(true_mult) < eps:
        # Model gave non-zero; user is indifferent → remove zeros it out.
        return "remove", 0.0
    if (pre_mult > 0) != (true_mult > 0):
        return "remove", 0.0
    if abs(true_mult) >= abs(pre_mult):
        return "affirm", affirm_bonus * pre_mult
    return "moderate", moderated_mult(pre_mult, mults)


def categories_decision(true_mult, mults):
    """5-category picker: pick the bucket closest to user's true mult."""
    return float(mults[np.argmin(np.abs(mults - true_mult))])


def apply_noise(applied_mult, mults, noise, rng):
    """With probability `noise`, replace applied_mult with an adjacent
    bucket (forces participant slip). At noise=0, no change."""
    if noise <= 0 or rng.random() > noise:
        return applied_mult
    idx = int(np.argmin(np.abs(mults - applied_mult)))
    if idx == 0:
        new_idx = 1
    elif idx == len(mults) - 1:
        new_idx = idx - 1
    else:
        new_idx = idx + (1 if rng.random() < 0.5 else -1)
    return float(mults[new_idx])


# ---------------------------------------------------------------------------
# Batch fits (Newton + L2). Mirrors web-interface/test_eval_parity.py.
# ---------------------------------------------------------------------------

def fit_standard_kernel(D, y, lam, max_iter=15, tol=1e-7):
    """Kernel logistic regression in dual form. Returns alpha (T,)."""
    T = len(D)
    alpha = np.zeros(T)
    for _ in range(max_iter):
        u = D @ alpha
        p = sigmoid(u)
        w = p * (1 - p)
        rhs = -(p - y + lam * alpha)
        A = (w[:, None] * D) + lam * np.eye(T)
        try:
            d_alpha = np.linalg.solve(A, rhs)
        except np.linalg.LinAlgError:
            break
        alpha = alpha + d_alpha
        if np.max(np.abs(d_alpha)) < tol:
            break
    return alpha


def fit_partial_primal(U, y, G, beta0, lam, max_iter=15, tol=1e-7):
    """K-dim primal logistic regression with G-shape prior centered at β₀."""
    T, K = U.shape
    beta = beta0.copy()
    for _ in range(max_iter):
        u = U @ beta
        p = sigmoid(u)
        w = p * (1 - p)
        grad = U.T @ (p - y) + lam * G @ (beta - beta0)
        H = U.T @ (w[:, None] * U) + lam * G
        try:
            d_beta = np.linalg.solve(H, -grad)
        except np.linalg.LinAlgError:
            break
        beta = beta + d_beta
        if np.max(np.abs(d_beta)) < tol:
            break
    return beta


# ---------------------------------------------------------------------------
# Held-out evaluation helpers
# ---------------------------------------------------------------------------

def heldout_log_likelihood(logits, choices):
    """Mean Bernoulli LL over held-out test pairs."""
    p = sigmoid(logits)
    eps = 1e-10
    return float(np.mean(choices * np.log(p + eps)
                         + (1 - choices) * np.log(1 - p + eps)))


def make_checkpoints(num_trials, step):
    """Trial counts at which to refit. step<=0 → only num_trials.
    step=1 → every trial. step>1 → multiples of step, plus 1 and num_trials."""
    if step <= 0:
        return [num_trials]
    pts = list(range(step, num_trials + 1, step))
    if 1 not in pts:
        pts = [1] + pts
    if pts[-1] != num_trials:
        pts.append(num_trials)
    return sorted(set(pts))


# ---------------------------------------------------------------------------
# Summary quality
# ---------------------------------------------------------------------------

def summary_quality(scores_K, w_star, top_n=10):
    """Quality of an inferred K-vec dim score against ground truth w*.

    Returns dict with:
      - spearman: rank correlation across all K dims
      - top_n_sign_agreement: fraction of top-N dims (by |scores|) whose
        sign matches the ground-truth sign for that dim
      - top_n_overlap: |top_n_inferred ∩ top_n_true| / top_n
    """
    K = len(scores_K)
    top_n = min(top_n, K)
    try:
        sp, _ = spearmanr(scores_K, w_star)
    except Exception:
        sp = float("nan")
    if not math.isfinite(sp):
        sp = 0.0

    top_inf = np.argsort(-np.abs(scores_K))[:top_n]
    top_true = np.argsort(-np.abs(w_star))[:top_n]
    sign_match = (np.sign(scores_K[top_inf]) == np.sign(w_star[top_inf])).mean()
    overlap = len(set(top_inf) & set(top_true)) / top_n

    return {
        "spearman": float(sp),
        "top_n_sign_agreement": float(sign_match),
        "top_n_overlap": float(overlap),
        "combined": float(0.5 * sp + 0.5 * (2 * sign_match - 1)),
    }


def predicted_rating(q_other, q_standard, temperature):
    """P(participant prefers `other` summary over `standard`).

    Returns float in (0, 1). 0.5 = no preference; >0.5 = other preferred."""
    return float(sigmoid(temperature * (q_other - q_standard)))


# ---------------------------------------------------------------------------
# Per-user simulation
# ---------------------------------------------------------------------------

def simulate_one_user(user, ctx, args, rng):
    """Run all 3 conditions for one user. Returns dict of per-condition
    results (per-trial data + fit-quality + predicted rating)."""
    embeddings = ctx["embeddings"]
    bt_scores = ctx["bt_scores"]
    V = ctx["V"]
    G = ctx["G"]
    mu = ctx["mu"]
    quintile_bounds = ctx["quintile_bounds"]
    mults = ctx["mults"]
    N, d = embeddings.shape
    K = V.shape[0]

    w_star = user["weights"]
    w_star_max = max(np.abs(w_star).max(), 1e-9)
    true_mults = np.array([
        w_star_to_mult(w_star[k], w_star_max, mults) for k in range(K)
    ])
    true_utils = bt_scores @ w_star

    # Sample training + test pairs. When predefined-pairs is set (e.g.,
    # dilemmas), both come from that pool — disjoint, per-user shuffled —
    # mirroring the human experiment's fixed-pair-pool design.
    predefined_pairs = ctx.get("predefined_pairs")
    if predefined_pairs is not None:
        pool = list(predefined_pairs)
        rng.shuffle(pool)
        test_pool = pool[:args.num_test_pairs]
        trial_pairs = pool[args.num_test_pairs:args.num_test_pairs + args.num_trials]
        test_a = np.array([p[0] for p in test_pool], dtype=int)
        test_b = np.array([p[1] for p in test_pool], dtype=int)
    else:
        trial_pairs = []
        while len(trial_pairs) < args.num_trials:
            a, b = rng.choice(N, size=2, replace=False)
            trial_pairs.append((int(a), int(b)))
        test_a = rng.integers(0, N, size=args.num_test_pairs)
        test_b = rng.integers(0, N, size=args.num_test_pairs)
        mask = test_a == test_b
        while mask.any():
            test_b[mask] = rng.integers(0, N, size=int(mask.sum()))
            mask = test_a == test_b
    test_choices = (true_utils[test_a] > true_utils[test_b]).astype(int)
    test_delta = embeddings[test_a] - embeddings[test_b]
    test_U = test_delta @ V.T  # (M, K)

    results = {"user_id": user["id"], "archetype": user["archetype"], "conditions": {}}
    checkpoints = make_checkpoints(args.num_trials, args.checkpoint_step)

    for cond in CONDITIONS:
        # Per-trial accumulators (collected once across all conditions' checkpoints).
        deltas = np.zeros((args.num_trials, d))
        ys = np.zeros(args.num_trials, dtype=int)
        lam_traj = np.zeros((args.num_trials, K))
        visible_traj = np.zeros((args.num_trials, K), dtype=bool)
        action_log = []

        for t, (idx_a, idx_b) in enumerate(trial_pairs):
            phi_a = embeddings[idx_a]
            phi_b = embeddings[idx_b]
            delta = phi_a - phi_b
            y = user_chooses(true_utils[idx_a], true_utils[idx_b], args.beta, rng)
            chosen_phi = phi_a if y == 1 else phi_b
            value_if_chosen = V @ (chosen_phi - mu)  # (K,)

            deltas[t] = delta
            ys[t] = y

            if cond == "choice_only":
                continue

            k_vis = min(args.top_k_inferences, K)
            visible = np.argsort(-np.abs(value_if_chosen))[:k_vis]
            visible_traj[t, visible] = True

            for k in visible:
                pre_mult = value_to_mult(value_if_chosen[k], quintile_bounds[:, k], mults)

                if cond == "inference_affirm":
                    action, applied = affirm_decision(pre_mult, true_mults[k], mults)
                else:  # inference_categories
                    applied = categories_decision(true_mults[k], mults)
                    action = "modify" if abs(applied - pre_mult) > 1e-9 else "none"

                applied = apply_noise(applied, mults, args.participant_noise, rng)
                lam_traj[t, k] = applied
                action_log.append({"trial": t, "dim": int(k), "action": action,
                                   "pre_mult": float(pre_mult),
                                   "true_mult": float(true_mults[k]),
                                   "applied": float(applied)})

        # Pre-compute full kernel/projection once; we'll slice into prefixes.
        D_full = deltas @ deltas.T          # (T, T)
        U_full = deltas @ V.T               # (T, K)
        cross_full = test_delta @ deltas.T  # (M, T)

        # Feedback multipliers Λ → design-matrix scale. For choice_only this
        # is all-ones. For inference conditions, the design-matrix entry per
        # (trial, dim) becomes:
        #
        #     Ũ_α[t,k] = U[t,k] · ((1 − α) + α · λ_tk)    for visible dims
        #     Ũ_α[t,k] = U[t,k]                            for invisible dims
        #
        # α=0 ⇒ projection only (feedback ignored).  α=1 ⇒ full feedback (the
        # original design). α∈(0,1) interpolates. Useful for calibration.
        alpha = getattr(args, "feedback_alpha", 1.0)
        feedback_full = np.ones_like(U_full)
        if cond != "choice_only":
            feedback_full[visible_traj] = ((1.0 - alpha)
                                            + alpha * lam_traj[visible_traj])
        U_adj_full = feedback_full * U_full

        ckpts = []
        for t_end in checkpoints:
            if t_end < 1 or t_end > args.num_trials:
                continue
            D_t = D_full[:t_end, :t_end]
            U_t = U_full[:t_end]
            U_adj_t = U_adj_full[:t_end]
            y_t = ys[:t_end].astype(float)

            # All three fits, every checkpoint, every condition.
            alpha = fit_standard_kernel(D_t, y_t, args.lambda_standard)
            beta_proj = fit_partial_primal(U_t, y_t, G, np.zeros(K),
                                           args.lambda_partial)
            if cond == "choice_only":
                beta_part = beta_proj  # Λ=1 → identical fit; skip recompute
            else:
                beta_part = fit_partial_primal(U_adj_t, y_t, G, np.zeros(K),
                                               args.lambda_partial)

            # Held-out scoring
            cross_t = cross_full[:, :t_end]
            logits_std = cross_t @ alpha
            logits_proj = test_U @ beta_proj
            logits_part = test_U @ beta_part
            acc_std = float(((logits_std > 0).astype(int) == test_choices).mean())
            acc_proj = float(((logits_proj > 0).astype(int) == test_choices).mean())
            acc_part = float(((logits_part > 0).astype(int) == test_choices).mean())
            ll_std = heldout_log_likelihood(logits_std, test_choices)
            ll_proj = heldout_log_likelihood(logits_proj, test_choices)
            ll_part = heldout_log_likelihood(logits_part, test_choices)

            # Summary quality vs ground truth (cheap; useful for trajectory)
            scores_std = U_t.T @ alpha            # V θ_std (K-dim projection)
            scores_proj = G @ beta_proj           # V θ_proj
            scores_part = G @ beta_part           # V θ_part
            q_std = summary_quality(scores_std, w_star, args.n_dimensions_shown)
            q_proj = summary_quality(scores_proj, w_star, args.n_dimensions_shown)
            q_part = summary_quality(scores_part, w_star, args.n_dimensions_shown)
            # Predicted DV uses the partial fit (= what the experiment shows).
            rating = predicted_rating(q_part["combined"], q_std["combined"],
                                      args.rating_temperature)

            ckpts.append({
                "n_trials": int(t_end),
                "test_acc_standard": acc_std,
                "test_acc_projected": acc_proj,
                "test_acc_partial": acc_part,
                "test_ll_standard": ll_std,
                "test_ll_projected": ll_proj,
                "test_ll_partial": ll_part,
                "spearman_standard": q_std["spearman"],
                "spearman_projected": q_proj["spearman"],
                "spearman_partial": q_part["spearman"],
                "topn_sign_standard": q_std["top_n_sign_agreement"],
                "topn_sign_projected": q_proj["top_n_sign_agreement"],
                "topn_sign_partial": q_part["top_n_sign_agreement"],
                "topn_overlap_standard": q_std["top_n_overlap"],
                "topn_overlap_projected": q_proj["top_n_overlap"],
                "topn_overlap_partial": q_part["top_n_overlap"],
                "combined_standard": q_std["combined"],
                "combined_projected": q_proj["combined"],
                "combined_partial": q_part["combined"],
                "rating_partial_vs_standard": rating,
            })

        results["conditions"][cond] = {
            "checkpoints": ckpts,
            "actions": action_log,
        }

    return results


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

FIT_TYPES = ["standard", "projected", "partial"]


def aggregate_final(per_user_results):
    """One row per (user, condition) using the final-T checkpoint.

    Carries metrics for all three fits (standard / projected / partial).
    """
    rows = []
    for user_res in per_user_results:
        uid = user_res["user_id"]
        for cond, res in user_res["conditions"].items():
            if not res["checkpoints"]:
                continue
            final = res["checkpoints"][-1]
            row = {
                "user_id": uid,
                "condition": cond,
                "n_trials": final["n_trials"],
                "rating_partial_vs_standard": final["rating_partial_vs_standard"],
            }
            for fit in FIT_TYPES:
                for m in ["test_acc", "test_ll", "spearman", "topn_sign",
                          "topn_overlap", "combined"]:
                    row[f"{m}_{fit}"] = final[f"{m}_{fit}"]
            rows.append(row)
    return pd.DataFrame(rows)


def aggregate_curves(per_user_results):
    """One row per (user, condition, n_trials, fit_type). Long format."""
    rows = []
    for user_res in per_user_results:
        uid = user_res["user_id"]
        for cond, res in user_res["conditions"].items():
            for ckpt in res["checkpoints"]:
                t = ckpt["n_trials"]
                for fit in FIT_TYPES:
                    rows.append({
                        "user_id": uid,
                        "condition": cond,
                        "fit_type": fit,
                        "n_trials": t,
                        "test_acc": ckpt[f"test_acc_{fit}"],
                        "test_ll": ckpt[f"test_ll_{fit}"],
                        "spearman": ckpt[f"spearman_{fit}"],
                        "combined": ckpt[f"combined_{fit}"],
                    })
    return pd.DataFrame(rows)


def write_summary(df, curves_df, args, output_dir, dim_names):
    lines = ["# Simulation Summary (revamped)\n"]
    lines.append("Predicts the experimental DV: probability that a participant "
                 "prefers the partial/projected K-dim summary over the unrestricted "
                 "standard summary.\n")

    lines.append("## Parameters\n")
    lines.append("| Parameter | Value |")
    lines.append("|-----------|-------|")
    lines.append(f"| Users | {args.num_users} |")
    lines.append(f"| Trials per user | {args.num_trials} |")
    lines.append(f"| Test pairs (held-out) | {args.num_test_pairs} |")
    lines.append(f"| K (dimensions) | {len(dim_names)} |")
    lines.append(f"| Top-K inferences visible | {args.top_k_inferences} |")
    lines.append(f"| Participant noise (per-dim slip prob) | {args.participant_noise} |")
    lines.append(f"| Beta (choice noise) | {args.beta} |")
    lines.append(f"| λ standard | {args.lambda_standard} |")
    lines.append(f"| λ partial  | {args.lambda_partial} |")
    lines.append(f"| Rating temperature τ | {args.rating_temperature} |")
    lines.append(f"| Top-N dims shown in summary | {args.n_dimensions_shown} |")
    lines.append(f"| Seed | {args.seed} |")
    lines.append("")

    lines.append("## Predicted Rating (P[partial > standard])\n")
    lines.append("Probability the simulated participant prefers the partial "
                 "K-dim summary (with feedback re-weighting) over the standard "
                 "summary. 0.5 = no effect; >0.5 = partial preferred.\n")
    lines.append("| Condition | Mean rating | SD | Pct > 0.5 |")
    lines.append("|-----------|-------------|----|-----------|")
    for cond in CONDITIONS:
        cdf = df[df["condition"] == cond]
        if cdf.empty:
            continue
        m = cdf["rating_partial_vs_standard"].mean()
        sd = cdf["rating_partial_vs_standard"].std()
        pct = (cdf["rating_partial_vs_standard"] > 0.5).mean() * 100
        lines.append(f"| {cond} | {m:.3f} | {sd:.3f} | {pct:.0f}% |")
    lines.append("")

    lines.append("## Summary-Quality Means\n")
    lines.append("Quality scores against ground-truth w*. Higher is better. "
                 "`combined` = 0.5·spearman + 0.5·(2·top-N sign agreement − 1).\n")
    metrics = ["spearman", "topn_sign", "topn_overlap", "combined"]
    headers = ["Condition", "Fit"] + metrics
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for cond in CONDITIONS:
        cdf = df[df["condition"] == cond]
        if cdf.empty:
            continue
        for fit in FIT_TYPES:
            cells = [cond, fit]
            for m in metrics:
                cells.append(f"{cdf[f'{m}_{fit}'].mean():.3f}")
            lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    lines.append("## Held-Out Choice Accuracy at T\n")
    lines.append("| Condition | standard | projected | partial | Δ proj−std | Δ part−std |")
    lines.append("|-----------|----------|-----------|---------|------------|------------|")
    for cond in CONDITIONS:
        cdf = df[df["condition"] == cond]
        if cdf.empty:
            continue
        a_s = cdf["test_acc_standard"].mean()
        a_pr = cdf["test_acc_projected"].mean()
        a_pa = cdf["test_acc_partial"].mean()
        lines.append(f"| {cond} | {a_s:.3f} | {a_pr:.3f} | {a_pa:.3f} | "
                     f"{a_pr - a_s:+.3f} | {a_pa - a_s:+.3f} |")
    lines.append("")

    lines.append("## Held-Out Log-Likelihood at T\n")
    lines.append("| Condition | LL standard | LL projected | LL partial | Δ proj−std | Δ part−std |")
    lines.append("|-----------|-------------|--------------|------------|------------|------------|")
    for cond in CONDITIONS:
        cdf = df[df["condition"] == cond]
        if cdf.empty:
            continue
        l_s = cdf["test_ll_standard"].mean()
        l_pr = cdf["test_ll_projected"].mean()
        l_pa = cdf["test_ll_partial"].mean()
        lines.append(f"| {cond} | {l_s:+.4f} | {l_pr:+.4f} | {l_pa:+.4f} | "
                     f"{l_pr - l_s:+.4f} | {l_pa - l_s:+.4f} |")
    lines.append("")

    lines.append("## Significance Tests (paired Wilcoxon)\n")
    lines.append("Tests whether the predicted rating is reliably > 0.5 within each "
                 "condition (i.e., the partial-K-dim summary wins) and whether "
                 "inference conditions differ from choice_only.\n")
    lines.append("| Comparison | n | mean | Wilcoxon p |")
    lines.append("|------------|---|------|------------|")
    for cond in CONDITIONS:
        cdf = df[df["condition"] == cond]
        if cdf.empty:
            continue
        ratings = cdf["rating_partial_vs_standard"].values
        try:
            stat, p = wilcoxon(ratings - 0.5, zero_method="zsplit")
        except ValueError:
            p = float("nan")
        lines.append(f"| {cond} vs 0.5 | {len(ratings)} | {ratings.mean():.3f} | {p:.4f} |")

    base = df[df["condition"] == "choice_only"]["rating_partial_vs_standard"].values
    for cond in ["inference_affirm", "inference_categories"]:
        other = df[df["condition"] == cond]["rating_partial_vs_standard"].values
        if len(other) == 0 or len(base) == 0:
            continue
        n = min(len(base), len(other))
        try:
            stat, p = wilcoxon(other[:n], base[:n])
        except ValueError:
            p = float("nan")
        lines.append(f"| {cond} vs choice_only | {n} | "
                     f"Δ={other[:n].mean() - base[:n].mean():+.3f} | {p:.4f} |")
    lines.append("")

    # ----------------------------------------------------------------------
    # Learning-curve sanity check
    # ----------------------------------------------------------------------
    lines.append("## Learning Curves (test acc by trial count)\n")
    lines.append("Mean held-out accuracy across users at each checkpoint. "
                 "Should rise monotonically with more trials if learning is "
                 "working.\n")
    if curves_df is not None and not curves_df.empty:
        ts = sorted(curves_df["n_trials"].unique())
        # Show ~5 evenly-spaced rows so the table stays compact.
        if len(ts) > 5:
            idx = np.linspace(0, len(ts) - 1, 5).astype(int)
            ts_show = [ts[i] for i in idx]
        else:
            ts_show = ts
        header = ["Condition", "Fit"] + [f"T={t}" for t in ts_show]
        lines.append("| " + " | ".join(header) + " |")
        lines.append("| " + " | ".join(["---"] * len(header)) + " |")
        for cond in CONDITIONS:
            cdf = curves_df[curves_df["condition"] == cond]
            if cdf.empty:
                continue
            for fit_label in FIT_TYPES:
                if fit_label not in cdf["fit_type"].unique():
                    continue
                row = [cond, fit_label]
                for t in ts_show:
                    sub = cdf[(cdf["fit_type"] == fit_label) & (cdf["n_trials"] == t)]
                    row.append(f"{sub['test_acc'].mean():.3f}" if not sub.empty else "—")
                lines.append("| " + " | ".join(row) + " |")
        lines.append("")

        # Monotonicity check: report fit/cond combos where final acc <= half-T acc.
        bad = []
        for cond in CONDITIONS:
            for fit_label in FIT_TYPES:
                sub = (curves_df[(curves_df["condition"] == cond)
                                 & (curves_df["fit_type"] == fit_label)]
                       .groupby("n_trials")["test_acc"].mean())
                if len(sub) < 3:
                    continue
                t_half = sub.index[len(sub) // 2]
                t_full = sub.index[-1]
                if sub.loc[t_full] <= sub.loc[t_half] - 1e-3:
                    bad.append(f"{cond}/{fit_label}: T={t_half}→{sub.loc[t_half]:.3f}, "
                               f"T={t_full}→{sub.loc[t_full]:.3f}")
        if bad:
            lines.append("**⚠ Non-monotonic learning detected (acc didn't improve "
                         "from mid-T to end-T):**\n")
            for b in bad:
                lines.append(f"- {b}")
            lines.append("")

    lines.append("## Go/No-Go Read\n")
    pct_inf_aff = (df[df["condition"] == "inference_affirm"]
                   ["rating_partial_vs_standard"] > 0.5).mean() * 100
    pct_inf_cat = (df[df["condition"] == "inference_categories"]
                   ["rating_partial_vs_standard"] > 0.5).mean() * 100
    pct_choice = (df[df["condition"] == "choice_only"]
                  ["rating_partial_vs_standard"] > 0.5).mean() * 100
    lines.append(f"- Predicted win rate (other > standard) — "
                 f"choice_only: {pct_choice:.0f}% · "
                 f"inference_affirm: {pct_inf_aff:.0f}% · "
                 f"inference_categories: {pct_inf_cat:.0f}%")
    lines.append("- A meaningful experimental effect requires the inference "
                 "conditions to be reliably above choice_only AND the "
                 "Wilcoxon-vs-0.5 test to reach p<0.05 with the planned N.")
    lines.append("- If the inference conditions don't outperform choice_only "
                 "in this sim, sweep `--participant-noise` (try 0.0 / 0.15 / 0.30) "
                 "and `--num-trials` to find the regime where the effect emerges.")

    with open(output_dir / "summary.md", "w") as f:
        f.write("\n".join(lines) + "\n")


FIT_STYLE = {
    "standard":  {"color": "#444444", "marker": "o", "label": "MLE (standard kernel)"},
    "projected": {"color": "#1f77b4", "marker": "s", "label": "MLE projected onto basis"},
    "partial":   {"color": "#d62728", "marker": "^", "label": "Partial (feedback re-weighted)"},
}


def plot_learning_curves(curves_df, output_dir):
    """Held-out test acc and LL vs n_trials, one panel per condition.

    Three lines per panel: standard / projected / partial.
    """
    if curves_df is None or curves_df.empty:
        return
    fig, axes = plt.subplots(2, len(CONDITIONS), figsize=(4.8 * len(CONDITIONS), 8),
                             sharex=True)
    if len(CONDITIONS) == 1:
        axes = axes[:, None]

    metric_specs = [
        ("test_acc", "Held-out accuracy", 0.5),
        ("test_ll", "Held-out log-likelihood", None),
    ]
    for row_idx, (col, ylabel, hline) in enumerate(metric_specs):
        for col_idx, cond in enumerate(CONDITIONS):
            ax = axes[row_idx, col_idx]
            cdf = curves_df[curves_df["condition"] == cond]
            if cdf.empty:
                ax.set_visible(False)
                continue
            for fit_label in FIT_TYPES:
                sub = cdf[cdf["fit_type"] == fit_label]
                if sub.empty:
                    continue
                grouped = sub.groupby("n_trials")[col]
                mean = grouped.mean()
                sem = grouped.std() / np.sqrt(grouped.count())
                style = FIT_STYLE[fit_label]
                ax.plot(mean.index, mean.values,
                        marker=style["marker"], color=style["color"],
                        label=style["label"], linewidth=2)
                ax.fill_between(mean.index, mean.values - sem.values,
                                mean.values + sem.values,
                                color=style["color"], alpha=0.15)
            if hline is not None:
                ax.axhline(hline, color="gray", linestyle="--", alpha=0.5)
            if row_idx == 0:
                ax.set_title(cond, fontweight="bold")
            if row_idx == len(metric_specs) - 1:
                ax.set_xlabel("# trials collected")
            if col_idx == 0:
                ax.set_ylabel(ylabel)
            ax.grid(True, alpha=0.3)
            if col_idx == 0 and row_idx == 0:
                ax.legend(loc="lower right", fontsize=9)
    fig.suptitle("Learning curves — three fits per condition",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig(output_dir / "learning_curves.png", dpi=150, bbox_inches="tight")
    plt.close()


def plot_results(df, output_dir):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # Predicted rating distribution per condition
    ax = axes[0]
    data = []
    labels = []
    for cond in CONDITIONS:
        cdf = df[df["condition"] == cond]
        if not cdf.empty:
            data.append(cdf["rating_partial_vs_standard"].values)
            labels.append(cond.replace("_", "\n"))
    if data:
        ax.boxplot(data, tick_labels=labels, showmeans=True)
        ax.axhline(0.5, color="gray", linestyle="--", alpha=0.5, label="no preference")
        ax.set_ylabel("P(partial summary preferred over standard)")
        ax.set_title("Predicted experimental DV", fontweight="bold")
        ax.legend(loc="lower right")
        ax.set_ylim(0, 1)

    # Quality decomposition: spearman per fit
    ax = axes[1]
    width = 0.27
    x = np.arange(len(CONDITIONS))
    for i, fit in enumerate(FIT_TYPES):
        means = []
        for cond in CONDITIONS:
            cdf = df[df["condition"] == cond]
            means.append(cdf[f"spearman_{fit}"].mean() if not cdf.empty else 0)
        ax.bar(x + (i - 1) * width, means, width,
               color=FIT_STYLE[fit]["color"], label=FIT_STYLE[fit]["label"])
    ax.set_xticks(x)
    ax.set_xticklabels([c.replace("_", "\n") for c in CONDITIONS])
    ax.set_ylabel("Spearman(scores, w*)")
    ax.set_title("Summary quality (rank corr. with ground truth)", fontweight="bold")
    ax.legend(fontsize=8)
    ax.grid(True, axis="y", alpha=0.3)

    fig.suptitle("Predicting the experimental DV — final 3 conditions",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig(output_dir / "predicted_dv.png", dpi=150, bbox_inches="tight")
    plt.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_simulation(args):
    rng = np.random.default_rng(args.seed)

    print("Loading data...")
    embeddings, bt_scores, V, G, mu, option_ids, dim_names = load_data(
        args.embeddings_parquet, args.bt_scores, args.directions,
        option_id_column=args.option_id_column,
    )
    N, d = embeddings.shape
    K = V.shape[0]
    print(f"  Options: {N}, d: {d}, K: {K}")

    # Build per-dim quintile boundaries from the embedding pool's projections.
    # We use V·(φ - μ) since the post-eval categorization works on signed
    # value_if_chosen scores symmetric around 0.
    centered = embeddings - mu[np.newaxis, :]
    pool_proj = centered @ V.T  # (N, K)
    quintile_bounds = perdim_quintile_boundaries(pool_proj, n_cats=len(DEFAULT_MULTS))

    print("Generating synthetic users...")
    users = generate_users(args.num_users, K, rng)

    predefined_pairs = None
    if args.predefined_pairs:
        predefined_pairs = load_predefined_pairs(args.predefined_pairs, option_ids)
        need = args.num_trials + args.num_test_pairs
        if len(predefined_pairs) < need:
            raise ValueError(f"predefined-pairs pool has only {len(predefined_pairs)} "
                             f"pairs, but need {need} = num_trials + num_test_pairs.")

    mults = DEFAULT_MULTS * args.multiplier_scale
    ctx = {
        "embeddings": embeddings, "bt_scores": bt_scores,
        "V": V, "G": G, "mu": mu,
        "quintile_bounds": quintile_bounds, "mults": mults,
        "predefined_pairs": predefined_pairs,
    }

    per_user_results = []
    print("Running simulation...")
    for i, user in enumerate(users):
        per_user_results.append(simulate_one_user(user, ctx, args, rng))
        if (i + 1) % 10 == 0 or i == len(users) - 1:
            print(f"  user {i + 1}/{len(users)} done")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = aggregate_final(per_user_results)
    df.to_csv(output_dir / "per_user_per_condition.csv", index=False)
    print(f"Saved per_user_per_condition.csv ({len(df)} rows)")

    curves_df = aggregate_curves(per_user_results)
    curves_df.to_csv(output_dir / "learning_curves.csv", index=False)
    print(f"Saved learning_curves.csv ({len(curves_df)} rows)")

    with open(output_dir / "user_profiles.json", "w") as f:
        profiles = []
        for u in users:
            profiles.append({
                "id": int(u["id"]),
                "archetype": u["archetype"],
                "weights": {dim_names[k]: float(u["weights"][k]) for k in range(K)},
            })
        json.dump(profiles, f, indent=2)
    print("Saved user_profiles.json")

    write_summary(df, curves_df, args, output_dir, dim_names)
    print("Saved summary.md")
    try:
        plot_results(df, output_dir)
        print("Saved predicted_dv.png")
    except Exception as e:
        print(f"Warning: could not save predicted_dv.png: {e}")
    try:
        plot_learning_curves(curves_df, output_dir)
        print("Saved learning_curves.png")
    except Exception as e:
        print(f"Warning: could not save learning_curves.png: {e}")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--embeddings-parquet", required=True)
    p.add_argument("--bt-scores", required=True)
    p.add_argument("--directions", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--option-id-column", default="movie_id")

    p.add_argument("--num-users", type=int, default=50)
    p.add_argument("--num-trials", type=int, default=20,
                   help="Trials per user. Defaults to experiment N=20.")
    p.add_argument("--num-test-pairs", type=int, default=200,
                   help="Held-out test pairs (diagnostic only).")
    p.add_argument("--top-k-inferences", type=int, default=5,
                   help="Number of dims visible per trial in inference conditions.")
    p.add_argument("--n-dimensions-shown", type=int, default=10,
                   help="Top-N dims shown in the post-experiment summary.")
    p.add_argument("--participant-noise", type=float, default=0.10,
                   help="Probability the user picks an adjacent (wrong) "
                        "category on a given visible dim.")
    p.add_argument("--beta", type=float, default=2.0,
                   help="Choice-noise temperature (BTL).")
    p.add_argument("--lambda-standard", type=float, default=10.0,
                   help="L2 regularization for the kernel-logistic fit.")
    p.add_argument("--lambda-partial", type=float, default=0.05,
                   help="L2 regularization for the K-dim primal fit "
                        "(both projected and partial-with-feedback). "
                        "Default 0.05 matches the calibrated value from the "
                        "joint pilot + sim grid sweep (consistent across "
                        "sources).")
    p.add_argument("--feedback-alpha", type=float, default=0.5,
                   help="Feedback strength α ∈ [0, 1] for the partial fit. "
                        "Ũ_α = U·((1−α) + α·λ_tk). α=0 collapses partial to "
                        "projected; α=1 is full feedback. Default 0.5 is the "
                        "calibrated mid-point recommendation.")
    p.add_argument("--multiplier-scale", type=float, default=1.0,
                   help="Scalar multiplied into DEFAULT_MULTS = "
                        "[-1.5,-1.0,0,1.0,1.5]. Affects both how the synthetic "
                        "user maps w* to a category AND how the fit interprets "
                        "the chosen category. For calibration.")
    p.add_argument("--rating-temperature", type=float, default=5.0,
                   help="Temperature for sigmoid mapping quality gap to "
                        "predicted rating.")
    p.add_argument("--checkpoint-step", type=int, default=1,
                   help="Refit at every Nth trial. 1 = every trial (default), "
                        "5 = at trials 5, 10, 15, ... 0 disables intermediate "
                        "checkpoints (only fits at T).")
    p.add_argument("--seed", type=int, default=42)

    p.add_argument("--predefined-pairs", default=None,
                   help="Optional JSON of (option_a_id, option_b_id) pairs "
                        "(e.g., dilemma pairs). When set, training and test "
                        "trials are sampled WITHOUT replacement from this pool, "
                        "matching the human experiment.")

    # Deprecated args (kept for backward compatibility with run_*.sh)
    p.add_argument("--slider-noise", type=float, default=None,
                   help="DEPRECATED: ignored. Use --participant-noise.")
    p.add_argument("--learning-rate", type=float, default=None,
                   help="DEPRECATED: ignored (no SGD).")
    p.add_argument("--projection-lambda", type=float, default=None,
                   help="DEPRECATED: ignored.")

    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_simulation(args)
