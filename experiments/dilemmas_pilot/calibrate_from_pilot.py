"""
Calibrate (lambda_partial, multiplier_scale, feedback_alpha) using the pilot
data via within-participant cross-validation, and head-to-head test the
modified projection method (partial fit on Ũ = Λ⊙U) against the standard
kernel-logistic baseline.

For each pilot participant we observe 20 (option_a_id, option_b_id, chosen,
visible_dims, multipliers) rows. We treat each participant as their own
ground truth: on each CV fold, refit BOTH the standard-kernel model on the
delta-Gram and the partial K-dim primal on the (α, scale, λ)-parameterized
design matrix; score both on the held-out trials.

Two questions answered:
  (1) Does the modified projection beat the standard baseline? — paired
      Wilcoxon test on Δ-LL across participants.
  (2) What are the best (λ, scale, α)? — max mean held-out LL.

CV scheme:
  - 5-fold (default) over each participant's 20 trials, stratified by chosen
    side to avoid degenerate folds.
  - Per fold × per (λ, s, α): fit standard kernel + partial primal on train,
    score both on test.

Outputs (in --output-dir):
  - cv_results.csv: one row per (participant × fold × grid-point), with both
    std and partial metrics.
  - cv_summary.csv: aggregated over folds and participants, per condition
    × grid-point.
  - calibration_report.md: head-to-head + best-params per condition.

Usage:
  python experiments/pilot/calibrate_from_pilot.py \
    --pilot-csv experiments/pilot/data.csv \
    --embeddings-parquet datasets/dailydilemmas/selected_actions-embedded.parquet \
    --directions method_directions/outputs/dailydilemmas/directions.npz \
    --option-id-column action_id \
    --output-dir experiments/pilot/calibration

Note: choice_only participants have no feedback, so the "partial" fit
collapses to the projected fit (Ũ = U); for those participants we're
testing whether the K-dim projection alone beats the kernel baseline.
"""

import argparse
import itertools
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pilot-csv", required=True)
    p.add_argument("--embeddings-parquet", required=True)
    p.add_argument("--directions", required=True)
    p.add_argument("--option-id-column", default="action_id")
    p.add_argument("--output-dir", required=True)

    p.add_argument("--n-folds", type=int, default=5)
    p.add_argument("--lambda-grid", default="0.001,0.005,0.01,0.025,0.05,0.1,0.25,0.5,1.0")
    p.add_argument("--gamma-grid", default="0.0,0.25,0.5,0.75,1.0",
                   help="Projection degree γ \in [0,1]. γ=0 is pure kernel "
                        "(full d-dim), γ=1 is pure K-dim projection.")
    p.add_argument("--alpha-grid", default="0.0,0.25,0.5,0.75,1.0",
                   help="Feedback strength α \in [0,1]. α=0 ignores feedback, "
                        "α=1 is full midpoint replacement on changed dims.")
    p.add_argument("--lambda-standard", type=float, default=0.01,
                   help="Fixed L2 regularization for the kernel-logistic "
                        "baseline. Matches the experiment's value of 0.01.")
    p.add_argument("--n-dims", type=int, default=None,
                   help="Use only the top-D directions (by norm). "
                        "Default: use all K dimensions.")
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


# -- shared with run_simulation; reproduced here so this script is standalone --

def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -50, 50)))


def perdim_bin_midpoints(values_pool, n_cats=5):
    """Bin midpoints for each dimension. Returns (n_cats, K)."""
    T, K = values_pool.shape
    midpoint_qs = np.array([(2 * i + 1) / (2 * n_cats) for i in range(n_cats)])
    midpoints = np.zeros((n_cats, K))
    for k in range(K):
        v = values_pool[:, k]
        symm = np.concatenate([v, -v])
        midpoints[:, k] = np.quantile(symm, midpoint_qs)
    return midpoints



