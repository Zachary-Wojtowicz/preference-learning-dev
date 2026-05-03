"""
Calibrate (lambda_partial, multiplier_scale, feedback_alpha) using the pilot
data via within-participant cross-validation.

For each pilot participant we observe 20 (option_a_id, option_b_id, chosen,
visible_dims, multipliers) rows. We treat each participant as their own
ground truth: refit the partial model on a train subset of their trials and
score on the held-out trials. Sweep the parameter grid; pick parameters that
maximize mean held-out log-likelihood across participants.

CV scheme:
  - 5-fold (default) over each participant's 20 trials, stratified by chosen
    side to avoid degenerate folds.
  - Per fold × per (λ, s, α): refit the K-dim primal logistic on the
    rescaled design matrix Ũ_α = U·((1−α) + α·s·λ_raw); evaluate on the
    held-out fold's trials.

Outputs (in --output-dir):
  - cv_results.csv: one row per (participant × fold × grid-point)
  - cv_summary.csv: aggregated over folds and participants
  - calibration_report.md: ranked top-N settings + recommendation
  - heatmap_<metric>.png: 2-D slice of the grid

Usage:
  python experiments/pilot/calibrate_from_pilot.py \
    --pilot-csv experiments/pilot/data.csv \
    --embeddings-parquet datasets/dailydilemmas/selected_actions-embedded.parquet \
    --directions method_directions/outputs/dailydilemmas/directions.npz \
    --option-id-column action_id \
    --output-dir experiments/pilot/calibration

Caveat: the pilot is single-cell (inference_categories × dailydilemmas).
Calibration here is for *that* cell only. inference_affirm needs separate
data.
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
    p.add_argument("--lambda-grid", default="0.05,0.1,0.25,0.5,1.0,2.5,5.0")
    p.add_argument("--scale-grid", default="0.5,0.75,1.0,1.25,1.5")
    p.add_argument("--alpha-grid", default="0.0,0.25,0.5,0.75,1.0")
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


# -- shared with run_simulation; reproduced here so this script is standalone --

def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -50, 50)))


def fit_partial_primal(U, y, G, lam, max_iter=15, tol=1e-7):
    T, K = U.shape
    beta = np.zeros(K)
    for _ in range(max_iter):
        u = U @ beta
        p = sigmoid(u)
        w = p * (1 - p)
        grad = U.T @ (p - y) + lam * G @ beta
        H = U.T @ (w[:, None] * U) + lam * G
        try:
            d_beta = np.linalg.solve(H, -grad)
        except np.linalg.LinAlgError:
            break
        beta = beta + d_beta
        if np.max(np.abs(d_beta)) < tol:
            break
    return beta


def heldout_ll(logits, y):
    p = sigmoid(logits)
    eps = 1e-10
    return float(np.mean(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps)))


# ---------------------------------------------------------------------------

def load_pilot_participants(pilot_csv):
    df = pd.read_csv(pilot_csv).iloc[2:].reset_index(drop=True)
    parts = []
    for _, row in df.iterrows():
        if row["condition"] != "inference_categories":
            continue
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
            "responses": responses,
        })
    return parts


def build_per_trial_arrays(participant, embeddings, V, oid_to_idx, K):
    """For one participant, build (deltas, U, raw_lam, visible_mask, y).

    raw_lam[t,k] is the participant's submitted multiplier for visible dims,
    1.0 elsewhere. visible_mask[t,k] is True for visible dims.
    """
    resp = participant["responses"]
    T = len(resp)
    d = embeddings.shape[1]
    deltas = np.zeros((T, d))
    raw_lam = np.ones((T, K))
    visible_mask = np.zeros((T, K), dtype=bool)
    y = np.zeros(T, dtype=float)
    for t, r in enumerate(resp):
        oa = oid_to_idx.get(str(r["option_a_id"]))
        ob = oid_to_idx.get(str(r["option_b_id"]))
        if oa is None or ob is None:
            raise KeyError(f"Unknown option ids: {r['option_a_id']}, {r['option_b_id']}")
        deltas[t] = embeddings[oa] - embeddings[ob]
        y[t] = 1.0 if r["chosen"] == "a" else 0.0
        for dim_str, info in (r.get("inference_values") or {}).items():
            # dim_X is 1-indexed in the experiment data
            k = int(dim_str.split("_")[1]) - 1
            if not (0 <= k < K):
                continue
            visible_mask[t, k] = True
            raw_lam[t, k] = float(info.get("multiplier", 0.0))
    U = deltas @ V.T  # (T, K)
    return deltas, U, raw_lam, visible_mask, y


def cv_one_participant(U, raw_lam, visible_mask, y, G, lam, scale, alpha,
                        n_folds, seed):
    """Stratified K-fold CV for one participant. Returns list of dicts.
    Skips participants whose minor class (chosen='a' or 'b') has < 2 samples
    since stratified CV needs ≥ 2 per class."""
    T = len(y)
    if T < 2 or len(np.unique(y)) < 2:
        return []
    n_min = int(min(np.bincount(y.astype(int))))
    if n_min < 2:
        return []
    n_splits = min(n_folds, n_min)
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)

    rows = []
    for fold_idx, (train_idx, test_idx) in enumerate(skf.split(np.zeros(T), y.astype(int))):
        # Build Ũ_α with the original participant's submitted multipliers
        # rescaled by `scale`, then α-interpolated.
        # For invisible dims raw_lam is already 1.0 → contribution stays U.
        # For visible dims, recompute the design entry.
        scaled_lam = np.where(visible_mask, scale * raw_lam, 1.0)
        feedback = (1.0 - alpha) + alpha * scaled_lam
        # invisible dims should remain 1.0 (no feedback applied)
        feedback = np.where(visible_mask, feedback, 1.0)
        U_adj = U * feedback

        beta = fit_partial_primal(U_adj[train_idx], y[train_idx], G, lam)
        logits_te = U[test_idx] @ beta  # evaluate on PLAIN U (held-out
                                         # generalization to unseen pairs)
        acc = float(((logits_te > 0).astype(float) == y[test_idx]).mean())
        ll = heldout_ll(logits_te, y[test_idx])
        rows.append({"fold": fold_idx, "n_test": int(len(test_idx)),
                     "test_acc": acc, "test_ll": ll})
    return rows


def write_report(summary, output_path, args, n_participants):
    lines = ["# Pilot Calibration Report", ""]
    lines.append(f"- pilot file: `{Path(args.pilot_csv).name}`")
    lines.append(f"- N participants used: {n_participants} "
                  f"(inference_categories only)")
    lines.append(f"- {args.n_folds}-fold stratified CV per participant")
    lines.append(f"- λ grid: {args.lambda_grid}")
    lines.append(f"- multiplier-scale grid: {args.scale_grid}")
    lines.append(f"- α (feedback strength) grid: {args.alpha_grid}")
    lines.append("")

    lines.append("## How to read")
    lines.append("")
    lines.append("Each (λ, s, α) combination is scored by within-participant "
                  "cross-validated held-out **log-likelihood** and **accuracy**, "
                  "averaged across all 30 pilot participants and all 5 folds. "
                  "Higher = better. The test pairs are held out from training "
                  "for that fold but come from the participant's own real "
                  "trials — so this measures how well the partial fit predicts "
                  "the participant's *own* unseen choices, not a synthetic "
                  "ground truth.")
    lines.append("")

    metrics = [
        ("test_ll", "Mean held-out log-likelihood across folds and "
                    "participants. **Primary calibration metric** — sensitive "
                    "to confidence calibration and least dependent on the "
                    "small per-fold N."),
        ("test_acc", "Mean held-out accuracy. Step function — easier to "
                     "interpret but noisier at small fold sizes."),
    ]
    for m, descr in metrics:
        sub = summary.sort_values(m, ascending=False).head(10)
        lines.append(f"### Top 10 by `{m}`")
        lines.append("")
        lines.append(f"_{descr}_")
        lines.append("")
        lines.append("| rank | λ | scale | α | test_ll | test_acc |")
        lines.append("|---|---|---|---|---|---|")
        for i, (_, r) in enumerate(sub.iterrows(), 1):
            lines.append(f"| {i} | {r['lambda']:g} | {r['scale']:g} | "
                          f"{r['alpha']:g} | {r['test_ll']:+.4f} | "
                          f"{r['test_acc']:.3f} |")
        lines.append("")

    # Joint best by rank-sum across LL + acc
    sub = summary.copy()
    sub["rank_ll"] = sub["test_ll"].rank(ascending=False)
    sub["rank_acc"] = sub["test_acc"].rank(ascending=False)
    sub["rank_sum"] = sub["rank_ll"] + sub["rank_acc"]
    sub = sub.sort_values("rank_sum").head(8)
    lines.append("### Joint best (rank-sum of LL + accuracy)")
    lines.append("")
    lines.append("| rank | λ | scale | α | rank_sum | test_ll | test_acc |")
    lines.append("|---|---|---|---|---|---|---|")
    for i, (_, r) in enumerate(sub.iterrows(), 1):
        lines.append(f"| {i} | {r['lambda']:g} | {r['scale']:g} | "
                      f"{r['alpha']:g} | {int(r['rank_sum'])} | "
                      f"{r['test_ll']:+.4f} | {r['test_acc']:.3f} |")
    lines.append("")

    # Trivial baselines
    lines.append("## Reference baselines")
    lines.append("")
    lines.append("- **Chance**: log-likelihood = ln(0.5) = −0.693, accuracy = 0.500")
    lines.append("- **No-feedback baseline (α=0)**: rows in the table where α=0 "
                  "represent the projected fit (feedback ignored). Compare "
                  "best feedback-on rows to the best α=0 row to see whether "
                  "feedback adds value on real human data.")
    lines.append("")
    no_fb = summary[summary["alpha"] == 0.0].sort_values("test_ll", ascending=False).iloc[0]
    fb_on = summary[summary["alpha"] > 0.0].sort_values("test_ll", ascending=False).iloc[0]
    delta = fb_on["test_ll"] - no_fb["test_ll"]
    lines.append(f"  - Best α=0:   λ={no_fb['lambda']:g}, scale={no_fb['scale']:g} "
                  f"→ test_ll = {no_fb['test_ll']:+.4f}, acc = {no_fb['test_acc']:.3f}")
    lines.append(f"  - Best α>0:   λ={fb_on['lambda']:g}, scale={fb_on['scale']:g}, "
                  f"α={fb_on['alpha']:g} → test_ll = {fb_on['test_ll']:+.4f}, "
                  f"acc = {fb_on['test_acc']:.3f}")
    lines.append(f"  - **Δ LL (feedback − no-feedback): {delta:+.4f}** "
                  f"({'feedback helps' if delta > 0 else 'feedback hurts'} on this "
                  f"pilot cell)")
    lines.append("")

    output_path.write_text("\n".join(lines) + "\n")


def plot_heatmaps(summary, output_dir):
    for metric in ["test_ll", "test_acc"]:
        for collapse in ["alpha", "scale", "lambda"]:
            other = [d for d in ["lambda", "scale", "alpha"] if d != collapse]
            g = summary.groupby(other)[metric].mean().unstack(other[1])
            fig, ax = plt.subplots(figsize=(6.5, 4.5))
            im = ax.imshow(g.values, aspect="auto", origin="lower",
                            cmap="viridis")
            ax.set_xticks(range(len(g.columns)), [f"{c:g}" for c in g.columns])
            ax.set_yticks(range(len(g.index)), [f"{r:g}" for r in g.index])
            ax.set_xlabel(other[1])
            ax.set_ylabel(other[0])
            ax.set_title(f"Pilot CV · mean {metric}\n(averaged over {collapse})",
                          fontweight="bold")
            fig.colorbar(im, ax=ax)
            for i in range(g.shape[0]):
                for j in range(g.shape[1]):
                    v = g.values[i, j]
                    ax.text(j, i, f"{v:.3f}", ha="center", va="center",
                            color="white" if v < g.values.mean() else "black",
                            fontsize=8)
            plt.tight_layout()
            plt.savefig(output_dir / f"heatmap_{metric}_collapse_{collapse}.png",
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
    G = V @ V.T
    print(f"  K={K}, N options={len(option_ids)}")

    # Build per-participant arrays
    print("Building per-trial arrays per participant...")
    per_part = []
    skipped = 0
    for p in parts:
        try:
            deltas, U, raw_lam, vis, y = build_per_trial_arrays(
                p, embeddings, V, oid_to_idx, K)
            per_part.append({"qualtrics_id": p["qualtrics_id"],
                             "U": U, "raw_lam": raw_lam, "visible": vis, "y": y})
        except KeyError as e:
            print(f"  skip {p['qualtrics_id']}: {e}")
            skipped += 1
    print(f"  {len(per_part)} participants prepped ({skipped} skipped)")

    lambdas = parse_grid(args.lambda_grid)
    scales = parse_grid(args.scale_grid)
    alphas = parse_grid(args.alpha_grid)
    grid = list(itertools.product(lambdas, scales, alphas))
    print(f"\nGrid: {len(lambdas)} λ × {len(scales)} s × {len(alphas)} α "
          f"= {len(grid)} points × {len(per_part)} participants × "
          f"{args.n_folds} folds")

    rows = []
    for i, (lam, scale, alpha) in enumerate(grid, 1):
        for p in per_part:
            cv = cv_one_participant(p["U"], p["raw_lam"], p["visible"],
                                     p["y"], G, lam, scale, alpha,
                                     args.n_folds, args.seed)
            for r in cv:
                rows.append({
                    "lambda": lam, "scale": scale, "alpha": alpha,
                    "qualtrics_id": p["qualtrics_id"],
                    **r,
                })
        if i % 10 == 0 or i == len(grid):
            print(f"  done {i}/{len(grid)} grid points")

    df = pd.DataFrame(rows)
    df.to_csv(output_dir / "cv_results.csv", index=False)
    print(f"\nWrote {output_dir / 'cv_results.csv'} ({len(df)} rows)")

    summary = df.groupby(["lambda", "scale", "alpha"]).agg(
        test_ll=("test_ll", "mean"),
        test_acc=("test_acc", "mean"),
        n_obs=("test_ll", "size"),
    ).reset_index()
    summary.to_csv(output_dir / "cv_summary.csv", index=False)
    print(f"Wrote {output_dir / 'cv_summary.csv'} ({len(summary)} rows)")

    write_report(summary, output_dir / "calibration_report.md", args, len(per_part))
    print(f"Wrote {output_dir / 'calibration_report.md'}")

    plot_heatmaps(summary, output_dir)
    print("Done.")


if __name__ == "__main__":
    main()
