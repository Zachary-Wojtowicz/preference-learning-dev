"""
Simulated Preference Learning Experiment (revamped to match the 3 final
experimental conditions).

Goal: predict whether the planned human experiment is likely to detect an
effect. Mirrors the post-experiment forced-choice — *will participants
prefer the K-dim partial-fit summary over the unrestricted standard-fit
summary?* — rather than measuring online learning curves.

Three conditions:
  1. choice_only            — binary choice, no per-dim feedback.
                              standard fit vs. projected fit (β₀ = 0).
  2. inference_affirm       — top-K=5 visible dims, Affirm/Moderate/Remove.
                              standard vs. partial fit (β₀ = G⁻¹·mean(λ_t)).
  3. inference_categories   — top-K=5 visible dims, 5-category picker.
                              standard vs. partial fit (β₀ from λ_t).

Pipeline per simulated user × condition:
  1. Sample T trials of (a, b); user chooses by their true K-vec w*.
  2. For inference conditions: pick top-5 dims by |V·φ_chosen|, compute
     model's pre-selected category via per-dim quintile bucketing of the
     trial-pool projections, simulate the participant's per-dim feedback
     (with calibrated noise) → λ_t (K-vec, 0 for invisible/no-effect).
  3. End-of-experiment batch MAP fits via Newton+L2 (mirrors web-interface
     post-eval code path):
        standard       — kernel logistic in dual form, full d-dim kernel
        partial/proj   — K-dim primal logistic, G-shape prior centered at β₀
  4. Score each fit: Spearman(scores_K, w*) + top-N sign-agreement.
  5. Predict participant rating: σ(τ · (Q_other − Q_standard)).

Aggregate: per-condition mean rating, paired Wilcoxon vs. choice_only.
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
    G_reg = G + 1e-6 * np.eye(G.shape[0])
    G_inv = np.linalg.inv(G_reg)

    print(f"  Gram matrix condition number: {np.linalg.cond(G):.1f}")
    print(f"  Max inter-dimension correlation: {np.abs(G - np.eye(G.shape[0])).max():.3f}")

    return embeddings, bt_scores, V, G, G_inv, mu, option_ids, dim_names


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


def compute_beta0(lam_traj, visible_traj, G_inv):
    """β₀ = G⁻¹ · mean_t(λ_t), averaged over visible-trials per dim;
    0 for dims never visible."""
    K = lam_traj.shape[1]
    avg = np.zeros(K)
    for k in range(K):
        n_visible = visible_traj[:, k].sum()
        if n_visible > 0:
            avg[k] = lam_traj[visible_traj[:, k], k].mean()
    return G_inv @ avg


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
    G_inv = ctx["G_inv"]
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

    # Sample one shared trial pool so all conditions see the same pairs.
    trial_pairs = []
    while len(trial_pairs) < args.num_trials:
        a, b = rng.choice(N, size=2, replace=False)
        trial_pairs.append((int(a), int(b)))

    # Pre-compute test pairs + choices once per user (held-out accuracy).
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

    for cond in CONDITIONS:
        # Per-trial accumulators
        deltas = np.zeros((args.num_trials, d))
        ys = np.zeros(args.num_trials, dtype=int)
        lam_traj = np.zeros((args.num_trials, K))
        visible_traj = np.zeros((args.num_trials, K), dtype=bool)
        action_log = []  # for diagnostics

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
                # No per-dim signal collected.
                continue

            # Top-K visible dims by |value_if_chosen|
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

        # Build kernel + projection matrices
        D = deltas @ deltas.T  # (T, T) full d-dim kernel
        U = deltas @ V.T       # (T, K) projections

        # Standard fit (kernel logistic, dual form)
        alpha = fit_standard_kernel(D, ys.astype(float), args.lambda_standard)
        scores_std = U.T @ alpha  # (K,)

        # Partial / projected fit (K-dim primal with prior)
        if cond == "choice_only":
            beta0 = np.zeros(K)
            other_label = "projected"
        else:
            beta0 = compute_beta0(lam_traj, visible_traj, G_inv)
            other_label = "partial"
        beta = fit_partial_primal(U, ys.astype(float), G, beta0, args.lambda_partial)
        scores_other = G @ beta  # (K,)

        # Summary quality vs ground truth
        q_std = summary_quality(scores_std, w_star, args.n_dimensions_shown)
        q_other = summary_quality(scores_other, w_star, args.n_dimensions_shown)
        rating = predicted_rating(q_other["combined"], q_std["combined"],
                                  args.rating_temperature)

        # Held-out test set accuracy (for diagnostics)
        # Standard: theta = sum_t alpha_t delta_t → test_logit = sum_t alpha_t (delta_test · delta_t)
        cross_kernel = test_delta @ deltas.T  # (M, T)
        test_logit_std = cross_kernel @ alpha
        test_acc_std = ((test_logit_std > 0).astype(int) == test_choices).mean()

        # Partial: theta_K = beta in K-space (for dim-aligned utility); test_logit = U_test · beta
        test_logit_other = test_U @ beta
        test_acc_other = ((test_logit_other > 0).astype(int) == test_choices).mean()

        results["conditions"][cond] = {
            "other_label": other_label,
            "quality_standard": q_std,
            "quality_other": q_other,
            "predicted_rating_other_vs_standard": rating,
            "test_acc_standard": float(test_acc_std),
            "test_acc_other": float(test_acc_other),
            "n_trials": int(args.num_trials),
            "actions": action_log,
        }

    return results


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def aggregate_results(per_user_results):
    """Roll up per-user results into condition-level summary rows."""
    rows = []
    for user_res in per_user_results:
        uid = user_res["user_id"]
        for cond, res in user_res["conditions"].items():
            rows.append({
                "user_id": uid,
                "condition": cond,
                "other_label": res["other_label"],
                "spearman_standard": res["quality_standard"]["spearman"],
                "spearman_other": res["quality_other"]["spearman"],
                "topn_sign_standard": res["quality_standard"]["top_n_sign_agreement"],
                "topn_sign_other": res["quality_other"]["top_n_sign_agreement"],
                "topn_overlap_standard": res["quality_standard"]["top_n_overlap"],
                "topn_overlap_other": res["quality_other"]["top_n_overlap"],
                "combined_standard": res["quality_standard"]["combined"],
                "combined_other": res["quality_other"]["combined"],
                "rating_other_vs_standard": res["predicted_rating_other_vs_standard"],
                "test_acc_standard": res["test_acc_standard"],
                "test_acc_other": res["test_acc_other"],
            })
    return pd.DataFrame(rows)


def write_summary(df, args, output_dir, dim_names):
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

    lines.append("## Predicted Rating (P[other > standard])\n")
    lines.append("Probability the simulated participant prefers the K-dim "
                 "(partial/projected) summary over the standard summary. "
                 "0.5 = no effect; >0.5 = K-dim preferred.\n")
    lines.append("| Condition | Other-fit type | Mean rating | SD | Pct > 0.5 |")
    lines.append("|-----------|----------------|-------------|----|-----------|")
    for cond in CONDITIONS:
        cdf = df[df["condition"] == cond]
        if cdf.empty:
            continue
        m = cdf["rating_other_vs_standard"].mean()
        sd = cdf["rating_other_vs_standard"].std()
        pct = (cdf["rating_other_vs_standard"] > 0.5).mean() * 100
        other = cdf["other_label"].iloc[0]
        lines.append(f"| {cond} | {other} | {m:.3f} | {sd:.3f} | {pct:.0f}% |")
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
        for which in ["standard", "other"]:
            cells = [cond, which if which == "standard" else cdf["other_label"].iloc[0]]
            for m in metrics:
                col = f"{m}_{which}"
                cells.append(f"{cdf[col].mean():.3f}")
            lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    lines.append("## Held-Out Choice Accuracy (diagnostic)\n")
    lines.append("| Condition | Standard fit | Other fit |")
    lines.append("|-----------|--------------|-----------|")
    for cond in CONDITIONS:
        cdf = df[df["condition"] == cond]
        if cdf.empty:
            continue
        lines.append(f"| {cond} | {cdf['test_acc_standard'].mean():.3f} | "
                     f"{cdf['test_acc_other'].mean():.3f} |")
    lines.append("")

    lines.append("## Significance Tests (paired Wilcoxon)\n")
    lines.append("Tests whether the predicted rating is reliably > 0.5 within each "
                 "condition (i.e., the K-dim summary wins) and whether inference "
                 "conditions differ from choice_only.\n")
    lines.append("| Comparison | n | mean | Wilcoxon p |")
    lines.append("|------------|---|------|------------|")
    for cond in CONDITIONS:
        cdf = df[df["condition"] == cond]
        if cdf.empty:
            continue
        ratings = cdf["rating_other_vs_standard"].values
        try:
            stat, p = wilcoxon(ratings - 0.5, zero_method="zsplit")
        except ValueError:
            p = float("nan")
        lines.append(f"| {cond} vs 0.5 | {len(ratings)} | {ratings.mean():.3f} | {p:.4f} |")

    base = df[df["condition"] == "choice_only"]["rating_other_vs_standard"].values
    for cond in ["inference_affirm", "inference_categories"]:
        other = df[df["condition"] == cond]["rating_other_vs_standard"].values
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

    lines.append("## Go/No-Go Read\n")
    pct_inf_aff = (df[df["condition"] == "inference_affirm"]
                   ["rating_other_vs_standard"] > 0.5).mean() * 100
    pct_inf_cat = (df[df["condition"] == "inference_categories"]
                   ["rating_other_vs_standard"] > 0.5).mean() * 100
    pct_choice = (df[df["condition"] == "choice_only"]
                  ["rating_other_vs_standard"] > 0.5).mean() * 100
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


def plot_results(df, output_dir):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # Predicted rating distribution per condition
    ax = axes[0]
    data = []
    labels = []
    for cond in CONDITIONS:
        cdf = df[df["condition"] == cond]
        if not cdf.empty:
            data.append(cdf["rating_other_vs_standard"].values)
            labels.append(cond.replace("_", "\n"))
    if data:
        ax.boxplot(data, labels=labels, showmeans=True)
        ax.axhline(0.5, color="gray", linestyle="--", alpha=0.5, label="no preference")
        ax.set_ylabel("P(K-dim summary preferred over standard)")
        ax.set_title("Predicted experimental DV", fontweight="bold")
        ax.legend(loc="lower right")
        ax.set_ylim(0, 1)

    # Quality decomposition
    ax = axes[1]
    metrics = ["spearman_standard", "spearman_other"]
    width = 0.35
    x = np.arange(len(CONDITIONS))
    for i, m in enumerate(metrics):
        means = []
        for cond in CONDITIONS:
            cdf = df[df["condition"] == cond]
            means.append(cdf[m].mean() if not cdf.empty else 0)
        ax.bar(x + (i - 0.5) * width, means, width,
               label="standard fit" if "standard" in m else "K-dim fit")
    ax.set_xticks(x)
    ax.set_xticklabels([c.replace("_", "\n") for c in CONDITIONS])
    ax.set_ylabel("Spearman(scores, w*)")
    ax.set_title("Summary quality (rank corr. with ground truth)", fontweight="bold")
    ax.legend()
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
    embeddings, bt_scores, V, G, G_inv, mu, option_ids, dim_names = load_data(
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

    ctx = {
        "embeddings": embeddings, "bt_scores": bt_scores,
        "V": V, "G": G, "G_inv": G_inv, "mu": mu,
        "quintile_bounds": quintile_bounds, "mults": DEFAULT_MULTS,
    }

    per_user_results = []
    print("Running simulation...")
    for i, user in enumerate(users):
        per_user_results.append(simulate_one_user(user, ctx, args, rng))
        if (i + 1) % 10 == 0 or i == len(users) - 1:
            print(f"  user {i + 1}/{len(users)} done")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = aggregate_results(per_user_results)
    df.to_csv(output_dir / "per_user_per_condition.csv", index=False)
    print(f"Saved per_user_per_condition.csv ({len(df)} rows)")

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

    write_summary(df, args, output_dir, dim_names)
    print("Saved summary.md")
    try:
        plot_results(df, output_dir)
        print("Saved predicted_dv.png")
    except Exception as e:
        print(f"Warning: could not save plot: {e}")


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
    p.add_argument("--lambda-partial", type=float, default=1.0,
                   help="L2 regularization for the K-dim primal fit.")
    p.add_argument("--rating-temperature", type=float, default=5.0,
                   help="Temperature for sigmoid mapping quality gap to "
                        "predicted rating.")
    p.add_argument("--seed", type=int, default=42)

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