def fit_feedback_gradient(U, U_adj, y, G, lam, max_iter=15, tol=1e-7):
    """K-dim primal logistic where predictions use raw U but gradients
    use feedback-adjusted U_adj. No train/test scale mismatch."""
    T, K = U.shape
    beta = np.zeros(K)
    for _ in range(max_iter):
        u = U @ beta                       # predict on RAW U
        p = sigmoid(u)
        w = p * (1 - p)
        grad = U_adj.T @ (p - y) + lam * G @ beta   # gradient on ADJUSTED
        H = U.T @ (w[:, None] * U) + lam * G         # Hessian on RAW
        try:
            d_beta = np.linalg.solve(H, -grad)
        except np.linalg.LinAlgError:
            break
        beta = beta + d_beta
        if np.max(np.abs(d_beta)) < tol:
            break
    return beta


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


def heldout_ll(logits, y):
    p = sigmoid(logits)
    eps = 1e-10
    return float(np.mean(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps)))


# ---------------------------------------------------------------------------

def load_pilot_participants(pilot_csv):
    """Load every participant's responses + condition label. Drops rows with
    no parsed experiment_data or no feedback trials."""
    df = pd.read_csv(pilot_csv).iloc[2:].reset_index(drop=True)
    parts = []
    for _, row in df.iterrows():
        ed_raw = row.get("experiment_data")
        if not isinstance(ed_raw, str):
            continue
        try:
            ed = json.loads(ed_raw)
        except json.JSONDecodeError:
            continue
        responses = ed.get("responses") or []
        if not responses:
            continue
        parts.append({
            "qualtrics_id": row["ResponseId"],
            "condition": row.get("condition"),
            "domain": row.get("domain"),
            "responses": responses,
        })
    return parts


def build_per_trial_arrays(participant, embeddings, V, oid_to_idx, K,
                           bin_midpoints=None, cat_keys=None):
    """For one participant, build (deltas, U, raw_lam, visible_mask, actions, y).

    raw_lam[t,k] is the midpoint for the participant's selected category
    (for dims where they changed), or NaN (for unchanged/affirmed dims).
    0.0 for removed dims.
    actions[t,k] is one of: '', 'none', 'affirm', 'remove', 'modify', 'moderate'.
    visible_mask[t,k] is True for visible dims.
    """
    resp = participant["responses"]
    T = len(resp)
    d = embeddings.shape[1]
    deltas = np.zeros((T, d))
    raw_lam = np.full((T, K), np.nan)  # NaN = passthrough marker
    visible_mask = np.zeros((T, K), dtype=bool)
    actions = np.full((T, K), '', dtype=object)
    y = np.zeros(T, dtype=float)
    for t, r in enumerate(resp):
        oa = oid_to_idx.get(str(r["option_a_id"]))
        ob = oid_to_idx.get(str(r["option_b_id"]))
        if oa is None or ob is None:
            raise KeyError(f"Unknown option ids: {r['option_a_id']}, {r['option_b_id']}")
        deltas[t] = embeddings[oa] - embeddings[ob]
        y[t] = 1.0 if r["chosen"] == "a" else 0.0
        for dim_str, info in (r.get("inference_values") or {}).items():
            k = int(dim_str.split("_")[1]) - 1
            if not (0 <= k < K):
                continue
            visible_mask[t, k] = True
            action = info.get("action", "none")
            actions[t, k] = action
            cat_key = info.get("category", "indifferent")
            if action == "remove":
                raw_lam[t, k] = 0.0  # zero out this dimension
            elif action in ("affirm", "moderate"):
                # Affirm (or old moderate): store raw delta projection
                raw_lam[t, k] = (deltas[t] @ V[k])
            elif action == "modify":
                # Category was changed -- use midpoint
                if bin_midpoints is not None and cat_keys is not None and cat_key in cat_keys:
                    cat_idx = cat_keys.index(cat_key)
                    raw_lam[t, k] = bin_midpoints[cat_idx, k]
                else:
                    raw_lam[t, k] = float(info.get("multiplier", 0.0))
            elif action == "none":
                # Confirmed default category -- store midpoint for ALL visible dims
                if bin_midpoints is not None and cat_keys is not None and cat_key in cat_keys:
                    cat_idx = cat_keys.index(cat_key)
                    raw_lam[t, k] = bin_midpoints[cat_idx, k]
                else:
                    raw_lam[t, k] = float(info.get("multiplier", 0.0))
            # else: unknown action -> stays NaN
    U = deltas @ V.T  # (T, K)
    return deltas, U, raw_lam, visible_mask, actions, y


