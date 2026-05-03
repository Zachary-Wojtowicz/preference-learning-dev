"""
Grid sweep over (lambda_partial, multiplier_scale, feedback_alpha) on the
weight-vec simulation.

Drives `simulate_one_user` from run_simulation.py for each grid point. With
N=30 users × 3 conditions × ~150 grid points each fitting Newton on a small
matrix, a typical sweep runs in a couple of minutes.

Outputs:
  - grid_results.csv: (grid_point × user × condition × fit) → metrics
  - grid_summary.csv: averaged over users; one row per (grid × cond × fit)
  - calibration_report.md: ranked top-5 settings for each condition, by
    each criterion (Spearman vs w*, held-out LL, predicted-rating DV).
  - heatmap_<condition>_<metric>.png: 2-D slice through the grid (lambda × scale,
    averaged over alpha) for visual inspection.

Usage:
  python simulation/calibrate_grid.py \
    --embeddings-parquet datasets/movies_100/movielens-32m-enriched-qwen3emb-100-embedded.parquet \
    --bt-scores method_llm_gen/outputs/movies_100/bt_scores.csv \
    --directions method_directions/outputs/movies_100/directions.npz \
    --option-id-column movie_id \
    --output-dir simulation/outputs/calibration_movies_100 \
    --num-users 30
"""

import argparse
import itertools
from pathlib import Path
from types import SimpleNamespace

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from run_simulation import (
    CONDITIONS, FIT_TYPES, DEFAULT_MULTS,
    load_data, load_predefined_pairs, generate_users,
    perdim_quintile_boundaries, simulate_one_user,
)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--embeddings-parquet", required=True)
    p.add_argument("--bt-scores", required=True)
    p.add_argument("--directions", required=True)
    p.add_argument("--option-id-column", default="movie_id")
    p.add_argument("--predefined-pairs", default=None)
    p.add_argument("--output-dir", required=True)

    p.add_argument("--num-users", type=int, default=30)
    p.add_argument("--num-trials", type=int, default=20)
    p.add_argument("--num-test-pairs", type=int, default=200)
    p.add_argument("--top-k-inferences", type=int, default=5)
    p.add_argument("--n-dimensions-shown", type=int, default=10)
    p.add_argument("--participant-noise", type=float, default=0.10)
    p.add_argument("--beta", type=float, default=2.0)
    p.add_argument("--lambda-standard", type=float, default=10.0)
    p.add_argument("--rating-temperature", type=float, default=5.0)
    p.add_argument("--seed", type=int, default=42)

    p.add_argument("--lambda-grid", default="0.1,0.25,0.5,1.0,2.5,5.0",
                   help="Comma-separated values of lambda_partial.")
    p.add_argument("--scale-grid", default="0.5,0.75,1.0,1.25,1.5",
                   help="Comma-separated multiplier-scale values.")
    p.add_argument("--alpha-grid", default="0.0,0.25,0.5,0.75,1.0",
                   help="Comma-separated feedback-alpha values.")
    return p.parse_args()


def parse_grid(s):
    return [float(x) for x in s.split(",") if x.strip()]


def run_one_grid_point(users, ctx_template, base_args, lam, scale, alpha,
                       seed_base):
    """Run all users at one (lam, scale, alpha) grid point. Returns rows."""
    mults = DEFAULT_MULTS * scale
    quintile_bounds = perdim_quintile_boundaries(
        ctx_template["pool_proj"], n_cats=len(mults))
    ctx = {
        **{k: v for k, v in ctx_template.items() if k != "pool_proj"},
        "quintile_bounds": quintile_bounds,
        "mults": mults,
    }
    sim_args = SimpleNamespace(**vars(base_args))
    sim_args.lambda_partial = lam
    sim_args.feedback_alpha = alpha
    sim_args.checkpoint_step = 0  # only final-T

    rows = []
    for user in users:
        rng = np.random.default_rng(seed_base + user["id"])
        res = simulate_one_user(user, ctx, sim_args, rng)
        for cond, cdata in res["conditions"].items():
            if not cdata["checkpoints"]:
                continue
            final = cdata["checkpoints"][-1]
            for fit in FIT_TYPES:
                rows.append({
                    "lambda": lam, "scale": scale, "alpha": alpha,
                    "user_id": user["id"], "condition": cond, "fit": fit,
                    "test_acc": final[f"test_acc_{fit}"],
                    "test_ll": final[f"test_ll_{fit}"],
                    "spearman": final[f"spearman_{fit}"],
                    "topn_sign": final[f"topn_sign_{fit}"],
                    "combined": final[f"combined_{fit}"],
                    "rating_partial_vs_standard":
                        final["rating_partial_vs_standard"],
                })
    return rows


