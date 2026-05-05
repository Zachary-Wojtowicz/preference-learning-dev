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
    2. inference_affirm       — top-K=3 visible dims, Affirm/Moderate/Remove.
    3. inference_categories   — top-K=3 visible dims, 5-category picker.

  Fits (computed for every condition, so we can compare apples-to-apples):
    A. standard   — kernel logistic regression in full d-dim space (MLE).
    B. projected  — K-dim primal logistic regression on plain U
                    (MLE projected onto the interpretable basis; ignores
                    feedback). λ_partial regularization.
    C. partial    — K-dim primal logistic with feedback-adjusted gradients.
                    Predictions use raw U; gradients use Ũ where:
                    - affirm/none dims: passthrough (U_adj = U)
                    - modify/moderate dims: midpoint replacement
                    - remove dims: zeroed out
                    α blends between U and replacement: (1-α)*U + α*midpoint
    D. blend      — post-hoc ensemble of standard + partial:
                    logit_blend = (1-γ)*logit_std + γ*logit_partial
                    γ=0 is pure kernel, γ=1 is pure partial.

  For choice_only, Λ ≡ 1, so projected and partial are identical fits
  (we still compute both for plotting consistency).

Pipeline per simulated user × condition:
  1. Sample T trials (idx_a, idx_b); user chooses by their true K-vec w*.
  2. For inference conditions: pick top-K dims by |V·φ_chosen|, compute the
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
from sklearn.model_selection import StratifiedKFold


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

def generate_users(num_users, K, rng, sparsity=0.3, mag_min=1.5, mag_max=3.0):
    """Sparse random users. Each gets ±[mag_min, mag_max] weights on a random
    subset of dimensions, 0 elsewhere — emulates a person who cares about
    a few specific qualities and is indifferent to the rest.

    Defaults (sparsity=0.3, mag_min=1.5, mag_max=3.0) approximate real
    pilot participants: 2-3 strongly-active dims out of K=10. With weaker
    settings (sparsity=0.5, mag in [0.7, 1.0]) the resulting choices are
    too noisy to learn from at T=20 — random_projection accuracy actually
    DROPS with more data because the fit overfits noise (T/K=2.0 with
    correlated features). Realistic concentration → choice signal large
    enough that LOO accuracy rises with T.
    """
    users = []
    n_active_target = max(2, int(round(sparsity * K)))
    for i in range(num_users):
        n_active = max(2, int(rng.normal(n_active_target, max(1, sparsity * K * 0.3))))
        n_active = min(n_active, K)
        active = rng.choice(K, size=n_active, replace=False)
        weights = np.zeros(K)
        magnitudes = rng.uniform(mag_min, mag_max, size=n_active)
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


def perdim_bin_midpoints(values_pool, n_cats=5):
    """For each dimension k, compute the midpoint of each of the n_cats
    quintile bins.  Returns (n_cats, K) array.

    Uses the symmetric distribution {v, -v} to match
    perdim_quintile_boundaries.  Midpoints are at quantiles
    [1/(2n), 3/(2n), ..., (2n-1)/(2n)] — the center of mass of each bin.
    """
    T, K = values_pool.shape
    midpoint_qs = np.array([(2 * i + 1) / (2 * n_cats) for i in range(n_cats)])
    midpoints = np.zeros((n_cats, K))
    for k in range(K):
        v = values_pool[:, k]
        symm = np.concatenate([v, -v])
        midpoints[:, k] = np.quantile(symm, midpoint_qs)
    return midpoints


def compute_beta_prior(lam_traj, t_end, K):
    """Compute per-dimension prior mean from feedback observations.

    For each dimension k, averages all finite (non-NaN) feedback values
    across trials [0, t_end). Dimensions with no feedback get 0.
    Returns (K,) array.
    """
    bp = np.zeros(K)
    prefix = lam_traj[:t_end]  # (t_end, K)
    for k in range(K):
        vals = prefix[:, k]
        finite = vals[np.isfinite(vals)]
        if len(finite) > 0:
            bp[k] = finite.mean()
    return bp


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


def affirm_decision(pre_mult, true_mult, mults):
    """Simulate the participant's affirm/remove decision.

    Affirm = "yes, the default-selected category is right for me on this dim."
    Remove = "this dim is irrelevant or the default has the wrong sign."
    Returns (action_label, _unused). Caller computes the stored value from
    the pre-selected category midpoint (affirm) or 0.0 (remove).
    """
    eps = 1e-9
    if abs(pre_mult) < eps and abs(true_mult) < eps:
        return "affirm", 0.0
    if abs(pre_mult) < eps:
        return "affirm", 0.0
    if abs(true_mult) < eps:
        return "remove", 0.0
    if (pre_mult > 0) != (true_mult > 0):
        return "remove", 0.0
    return "affirm", pre_mult


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