def cv_one_participant(deltas, U, raw_lam, visible_mask, y, G,
                        lam_p, gamma, alpha, lam_s, n_folds, seed):
    """Stratified K-fold CV for one participant.

    Fits BOTH the standard kernel-logistic baseline and the K-dim primal
    (with feedback-adjusted gradient) on each train fold, then blends
    their test logits:

        logit_test = (1 − γ) · logit_std + γ · logit_proj

    γ=0 is pure kernel, γ=1 is pure K-dim projection.
    α controls feedback strength within the K-dim fit.
    """
    T = len(y)
    if T < 2 or len(np.unique(y)) < 2:
        return []
    n_min = int(min(np.bincount(y.astype(int))))
    if n_min < 2:
        return []
    n_splits = min(n_folds, n_min)
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)

    # Pre-compute the full delta-Gram once; we'll slice per fold.
    D_full = deltas @ deltas.T  # (T, T)

    # Build Ũ once outside the fold loop.
    # Passthrough (NaN in raw_lam): U_adj = U  (affirm / no-change)
    # Replace (finite in raw_lam): U_adj = (1-α)*U + α*midpoint
    #   — this covers both 'modify'/'moderate' (midpoint > 0 or < 0)
    #     and 'remove' (midpoint = 0, so U_adj = (1-α)*U at α=1 → zero)
    U_adj = U.copy()
    has_replacement = np.isfinite(raw_lam)  # True where action was modify/moderate/remove
    if has_replacement.any():
        U_adj[has_replacement] = ((1.0 - alpha) * U[has_replacement]
                                  + alpha * raw_lam[has_replacement])

    rows = []
    for fold_idx, (train_idx, test_idx) in enumerate(
            skf.split(np.zeros(T), y.astype(int))):
        # Standard kernel fit in dual form: alpha ∈ ℝ^|train|, scored on test
        # via cross-Gram.
        D_train = D_full[np.ix_(train_idx, train_idx)]
        alpha_dual = fit_standard_kernel(D_train, y[train_idx], lam_s)
        D_cross = D_full[np.ix_(test_idx, train_idx)]
        logits_std = D_cross @ alpha_dual
        acc_std = float(((logits_std > 0).astype(float) == y[test_idx]).mean())
        ll_std = heldout_ll(logits_std, y[test_idx])

        # Partial K-dim primal: predictions on raw U, gradients on U_adj.
        beta = fit_feedback_gradient(U[train_idx], U_adj[train_idx],
                                     y[train_idx], G, lam_p)
        logits_part = U[test_idx] @ beta
        acc_part = float(((logits_part > 0).astype(float) == y[test_idx]).mean())
        ll_part = heldout_ll(logits_part, y[test_idx])

        # Blended logits: (1-γ)*kernel + γ*projected
        logits_blend = (1.0 - gamma) * logits_std + gamma * logits_part
        acc_blend = float(((logits_blend > 0).astype(float) == y[test_idx]).mean())
        ll_blend = heldout_ll(logits_blend, y[test_idx])

        rows.append({
            "fold": fold_idx, "n_test": int(len(test_idx)),
            "test_acc_std": acc_std, "test_ll_std": ll_std,
            "test_acc_part": acc_part, "test_ll_part": ll_part,
            "test_acc_blend": acc_blend, "test_ll_blend": ll_blend,
            "delta_ll": ll_blend - ll_std,
            "delta_acc": acc_blend - acc_std,
        })
    return rows


def _participant_means(df, group_cols, value_col):
    """Average over folds within a participant (so each participant's
    voice is one observation per group), then return the long-format frame."""
    return df.groupby(group_cols + ["qualtrics_id"])[value_col].mean().reset_index()