def plot_heatmap(summary, condition, metric, output_path,
                 collapse="alpha"):
    """For (cond, metric), average over the collapse dim and plot a heatmap
    over the other two grid dims."""
    sub = summary[(summary["condition"] == condition)
                  & (summary["fit"] == "partial")]
    if sub.empty:
        return
    other_dims = [d for d in ["lambda", "scale", "alpha"] if d != collapse]
    g = sub.groupby(other_dims)[metric].mean().unstack(other_dims[1])
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    im = ax.imshow(g.values, aspect="auto", origin="lower",
                   cmap="viridis")
    ax.set_xticks(range(len(g.columns)), [f"{c:g}" for c in g.columns])
    ax.set_yticks(range(len(g.index)), [f"{r:g}" for r in g.index])
    ax.set_xlabel(other_dims[1])
    ax.set_ylabel(other_dims[0])
    ax.set_title(f"{condition} · partial · mean {metric}\n"
                 f"(averaged over {collapse})", fontweight="bold")
    fig.colorbar(im, ax=ax)
    # Annotate
    for i in range(g.shape[0]):
        for j in range(g.shape[1]):
            v = g.values[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                    color="white" if v < g.values.mean() else "black", fontsize=8)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def write_report(summary, output_path, args):
    lines = ["# Calibration Grid — Weight-vec Sim", ""]
    lines.append(f"- domain options: {Path(args.embeddings_parquet).name}")
    lines.append(f"- N users: {args.num_users}, trials: {args.num_trials}, "
                  f"test pairs: {args.num_test_pairs}")
    lines.append(f"- λ grid: {args.lambda_grid}")
    lines.append(f"- multiplier-scale grid: {args.scale_grid}")
    lines.append(f"- α (feedback strength) grid: {args.alpha_grid}")
    lines.append("")

    lines.append("## How to read")
    lines.append("")
    lines.append("Each section ranks (λ, scale, α) settings within a condition "
                  "by a particular criterion. The 'partial' fit is the one "
                  "whose parameters we're calibrating; 'standard' (kernel) and "
                  "'projected' rows are reference baselines.")
    lines.append("")

    metrics = [
        ("spearman", "Spearman rank correlation between the K-dim score "
                     "vector and the ground-truth w*. Higher = the inferred "
                     "preference vector is the right shape. **Most reliable** "
                     "calibration target since it isolates 'is the model "
                     "recovering the user's preferences?'."),
        ("test_ll", "Held-out test log-likelihood. Higher = better calibrated "
                    "predictions on unseen pairs."),
        ("test_acc", "Held-out test accuracy. Step function — less sensitive "
                     "than LL — but easy to interpret."),
        ("rating_partial_vs_standard",
         "Predicted experimental DV: P(participant prefers partial summary "
         "over standard). Aggregated by mapping summary quality through a "
         "sigmoid; this is the same DV the human pilot's evaluation screen "
         "estimates."),
    ]
    for cond in CONDITIONS:
        if cond == "choice_only":
            # Partial collapses to projected here; calibration only really
            # makes sense for inference conditions.
            continue
        lines.append(f"## Condition: {cond}")
        lines.append("")
        for m, descr in metrics:
            sub = summary[(summary["condition"] == cond)
                          & (summary["fit"] == "partial")]
            if sub.empty:
                continue
            sub2 = sub.sort_values(m, ascending=False).head(8)
            lines.append(f"### Top 8 by `{m}`")
            lines.append("")
            lines.append(f"_{descr}_")
            lines.append("")
            lines.append("| rank | λ | scale | α | "
                         "spearman | test_ll | test_acc | rating |")
            lines.append("|---|---|---|---|---|---|---|---|")
            for i, (_, r) in enumerate(sub2.iterrows(), 1):
                lines.append(f"| {i} | {r['lambda']:g} | {r['scale']:g} | "
                              f"{r['alpha']:g} | {r['spearman']:.3f} | "
                              f"{r['test_ll']:.3f} | {r['test_acc']:.3f} | "
                              f"{r['rating_partial_vs_standard']:.3f} |")
            lines.append("")

    # Aggregate "joint best": rank-sum across the 4 metrics for each cond.
    lines.append("## Joint-best recommendation (rank-sum across all 4 metrics)")
    lines.append("")
    lines.append("Each (λ, scale, α) gets ranked by each metric within each "
                  "condition; the rank-sum aggregates all four. Lowest rank-sum "
                  "= settings that look good on all criteria simultaneously. "
                  "Robust to a single metric being noisy.")
    lines.append("")
    for cond in CONDITIONS:
        if cond == "choice_only":
            continue
        sub = summary[(summary["condition"] == cond)
                      & (summary["fit"] == "partial")].copy()
        for m, _ in metrics:
            sub[f"rank_{m}"] = sub[m].rank(ascending=False)
        sub["rank_sum"] = sum(sub[f"rank_{m}"] for m, _ in metrics)
        sub = sub.sort_values("rank_sum").head(5)
        lines.append(f"### {cond}")
        lines.append("")
        lines.append("| rank | λ | scale | α | rank-sum | spearman | test_ll | rating |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for i, (_, r) in enumerate(sub.iterrows(), 1):
            lines.append(f"| {i} | {r['lambda']:g} | {r['scale']:g} | "
                          f"{r['alpha']:g} | {int(r['rank_sum'])} | "
                          f"{r['spearman']:.3f} | {r['test_ll']:.3f} | "
                          f"{r['rating_partial_vs_standard']:.3f} |")
        lines.append("")

    output_path.write_text("\n".join(lines) + "\n")


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading data...")
    embeddings, bt_scores, V, G, mu, option_ids, dim_names = load_data(
        args.embeddings_parquet, args.bt_scores, args.directions,
        option_id_column=args.option_id_column,
    )
    K = V.shape[0]
    print(f"  K={K}, N options={len(option_ids)}")

    centered = embeddings - mu[np.newaxis, :]
    pool_proj = centered @ V.T

    rng = np.random.default_rng(args.seed)
    users = generate_users(args.num_users, K, rng)

    predefined_pairs = None
    if args.predefined_pairs:
        predefined_pairs = load_predefined_pairs(args.predefined_pairs, option_ids)

    ctx_template = {
        "embeddings": embeddings, "bt_scores": bt_scores,
        "V": V, "G": G, "mu": mu,
        "predefined_pairs": predefined_pairs,
        "pool_proj": pool_proj,  # consumed inside run_one_grid_point
    }

    lambdas = parse_grid(args.lambda_grid)
    scales = parse_grid(args.scale_grid)
    alphas = parse_grid(args.alpha_grid)
    grid = list(itertools.product(lambdas, scales, alphas))
    print(f"\nGrid: {len(lambdas)} λ × {len(scales)} scales × {len(alphas)} αs "
          f"= {len(grid)} points × {args.num_users} users")

    base_args = SimpleNamespace(
        num_trials=args.num_trials, num_test_pairs=args.num_test_pairs,
        top_k_inferences=args.top_k_inferences,
        n_dimensions_shown=args.n_dimensions_shown,
        participant_noise=args.participant_noise, beta=args.beta,
        lambda_standard=args.lambda_standard,
        rating_temperature=args.rating_temperature,
    )

    all_rows = []
    for i, (lam, scale, alpha) in enumerate(grid, 1):
        rows = run_one_grid_point(users, ctx_template, base_args,
                                   lam, scale, alpha, args.seed)
        all_rows.extend(rows)
        if i % 5 == 0 or i == len(grid):
            print(f"  done {i}/{len(grid)} grid points")

    df = pd.DataFrame(all_rows)
    df.to_csv(output_dir / "grid_results.csv", index=False)
    print(f"\nWrote {output_dir / 'grid_results.csv'} ({len(df)} rows)")

    # Aggregate over users
    summary = df.groupby(["lambda", "scale", "alpha", "condition", "fit"]).agg(
        spearman=("spearman", "mean"),
        topn_sign=("topn_sign", "mean"),
        test_ll=("test_ll", "mean"),
        test_acc=("test_acc", "mean"),
        combined=("combined", "mean"),
        rating_partial_vs_standard=("rating_partial_vs_standard", "mean"),
    ).reset_index()
    summary.to_csv(output_dir / "grid_summary.csv", index=False)
    print(f"Wrote {output_dir / 'grid_summary.csv'} ({len(summary)} rows)")

    write_report(summary, output_dir / "calibration_report.md", args)
    print(f"Wrote {output_dir / 'calibration_report.md'}")

    for cond in ["inference_affirm", "inference_categories"]:
        for metric in ["spearman", "test_ll", "rating_partial_vs_standard"]:
            try:
                plot_heatmap(summary, cond, metric,
                             output_dir / f"heatmap_{cond}_{metric}.png")
            except Exception as e:
                print(f"  heatmap {cond}/{metric} skipped: {e}")
    print("Done.")


if __name__ == "__main__":
    main()