def fit_btl(X, X_grad, y, lam, P=None, XXT=None,
            beta_prior=None, mu_prior=0.0, max_iter=15, tol=1e-7):
    """Unified BTL logistic regression.

    Objective:
      min_b  -LL(Xb, y) + (lam/2) b'Pb + (mu/2) ||b - b_prior||^2

    When P is None, penalty is lam*||b||^2 (no matrix allocated).
    When beta_prior is provided with mu_prior > 0, adds a Gaussian prior
    pulling b toward the feedback-implied values.
    """
    T, p = X.shape
    theta = np.zeros(p)
    use_woodbury = (T * 2 < p) and (P is None) and (beta_prior is None)

    if use_woodbury and XXT is None:
        XXT = X @ X.T

    has_prior = beta_prior is not None and mu_prior > 0

    for _ in range(max_iter):
        logits = X @ theta
        prob = sigmoid(logits)
        w = prob * (1 - prob) + 1e-10
        Ptheta = lam * theta if P is None else lam * (P @ theta)
        grad = X_grad.T @ (prob - y) + Ptheta
        if has_prior:
            grad += mu_prior * (theta - beta_prior)

        if use_woodbury:
            M = np.diag(1.0 / w) + XXT / lam
            v = np.linalg.solve(M, X @ grad)
            d_theta = -(grad / lam - X.T @ v / (lam ** 2))
        else:
            if P is None:
                H = X.T @ (w[:, None] * X) + lam * np.eye(p)
            else:
                H = X.T @ (w[:, None] * X) + lam * P
            if has_prior:
                H += mu_prior * np.eye(p)
            d_theta = np.linalg.solve(H, -grad)

        theta = theta + d_theta
        if np.max(np.abs(d_theta)) < tol:
            break
    return theta


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
    V_rand = ctx["V_rand"]
    G_rand = ctx["G_rand"]
    mu = ctx["mu"]
    quintile_bounds = ctx["quintile_bounds"]
    bin_midpoints = ctx["bin_midpoints"]
    mults = ctx["mults"]
    N, d = embeddings.shape
    K = V.shape[0]

    w_star = user["weights"]
    w_star_max = max(np.abs(w_star).max(), 1e-9)
    true_mults = np.array([
        w_star_to_mult(w_star[k], w_star_max, mults) for k in range(K)
    ])
    # Generate choices from embedding projections (same space the model fits on)
    # This avoids the lossy bt_scores bottleneck.
    item_proj = embeddings @ V.T  # (N, K) — same projection as U_t
    true_utils = item_proj @ w_star

    # Sample training pairs only. LOO replaces the fixed held-out test set.
    predefined_pairs = ctx.get("predefined_pairs")
    if predefined_pairs is not None:
        pool = list(predefined_pairs)
        rng.shuffle(pool)
        trial_pairs = pool[:args.num_trials]
    else:
        trial_pairs = []
        while len(trial_pairs) < args.num_trials:
            a, b = rng.choice(N, size=2, replace=False)
            trial_pairs.append((int(a), int(b)))

    results = {"user_id": user["id"], "archetype": user["archetype"], "conditions": {}}
    checkpoints = make_checkpoints(args.num_trials, args.checkpoint_step)

    for cond in CONDITIONS:
        # Per-trial accumulators (collected once across all conditions' checkpoints).
        deltas = np.zeros((args.num_trials, d))
        ys = np.zeros(args.num_trials, dtype=int)
        lam_traj = np.full((args.num_trials, K), np.nan)  # NaN = passthrough
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

            # Pre-compute delta projection for feedback storage
            delta_proj = delta @ V.T  # (K,) projection onto each dim

            if cond == "choice_only":
                continue

            k_vis = min(args.top_k_inferences, K)
            visible = np.argsort(-np.abs(value_if_chosen))[:k_vis]
            visible_traj[t, visible] = True

            for k in visible:
                pre_mult = value_to_mult(value_if_chosen[k], quintile_bounds[:, k], mults)

                if cond == "inference_affirm":
                    action, _ = affirm_decision(pre_mult, true_mults[k], mults)
                    # Affirm-mode noise: probability of accidentally hitting
                    # the wrong button (binary flip). This is the 1-bit analog
                    # of the categories-mode adjacent-bucket slip.
                    if args.participant_noise > 0 and rng.random() < args.participant_noise:
                        action = "remove" if action == "affirm" else "affirm"
                    if action == "remove":
                        lam_traj[t, k] = 0.0
                        applied = 0.0
                    else:
                        # Affirm = confirm the algorithm's pre-selected category.
                        # Store the midpoint of that category (same calibrated
                        # scale as inference_categories' confirm path). This
                        # carries the 1-bit affirm signal at a stable magnitude
                        # rather than a noisy delta projection.
                        cat_idx = int(np.argmin(np.abs(mults - pre_mult)))
                        lam_traj[t, k] = bin_midpoints[cat_idx, k]
                        applied = pre_mult
                else:  # inference_categories
                    applied = categories_decision(true_mults[k], mults)
                    action = "modify" if abs(applied - pre_mult) > 1e-9 else "confirm"
                    applied = apply_noise(applied, mults, args.participant_noise, rng)
                    # Store midpoint for ALL visible dims (not just modified)
                    cat_idx = int(np.argmin(np.abs(mults - applied)))
                    lam_traj[t, k] = bin_midpoints[cat_idx, k]
                action_log.append({"trial": t, "dim": int(k), "action": action,
                                   "pre_mult": float(pre_mult),
                                   "true_mult": float(true_mults[k]),
                                   "applied": float(applied)})

        # Pre-compute projected design matrices.
        U_full = deltas @ V.T               # (T, K) -- LLM basis
        U_rand_full = deltas @ V_rand.T     # (T, K) -- random basis

        # Feedback prior: mu_prior = alpha (independent of lambda).
        # Per-condition alpha: --feedback-alpha-affirm and
        # --feedback-alpha-categories override --feedback-alpha when set.
        # Affirm carries less information per dim than categories (1 bit vs ~2.3
        # bits), so it generally benefits from a smaller mu_prior.
        if cond == "inference_affirm":
            mu_prior = (args.feedback_alpha_affirm
                        if args.feedback_alpha_affirm is not None
                        else args.feedback_alpha)
        elif cond == "inference_categories":
            mu_prior = (args.feedback_alpha_categories
                        if args.feedback_alpha_categories is not None
                        else args.feedback_alpha)
        else:  # choice_only
            mu_prior = args.feedback_alpha

        ckpts = []
        min_loo = 3
        for t_end in checkpoints:
            if t_end < min_loo or t_end > args.num_trials:
                continue
            y_prefix = ys[:t_end].astype(float)
            if len(np.unique(y_prefix)) < 2:
                continue

            # --- LOO evaluation (matches pilot learning_curves.py) ---
            all_idx = np.arange(t_end)
            y_int = y_prefix.astype(int)
            loo_logits = {
                "random_projection": np.zeros(t_end),
                "projection_only": np.zeros(t_end),
                "projection_alpha": np.zeros(t_end),
            }
            for held_out in range(t_end):
                train_idx = np.concatenate([all_idx[:held_out],
                                            all_idx[held_out+1:]])
                y_train = y_prefix[train_idx]
                if len(np.unique(y_train)) < 2:
                    continue  # logits stay 0 (chance)

                # Random projection baseline (P=I since G_rand=I)
                beta_rand = fit_btl(U_rand_full[train_idx], U_rand_full[train_idx],
                                    y_train, args.lambda_standard)
                loo_logits["random_projection"][held_out] = U_rand_full[held_out] @ beta_rand

                # LLM projection only (P=I)
                beta_p0 = fit_btl(U_full[train_idx], U_full[train_idx],
                                  y_train, args.lambda_partial)
                loo_logits["projection_only"][held_out] = U_full[held_out] @ beta_p0

                # LLM projection with feedback prior
                if cond == "choice_only":
                    loo_logits["projection_alpha"][held_out] = \
                        loo_logits["projection_only"][held_out]
                else:
                    bp = compute_beta_prior(lam_traj, t_end, K)
                    beta_pa = fit_btl(U_full[train_idx], U_full[train_idx],
                                      y_train, args.lambda_partial,
                                      beta_prior=bp, mu_prior=mu_prior)
                    loo_logits["projection_alpha"][held_out] = \
                        U_full[held_out] @ beta_pa

            # LOO metrics
            cv_acc = {}
            cv_ll = {}
            for fit_label, logits in loo_logits.items():
                cv_acc[fit_label] = float(
                    ((logits > 0).astype(int) == y_int).mean())
                cv_ll[fit_label] = heldout_log_likelihood(logits, y_prefix)

            # --- Summary quality (full fit on all t_end trials) ---
            U_t = U_full[:t_end]
            U_rand_t = U_rand_full[:t_end]
            beta_rand_full = fit_btl(U_rand_t, U_rand_t, y_prefix,
                                     args.lambda_standard)
            beta_proj_full = fit_btl(U_t, U_t, y_prefix, args.lambda_partial)
            if cond == "choice_only":
                beta_part_full = beta_proj_full
            else:
                bp_full = compute_beta_prior(lam_traj, t_end, K)
                beta_part_full = fit_btl(U_t, U_t, y_prefix,
                                         args.lambda_partial,
                                         beta_prior=bp_full, mu_prior=mu_prior)
            scores_rand = (V @ V_rand.T) @ beta_rand_full
            scores_proj = beta_proj_full  # P=I, so scores = beta directly
            scores_part = beta_part_full
            q_rand = summary_quality(scores_rand, w_star, args.n_dimensions_shown)
            q_proj = summary_quality(scores_proj, w_star, args.n_dimensions_shown)
            q_part = summary_quality(scores_part, w_star, args.n_dimensions_shown)
            rating = predicted_rating(q_part["combined"], q_rand["combined"],
                                      args.rating_temperature)

            ckpts.append({
                "n_trials": int(t_end),
                "test_acc_random_projection": cv_acc["random_projection"],
                "test_acc_projection_only": cv_acc["projection_only"],
                "test_acc_projection_alpha": cv_acc["projection_alpha"],
                "test_ll_random_projection": cv_ll["random_projection"],
                "test_ll_projection_only": cv_ll["projection_only"],
                "test_ll_projection_alpha": cv_ll["projection_alpha"],
                "spearman_random_projection": q_rand["spearman"],
                "spearman_projection_only": q_proj["spearman"],
                "spearman_projection_alpha": q_part["spearman"],
                "topn_sign_random_projection": q_rand["top_n_sign_agreement"],
                "topn_sign_projection_only": q_proj["top_n_sign_agreement"],
                "topn_sign_projection_alpha": q_part["top_n_sign_agreement"],
                "topn_overlap_random_projection": q_rand["top_n_overlap"],
                "topn_overlap_projection_only": q_proj["top_n_overlap"],
                "topn_overlap_projection_alpha": q_part["top_n_overlap"],
                "combined_random_projection": q_rand["combined"],
                "combined_projection_only": q_proj["combined"],
                "combined_projection_alpha": q_part["combined"],
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

FIT_TYPES = ["random_projection", "projection_only", "projection_alpha"]


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
    lines.append(f"| γ (projection blend) | {args.gamma} |")
    aa = (args.feedback_alpha_affirm if args.feedback_alpha_affirm is not None
          else args.feedback_alpha)
    ac = (args.feedback_alpha_categories if args.feedback_alpha_categories is not None
          else args.feedback_alpha)
    lines.append(f"| α default | {args.feedback_alpha} |")
    lines.append(f"| α affirm | {aa} |")
    lines.append(f"| α categories | {ac} |")
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

    lines.append("## LOO Choice Accuracy at T\n")
    lines.append("| Condition | random_proj | projection_only | projection_alpha | D alpha-rand |")
    lines.append("|-----------|-------------|-----------------|------------------|-------------|")
    for cond in CONDITIONS:
        cdf = df[df["condition"] == cond]
        if cdf.empty:
            continue
        a_s = cdf["test_acc_random_projection"].mean()
        a_po = cdf["test_acc_projection_only"].mean()
        a_pa = cdf["test_acc_projection_alpha"].mean()
        lines.append(f"| {cond} | {a_s:.3f} | {a_po:.3f} | {a_pa:.3f} | "
                     f"{a_pa - a_s:+.3f} |")
    lines.append("")

    lines.append("## LOO Log-Likelihood at T\n")
    lines.append("| Condition | LL random_proj | LL projection_only | LL projection_alpha | D alpha-rand |")
    lines.append("|-----------|----------------|--------------------|--------------------|-------------|")
    for cond in CONDITIONS:
        cdf = df[df["condition"] == cond]
        if cdf.empty:
            continue
        l_s = cdf["test_ll_random_projection"].mean()
        l_po = cdf["test_ll_projection_only"].mean()
        l_pa = cdf["test_ll_projection_alpha"].mean()
        lines.append(f"| {cond} | {l_s:+.4f} | {l_po:+.4f} | {l_pa:+.4f} | "
                     f"{l_pa - l_s:+.4f} |")
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
    "random_projection": {"color": "#444444", "marker": "o", "label": "Random projection (baseline)"},
    "projection_only":   {"color": "#1f77b4", "marker": "s", "label": "LLM projection (no feedback)"},
    "projection_alpha":  {"color": "#d62728", "marker": "^", "label": "LLM projection + feedback"},
}


def plot_learning_curves(curves_df, output_dir, use_bootstrap=False, cv_folds=5):
    """LOO accuracy and LL vs n_trials, one panel per condition.
    Normal-approx 95% CIs by default; bootstrap if use_bootstrap=True.
    """
    if curves_df is None or curves_df.empty:
        return
    fig, axes = plt.subplots(2, len(CONDITIONS), figsize=(4.8 * len(CONDITIONS), 8),
                             sharex=True)
    if len(CONDITIONS) == 1:
        axes = axes[:, None]

    if use_bootstrap:
        rng_boot = np.random.default_rng(42)
        N_BOOT = 2000

    metric_specs = [
        ("test_acc", "LOO accuracy", 0.5),
        ("test_ll", "LOO log-likelihood", None),
    ]
    for row_idx, (col, ylabel, hline) in enumerate(metric_specs):
        for col_idx, cond in enumerate(CONDITIONS):
            ax = axes[row_idx, col_idx]
            cdf = curves_df[curves_df["condition"] == cond]
            if cdf.empty:
                ax.set_visible(False)
                continue
            n_part = cdf["user_id"].nunique()
            for fit_label in FIT_TYPES:
                sub = cdf[cdf["fit_type"] == fit_label]
                if sub.empty:
                    continue
                style = FIT_STYLE[fit_label]
                ts = sorted(sub["n_trials"].unique())
                means, ci_lo, ci_hi = [], [], []
                for t_val in ts:
                    vals = sub[sub["n_trials"] == t_val][col].values
                    m = vals.mean()
                    means.append(m)
                    if len(vals) < 2:
                        ci_lo.append(m); ci_hi.append(m)
                    elif use_bootstrap:
                        boot = np.array([
                            vals[rng_boot.integers(0, len(vals), size=len(vals))].mean()
                            for _ in range(N_BOOT)
                        ])
                        ci_lo.append(np.percentile(boot, 2.5))
                        ci_hi.append(np.percentile(boot, 97.5))
                    else:
                        sem = vals.std() / np.sqrt(len(vals))
                        ci_lo.append(m - 1.96 * sem)
                        ci_hi.append(m + 1.96 * sem)
                ax.plot(ts, means, marker=style["marker"], color=style["color"],
                        label=style["label"], linewidth=2, markersize=4)
                ax.fill_between(ts, ci_lo, ci_hi,
                                color=style["color"], alpha=0.10)
            if hline is not None:
                ax.axhline(hline, color="gray", linestyle="--", alpha=0.5)
            if row_idx == 0:
                ax.set_title(f"{cond}\n(n={n_part})", fontweight="bold")
            if row_idx == len(metric_specs) - 1:
                ax.set_xlabel("prefix length (# trials used)")
            if col_idx == 0:
                ax.set_ylabel(ylabel)
            ax.grid(True, alpha=0.3)
            if col_idx == 0 and row_idx == 0:
                ax.legend(loc="lower right", fontsize=7)
    ci_label = f"bootstrap 95% CI, {N_BOOT} resamples" if use_bootstrap else "95% CI (1.96 x SEM)"
    fig.suptitle(f"Simulation learning curves -- LOO\n"
                 f"(shaded regions = {ci_label})",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig(output_dir / "learning_curves.png", dpi=150, bbox_inches="tight")
    plt.close()


def plot_loo_comparison(df, output_dir):
    """LOO accuracy comparison — same format as pilot's pilot_results.png.
    Directly reproducible from experimental data (no ground-truth needed).

    Panel 1: Per-user LOO accuracy advantage (LLM projection - random)
    Panel 2: Final-T LOO accuracy by fit type and condition
    """
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # --- Panel 1: Accuracy advantage (proj - random) per condition ---
    ax = axes[0]
    cond_labels, cond_means, cond_ci_lo, cond_ci_hi, cond_pvals = [], [], [], [], []
    cond_colors = ["#1f77b4", "#ff7f0e", "#2ca02c"]
    for cond in CONDITIONS:
        cdf = df[df["condition"] == cond]
        if cdf.empty:
            continue
        rand_acc = cdf["test_acc_random_projection"].values
        proj_acc = cdf["test_acc_projection_only"].values
        diff = proj_acc - rand_acc
        m = diff.mean()
        sem = diff.std() / np.sqrt(len(diff))
        cond_labels.append(cond.replace("_", "\n"))
        cond_means.append(m)
        cond_ci_lo.append(m - 1.96 * sem)
        cond_ci_hi.append(m + 1.96 * sem)
        try:
            _, p = wilcoxon(diff, zero_method="zsplit")
        except ValueError:
            p = float("nan")
        cond_pvals.append(p)

    if cond_labels:
        x = np.arange(len(cond_labels))
        means = np.array(cond_means)
        ci_lo = np.array(cond_ci_lo)
        ci_hi = np.array(cond_ci_hi)
        yerr = np.array([means - ci_lo, ci_hi - means])
        ax.bar(x, means, width=0.5, color=cond_colors[:len(x)],
               alpha=0.7, edgecolor="black", linewidth=0.5)
        ax.errorbar(x, means, yerr=yerr, fmt="none", ecolor="black",
                    capsize=6, capthick=1.5, linewidth=1.5)
        ax.axhline(0, color="gray", linestyle="--", alpha=0.5, label="no advantage")
        ax.set_xticks(x)
        ax.set_xticklabels(cond_labels)
        ax.set_ylabel("LOO accuracy advantage\n(LLM projection - random)")
        ax.set_title("LLM basis advantage\n(mean + 95% CI)", fontweight="bold")
        ax.legend(loc="lower right", fontsize=8)
        for i, p in enumerate(cond_pvals):
            sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"
            y_pos = max(ci_hi[i], 0) + 0.01
            ax.text(i, y_pos, f"{sig}\np={p:.3f}", ha="center", fontsize=8)

    # --- Panel 2: LOO accuracy by fit type (grouped bars) ---
    ax = axes[1]
    width = 0.25
    conds_present = [c for c in CONDITIONS if c in df["condition"].unique()]
    x = np.arange(len(conds_present))
    for i, fit in enumerate(FIT_TYPES):
        means, cis = [], []
        for cond in conds_present:
            cdf = df[df["condition"] == cond]
            vals = cdf[f"test_acc_{fit}"].values
            means.append(vals.mean())
            cis.append(1.96 * vals.std() / np.sqrt(len(vals)))
        ax.bar(x + (i - 1) * width, means, width, yerr=cis,
               color=FIT_STYLE[fit]["color"], label=FIT_STYLE[fit]["label"],
               alpha=0.7, edgecolor="black", linewidth=0.5, capsize=4)
    ax.axhline(0.5, color="gray", linestyle="--", alpha=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels([c.replace("_", "\n") for c in conds_present])
    ax.set_ylabel("LOO accuracy")
    ax.set_title("Final-T LOO accuracy by method\n(mean + 95% CI)", fontweight="bold")
    ax.legend(loc="lower right", fontsize=7)
    ax.grid(True, alpha=0.2, axis="y")

    fig.suptitle("Simulation -- LOO comparison (reproducible from experimental data)",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig(output_dir / "loo_comparison.png", dpi=150, bbox_inches="tight")
    plt.close()


def plot_results(df, output_dir):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # --- Panel 1: Predicted DV as mean + 95% CI per condition ---
    ax = axes[0]
    cond_labels = []
    cond_means = []
    cond_ci_lo = []
    cond_ci_hi = []
    cond_colors = ["#1f77b4", "#ff7f0e", "#2ca02c"]
    for cond in CONDITIONS:
        cdf = df[df["condition"] == cond]
        if cdf.empty:
            continue
        vals = cdf["rating_partial_vs_standard"].values
        m = vals.mean()
        sem = vals.std() / np.sqrt(len(vals))
        cond_labels.append(cond.replace("_", "\n"))
        cond_means.append(m)
        cond_ci_lo.append(m - 1.96 * sem)
        cond_ci_hi.append(m + 1.96 * sem)
    x = np.arange(len(cond_labels))
    cond_means = np.array(cond_means)
    cond_ci_lo = np.array(cond_ci_lo)
    cond_ci_hi = np.array(cond_ci_hi)
    yerr = np.array([cond_means - cond_ci_lo, cond_ci_hi - cond_means])
    bars = ax.bar(x, cond_means, width=0.5, color=cond_colors[:len(x)],
                  alpha=0.7, edgecolor="black", linewidth=0.5)
    ax.errorbar(x, cond_means, yerr=yerr, fmt="none", ecolor="black",
                capsize=6, capthick=1.5, linewidth=1.5)
    ax.axhline(0.5, color="gray", linestyle="--", alpha=0.5, label="no preference")
    ax.set_xticks(x)
    ax.set_xticklabels(cond_labels)
    ax.set_ylabel("P(LLM summary preferred)")
    ax.set_title("Predicted experimental DV\n(mean + 95% CI)", fontweight="bold")
    ax.set_ylim(0, 1)
    ax.legend(loc="lower right", fontsize=8)
    # Add significance annotations
    base = df[df["condition"] == "choice_only"]["rating_partial_vs_standard"].values
    y_max = max(cond_ci_hi) + 0.03
    for i, cond in enumerate(CONDITIONS[1:], 1):
        other = df[df["condition"] == cond]["rating_partial_vs_standard"].values
        if len(other) == 0 or len(base) == 0:
            continue
        n = min(len(base), len(other))
        try:
            _, p = wilcoxon(other[:n], base[:n])
        except ValueError:
            p = float("nan")
        if p < 0.001:
            sig_label = "***"
        elif p < 0.01:
            sig_label = "**"
        elif p < 0.05:
            sig_label = "*"
        else:
            sig_label = "ns"
        bar_y = y_max + 0.04 * (i - 1)
        ax.plot([0, i], [bar_y, bar_y], color="black", linewidth=1)
        ax.text((0 + i) / 2, bar_y + 0.01, f"{sig_label} (p={p:.3f})",
                ha="center", fontsize=8)

    # Quality decomposition: spearman per fit
    ax = axes[1]
    width = 0.35
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

    # Select top-D dimensions if --n-dims is set
    if args.n_dims is not None and args.n_dims < K:
        # Rank by variance of item projections: Var(v_k^T (phi - mu))
        # This matches the "variance_captured" metric from evaluate_basis.py
        centered = embeddings - embeddings.mean(axis=0)
        proj_var = np.var(centered @ V.T, axis=0)  # (K,)
        top_idx = np.argsort(-proj_var)[:args.n_dims]
        top_idx.sort()  # preserve original ordering
        V = V[top_idx]
        G = V @ V.T
        bt_scores = bt_scores[:, top_idx]
        dim_names = [dim_names[i] for i in top_idx]
        K = args.n_dims
        print(f"  Selected top {K} dimensions (by variance of item projections)")
        print(f"  Gram matrix condition number: {np.linalg.cond(G):.1f}")

    print(f"  Options: {N}, d: {d}, K: {K}")

    # Generate random orthonormal basis for the baseline (same D as LLM basis)
    rng_rand = np.random.default_rng(args.seed + 777)
    V_rand = rng_rand.standard_normal((K, d))
    V_rand, _ = np.linalg.qr(V_rand.T)  # (d, K) orthonormal columns
    V_rand = V_rand[:, :K].T              # (K, d) orthonormal rows
    G_rand = V_rand @ V_rand.T            # = I_K (orthonormal)
    print(f"  Random baseline: {K} orthonormal directions (G_rand = I)")

    # Build per-dim quintile boundaries from the embedding pool's projections.
    # We use V·(φ - μ) since the post-eval categorization works on signed
    # value_if_chosen scores symmetric around 0.
    centered = embeddings - mu[np.newaxis, :]
    pool_proj = centered @ V.T  # (N, K)
    quintile_bounds = perdim_quintile_boundaries(pool_proj, n_cats=len(DEFAULT_MULTS))

    # Bin midpoints for gradient replacement must come from DELTA projections
    # (same scale as U_tk = (φ_a - φ_b)⊤v_k), not option-level projections.
    # Sample random pairs to build the delta-projection distribution.
    _rng_mp = np.random.default_rng(args.seed + 999)
    _n_mp_pairs = min(2000, N * (N - 1) // 2)
    _mp_a = _rng_mp.integers(0, N, size=_n_mp_pairs)
    _mp_b = _rng_mp.integers(0, N, size=_n_mp_pairs)
    _mask = _mp_a == _mp_b
    while _mask.any():
        _mp_b[_mask] = _rng_mp.integers(0, N, size=int(_mask.sum()))
        _mask = _mp_a == _mp_b
    _delta_proj = (embeddings[_mp_a] - embeddings[_mp_b]) @ V.T  # (_n_mp_pairs, K)
    bin_midpoints = perdim_bin_midpoints(_delta_proj, n_cats=len(DEFAULT_MULTS))
    print(f"  Bin midpoints scale: option-level range [{pool_proj.min():.2f}, {pool_proj.max():.2f}], "
          f"delta-level range [{_delta_proj.min():.2f}, {_delta_proj.max():.2f}]")

    print("Generating synthetic users...")
    users = generate_users(args.num_users, K, rng,
                           sparsity=args.user_sparsity,
                           mag_min=args.user_mag_min,
                           mag_max=args.user_mag_max)

    predefined_pairs = None
    if args.predefined_pairs:
        predefined_pairs = load_predefined_pairs(args.predefined_pairs, option_ids)
        need = args.num_trials
        if len(predefined_pairs) < need:
            raise ValueError(f"predefined-pairs pool has only {len(predefined_pairs)} "
                             f"pairs, but need {need} = num_trials.")

    mults = DEFAULT_MULTS * args.multiplier_scale
    ctx = {
        "embeddings": embeddings, "bt_scores": bt_scores,
        "V": V, "G": G, "mu": mu,
        "V_rand": V_rand, "G_rand": G_rand,
        "quintile_bounds": quintile_bounds, "bin_midpoints": bin_midpoints, "mults": mults,
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
        plot_loo_comparison(df, output_dir)
        print("Saved loo_comparison.png")
    except Exception as e:
        print(f"Warning: could not save loo_comparison.png: {e}")
    try:
        plot_learning_curves(curves_df, output_dir,
                             use_bootstrap=args.bootstrap,
                             cv_folds=args.cv_folds)
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
    p.add_argument("--top-k-inferences", type=int, default=3,
                   help="Number of dims visible per trial in inference conditions.")
    p.add_argument("--n-dimensions-shown", type=int, default=10,
                   help="Top-N dims shown in the post-experiment summary.")
    p.add_argument("--participant-noise", type=float, default=0.10,
                   help="Probability the user picks an adjacent (wrong) "
                        "category on a given visible dim.")
    p.add_argument("--beta", type=float, default=2.0,
                   help="Choice-noise temperature (BTL).")
    p.add_argument("--lambda-standard", type=float, default=0.01,
                   help="L2 regularization for the kernel-logistic fit.")
    p.add_argument("--lambda-partial", type=float, default=0.01,
                   help="L2 regularization for the K-dim primal fit "
                        "(both projected and partial-with-feedback). "
                        "Default 0.01 — structural regularization from "
                        "the projection does the heavy lifting.")
    p.add_argument("--feedback-alpha", type=float, default=2.0,
                   help="Feedback prior strength. mu_prior = alpha. "
                        "Default 2.0. Used as fallback when condition-specific "
                        "alphas (--feedback-alpha-affirm, "
                        "--feedback-alpha-categories) are not set. "
                        "Calibrated via simulation sweep on dailydilemmas "
                        "(LOO-optimal for inference_affirm; high-effect zone "
                        "for inference_categories).")
    p.add_argument("--feedback-alpha-affirm", type=float, default=None,
                   help="Feedback prior strength for inference_affirm. "
                        "Defaults to --feedback-alpha. Affirm carries 1 bit per "
                        "dim (sign), so a smaller value (e.g., 0.25-0.5) is "
                        "often optimal vs categories' richer signal.")
    p.add_argument("--feedback-alpha-categories", type=float, default=None,
                   help="Feedback prior strength for inference_categories. "
                        "Defaults to --feedback-alpha.")
    p.add_argument("--gamma", type=float, default=1.0,
                   help="Projection degree γ ∈ [0, 1]. Blends kernel and "
                        "projected logits: (1-γ)*kernel + γ*projected. "
                        "γ=0 is pure kernel, γ=1 is pure projection. Default 1.0.")
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
    p.add_argument("--n-dims", type=int, default=None,
                   help="Use only the top-D directions (by norm). "
                        "Default: use all K dimensions.")
    p.add_argument("--cv-folds", type=int, default=5,
                   help="Number of CV folds for learning curve evaluation. "
                        "Default 5 (matching pilot calibration regime).")
    p.add_argument("--bootstrap", action="store_true",
                   help="Use bootstrap 95%% CIs in learning curve plots. "
                        "Default uses normal-approx (1.96 * SEM).")

    p.add_argument("--user-sparsity", type=float, default=0.3,
                   help="Fraction of dims that are active per user. "
                        "Default 0.3 (3 of 10 dims active) approximates "
                        "real participants. Try 0.5 to test sensitivity.")
    p.add_argument("--user-mag-min", type=float, default=1.5,
                   help="Minimum magnitude of active w* coefficients. "
                        "Default 1.5. Together with --user-mag-max, controls "
                        "choice signal strength.")
    p.add_argument("--user-mag-max", type=float, default=3.0,
                   help="Maximum magnitude of active w* coefficients. "
                        "Default 3.0. Higher = more decisive synthetic users.")

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