def write_report(df, summary, output_path, args, per_part):
    from scipy import stats as _stats

    lines = ["# Pilot Calibration Report", ""]
    lines.append(f"- pilot file: `{Path(args.pilot_csv).name}`")
    lines.append(f"- N participants used: {len(per_part)}")
    cond_counts = pd.Series([p["condition"] for p in per_part]).value_counts()
    lines.append(f"- by condition: {dict(cond_counts)}")
    lines.append(f"- {args.n_folds}-fold stratified CV per participant")
    lines.append(f"- λ_partial grid: {args.lambda_grid}")
    lines.append(f"- γ (projection degree) grid: {args.gamma_grid}")
    lines.append(f"- α (feedback strength) grid: {args.alpha_grid}")
    lines.append(f"- λ_standard (fixed): {args.lambda_standard}")
    lines.append("")

    lines.append("## How to read")
    lines.append("")
    lines.append("Two questions:")
    lines.append("")
    lines.append("1. **Does the modified projection method (partial fit on "
                  "Ũ = Λ⊙U) beat the standard kernel-logistic baseline?** — "
                  "head-to-head Wilcoxon test on Δ-LL across participants.")
    lines.append("2. **What are the best (λ, scale, α)?** — max held-out LL.")
    lines.append("")
    lines.append("CV is within-participant (5-fold stratified by chosen side). "
                  "Both fits are trained on each fold's train trials and scored "
                  "on the same held-out test trials, so the comparison is "
                  "perfectly paired at the participant × fold level.")
    lines.append("")

    # =====================================================================
    # PART 1 — Head-to-head test at the experiment's CURRENT settings:
    # λ_partial, α from the args grid that match what's deployed.
    # =====================================================================
    lines.append("## 1. Head-to-head: modified projection vs. standard kernel")
    lines.append("")
    lines.append("Per-condition Wilcoxon test on **per-participant mean Δ-LL** "
                  "(blend − standard). Δ > 0 means the blended model "
                  "predicted that participant's held-out choices better than the "
                  "kernel baseline. Tests evaluated at the deployed experiment "
                  "settings (λ_partial=0.05, γ=1.0, α=0.5) — the closest "
                  "grid point to those is reported.")
    lines.append("")

    # Find the closest grid point to the deployed defaults.
    def _closest(values, target):
        return min(values, key=lambda v: abs(v - target))
    grid_lams = sorted(df["lambda"].unique())
    grid_gammas = sorted(df["gamma"].unique())
    grid_alphas = sorted(df["alpha"].unique())
    deployed_lam = _closest(grid_lams, 0.05)
    deployed_gamma = _closest(grid_gammas, 1.0)
    deployed_alpha = _closest(grid_alphas, 0.5)
    lines.append(f"_Closest grid point to deployed defaults: λ={deployed_lam}, "
                  f"γ={deployed_gamma}, α={deployed_alpha}_")
    lines.append("")

    sub_at = df[(df["lambda"] == deployed_lam)
                & (df["gamma"] == deployed_gamma)
                & (df["alpha"] == deployed_alpha)]
    lines.append("| Condition | n | mean LL std | mean LL part | mean Δ-LL | Wilcoxon p (Δ vs 0) | mean Δ-acc |")
    lines.append("|---|---|---|---|---|---|---|")
    for cond in sorted(sub_at["condition"].unique()):
        cdf = sub_at[sub_at["condition"] == cond]
        per_p = cdf.groupby("qualtrics_id").agg(
            ll_std=("test_ll_std", "mean"),
            ll_part=("test_ll_part", "mean"),
            d_ll=("delta_ll", "mean"),
            d_acc=("delta_acc", "mean"),
        )
        if len(per_p) < 2:
            lines.append(f"| {cond} | {len(per_p)} | — | — | — | — | — |")
            continue
        try:
            stat, p = _stats.wilcoxon(per_p["d_ll"], zero_method="zsplit")
            p_str = f"{p:.3f}"
        except ValueError:
            p_str = "—"
        lines.append(f"| {cond} | {len(per_p)} | "
                      f"{per_p['ll_std'].mean():+.4f} | "
                      f"{per_p['ll_part'].mean():+.4f} | "
                      f"{per_p['d_ll'].mean():+.4f} | "
                      f"{p_str} | "
                      f"{per_p['d_acc'].mean():+.4f} |")
    lines.append("")

    # =====================================================================
    # PART 2 — Best parameters per condition.
    # =====================================================================
    lines.append("## 2. Best (λ, γ, α) per condition")
    lines.append("")
    lines.append("Sorted by mean held-out LL of the blended fit. For "
                  "`choice_only` participants there are no per-dim feedback "
                  "clicks, so the partial fit collapses to the projected fit "
                  "(Ũ = U) — α doesn't change anything in that cell.")
    lines.append("")

    for cond in sorted(summary["condition"].unique()):
        sub = summary[summary["condition"] == cond]
        if sub.empty:
            continue
        # Top-10 by blend LL
        top = sub.sort_values("test_ll_blend", ascending=False).head(10)
        # Best baseline (std) for this condition — independent of (λ, γ, α)
        ll_std = sub["test_ll_std"].iloc[0]  # constant within condition
        acc_std = sub["test_acc_std"].iloc[0]
        lines.append(f"### {cond} (n={int(sub['n_obs'].iloc[0]) // 5}, "
                      f"std baseline LL = {ll_std:+.4f}, acc = {acc_std:.3f})")
        lines.append("")
        lines.append("| rank | λ | γ | α | LL blend | Δ-LL | acc blend | Δ-acc |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for i, (_, r) in enumerate(top.iterrows(), 1):
            lines.append(f"| {i} | {r['lambda']:g} | {r['gamma']:g} | "
                          f"{r['alpha']:g} | {r['test_ll_blend']:+.4f} | "
                          f"{r['delta_ll']:+.4f} | "
                          f"{r['test_acc_blend']:.3f} | {r['delta_acc']:+.3f} |")
        lines.append("")

    # =====================================================================
    # PART 3 — Reference: chance and feedback on/off comparison
    # =====================================================================
    lines.append("## 3. Reference baselines")
    lines.append("")
    lines.append("- **Chance**: LL = ln(0.5) = −0.693, accuracy = 0.500")
    lines.append("- **α=0 rows** in the per-condition tables are the *projected* "
                  "fit (no feedback applied, just K-dim restriction). Compare "
                  "the best α>0 row to the best α=0 row within a condition to "
                  "see whether the feedback channel adds value on real human "
                  "data.")
    lines.append("")

    for cond in sorted(summary["condition"].unique()):
        sub = summary[summary["condition"] == cond]
        if sub.empty:
            continue
        if cond == "choice_only":
            continue  # α has no effect when no feedback exists
        no_fb = sub[sub["alpha"] == 0.0].sort_values("test_ll_blend", ascending=False).iloc[0]
        fb_on = sub[sub["alpha"] > 0.0].sort_values("test_ll_blend", ascending=False).iloc[0]
        delta = fb_on["test_ll_blend"] - no_fb["test_ll_blend"]
        lines.append(f"### {cond}")
        lines.append("")
        lines.append(f"  - Best α=0:   λ={no_fb['lambda']:g}, γ={no_fb['gamma']:g} "
                      f"→ LL = {no_fb['test_ll_blend']:+.4f}, acc = {no_fb['test_acc_blend']:.3f}")
        lines.append(f"  - Best α>0:   λ={fb_on['lambda']:g}, γ={fb_on['gamma']:g}, "
                      f"α={fb_on['alpha']:g} → LL = {fb_on['test_ll_blend']:+.4f}, "
                      f"acc = {fb_on['test_acc_blend']:.3f}")
        lines.append(f"  - **Δ LL (best feedback − best no-feedback): {delta:+.4f}** "
                      f"({'feedback helps' if delta > 0 else 'feedback hurts or no help'})")
        lines.append("")

    output_path.write_text("\n".join(lines) + "\n")


def plot_heatmaps(summary, output_dir):
    """Per-condition heatmap of blend LL over (λ, γ) at the best α."""
    for cond in sorted(summary["condition"].unique()):
        sub = summary[summary["condition"] == cond]
        if sub.empty:
            continue
        best_alpha = sub.groupby("alpha")["test_ll_blend"].mean().idxmax()
        sliced = sub[sub["alpha"] == best_alpha]
        g = sliced.pivot_table(index="lambda", columns="gamma",
                                values="test_ll_blend")
        if g.empty:
            continue
        fig, ax = plt.subplots(figsize=(6.5, 4.5))
        im = ax.imshow(g.values, aspect="auto", origin="lower", cmap="viridis")
        ax.set_xticks(range(len(g.columns)), [f"{c:g}" for c in g.columns])
        ax.set_yticks(range(len(g.index)), [f"{r:g}" for r in g.index])
        ax.set_xlabel("γ")
        ax.set_ylabel("λ")
        ax.set_title(f"{cond} · blend LL · best α={best_alpha:g}",
                     fontweight="bold")
        fig.colorbar(im, ax=ax)
        mean_v = float(np.nanmean(g.values))
        for i in range(g.shape[0]):
            for j in range(g.shape[1]):
                v = g.values[i, j]
                if np.isnan(v):
                    continue
                ax.text(j, i, f"{v:.3f}", ha="center", va="center",
                        color="white" if v < mean_v else "black", fontsize=8)
        plt.tight_layout()
        plt.savefig(output_dir / f"heatmap_{cond}_LL.png",
                    dpi=150, bbox_inches="tight")
        plt.close()


def parse_grid(s):
    return [float(x) for x in s.split(",") if x.strip()]


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading pilot...")
    parts = load_pilot_participants(args.pilot_csv)
    print(f"  found {len(parts)} inference_categories participants")

    print("Loading embeddings + directions...")
    parq = pd.read_parquet(args.embeddings_parquet)
    parq[args.option_id_column] = parq[args.option_id_column].astype(str)
    parq = parq.sort_values(args.option_id_column).reset_index(drop=True)
    option_ids = parq[args.option_id_column].tolist()
    embeddings = np.stack(parq["embedding"].apply(np.array).values).astype(np.float64)
    oid_to_idx = {oid: i for i, oid in enumerate(option_ids)}

    npz = np.load(args.directions)
    V_raw = npz["directions_raw"].astype(np.float64)
    norms = np.linalg.norm(V_raw, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    V = V_raw / norms
    K = V.shape[0]

    # Select top-D dimensions if --n-dims is set
    if args.n_dims is not None and args.n_dims < K:
        # Rank by variance of item projections: Var(v_k^T (phi - mu))
        centered = embeddings - embeddings.mean(axis=0)
        proj_var = np.var(centered @ V.T, axis=0)
        top_idx = np.argsort(-proj_var)[:args.n_dims]
        top_idx.sort()
        V = V[top_idx]
        K = args.n_dims
        print(f"  Selected top {K} dimensions (by variance of item projections)")

    G = V @ V.T
    print(f"  K={K}, N options={len(option_ids)}")

    # Compute per-dim bin midpoints from DELTA projections (same scale as
    # U_tk = (φ_a - φ_b)⊤v_k), not option-level projections.
    N = len(option_ids)
    _rng_mp = np.random.default_rng(args.seed + 999)
    _n_mp_pairs = min(2000, N * (N - 1) // 2)
    _mp_a = _rng_mp.integers(0, N, size=_n_mp_pairs)
    _mp_b = _rng_mp.integers(0, N, size=_n_mp_pairs)
    _mask = _mp_a == _mp_b
    while _mask.any():
        _mp_b[_mask] = _rng_mp.integers(0, N, size=int(_mask.sum()))
        _mask = _mp_a == _mp_b
    _delta_proj = (embeddings[_mp_a] - embeddings[_mp_b]) @ V.T
    bin_midpoints = perdim_bin_midpoints(_delta_proj, n_cats=5)
    CAT_KEYS = ["skip", "not_into", "indifferent", "like", "love"]
    print(f"  Delta-level midpoint range: [{_delta_proj.min():.3f}, {_delta_proj.max():.3f}]")

    # Build per-participant arrays
    print("Building per-trial arrays per participant...")
    per_part = []
    skipped = 0
    for p in parts:
        try:
            deltas, U, raw_lam, vis, actions, y = build_per_trial_arrays(
                p, embeddings, V, oid_to_idx, K,
                bin_midpoints=bin_midpoints, cat_keys=CAT_KEYS)
            per_part.append({"qualtrics_id": p["qualtrics_id"],
                             "condition": p["condition"],
                             "domain": p["domain"],
                             "deltas": deltas,
                             "U": U, "raw_lam": raw_lam, "visible": vis,
                             "actions": actions, "y": y})
        except KeyError as e:
            print(f"  skip {p['qualtrics_id']}: {e}")
            skipped += 1
    print(f"  {len(per_part)} participants prepped ({skipped} skipped)")

    # Diagnostic: show action distribution across all participants
    from collections import Counter
    action_counts = Counter()
    for p in per_part:
        for act in p["actions"].flat:
            if act:
                action_counts[act] += 1
    total_visible = sum(action_counts.values())
    if total_visible > 0:
        print(f"  Action distribution across {total_visible} visible-dim entries:")
        for act, cnt in action_counts.most_common():
            print(f"    {act}: {cnt} ({100*cnt/total_visible:.1f}%)")
        n_replaced = sum(1 for p in per_part for v in p["raw_lam"].flat if np.isfinite(v))
        print(f"  Dims with gradient modification (modify/moderate/remove): {n_replaced} ({100*n_replaced/total_visible:.1f}%)")
        n_passthrough = total_visible - n_replaced
        print(f"  Dims with passthrough (none/affirm): {n_passthrough} ({100*n_passthrough/total_visible:.1f}%)")
    cond_counts = pd.Series([p["condition"] for p in per_part]).value_counts()
    print("  by condition:", dict(cond_counts))

    lambdas = parse_grid(args.lambda_grid)
    gammas = parse_grid(args.gamma_grid)
    alphas = parse_grid(args.alpha_grid)
    grid = list(itertools.product(lambdas, gammas, alphas))
    print(f"\nGrid: {len(lambdas)} λ × {len(gammas)} γ × {len(alphas)} α "
          f"= {len(grid)} points × {len(per_part)} participants × "
          f"{args.n_folds} folds")

    rows = []
    for i, (lam, gamma, alpha) in enumerate(grid, 1):
        for p in per_part:
            cv = cv_one_participant(p["deltas"], p["U"], p["raw_lam"],
                                     p["visible"], p["y"], G,
                                     lam, gamma, alpha, args.lambda_standard,
                                     args.n_folds, args.seed)
            for r in cv:
                rows.append({
                    "lambda": lam, "gamma": gamma, "alpha": alpha,
                    "qualtrics_id": p["qualtrics_id"],
                    "condition": p["condition"],
                    "domain": p["domain"],
                    **r,
                })
        if i % 10 == 0 or i == len(grid):
            print(f"  done {i}/{len(grid)} grid points")

    df = pd.DataFrame(rows)
    df.to_csv(output_dir / "cv_results.csv", index=False)
    print(f"\nWrote {output_dir / 'cv_results.csv'} ({len(df)} rows)")

    # Per-condition × grid-point summary, including std-vs-partial deltas.
    summary = df.groupby(["condition", "lambda", "gamma", "alpha"]).agg(
        test_ll_std=("test_ll_std", "mean"),
        test_ll_part=("test_ll_part", "mean"),
        test_ll_blend=("test_ll_blend", "mean"),
        test_acc_std=("test_acc_std", "mean"),
        test_acc_part=("test_acc_part", "mean"),
        test_acc_blend=("test_acc_blend", "mean"),
        delta_ll=("delta_ll", "mean"),
        delta_acc=("delta_acc", "mean"),
        n_obs=("delta_ll", "size"),
    ).reset_index()
    summary.to_csv(output_dir / "cv_summary.csv", index=False)
    print(f"Wrote {output_dir / 'cv_summary.csv'} ({len(summary)} rows)")

    write_report(df, summary, output_dir / "calibration_report.md", args, per_part)
    print(f"Wrote {output_dir / 'calibration_report.md'}")

    plot_heatmaps(summary, output_dir)
    print("Done.")


if __name__ == "__main__":
    main()
