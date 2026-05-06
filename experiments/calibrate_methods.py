"""
Method calibration sweep — per-condition optimal (α, multiplier scheme) for LOO accuracy.

For each method (= condition), sweeps over a grid of (α, multiplier scheme)
[and optionally λ] and reports the combination that maximizes mean LOO
accuracy lift (projection_alpha − projection_only). Designed for:
  (a) reporting per-method optimal hyperparameters in the paper,
  (b) informing what defaults to deploy in new domains.

Multiplier schemes (define how each category maps to a per-dim prior value):
  - quintile_midpoints: per-dim quintile midpoints of the symmetrized
                        raw_projection distribution. Variance-weighted across
                        dims, quintile-derived (nonlinear) category spacing.
                        CURRENT DEFAULT.
  - linear_variance:    [-2σ, -σ, 0, σ, 2σ] per dim where σ = the dim's
                        raw_projection std. Variance-weighted, linear spacing.
                        Isolates the linear-vs-quintile axis.
  - linear_uniform:     [-2, -1, 0, 1, 2] for every dim. Uniform across dims,
                        linear spacing. Isolates the variance-weighting axis.
  - sign_uniform:       [-1, -1, 0, 1, 1] for every dim. Binary direction
                        (love=like, skip=not_into). Tests whether the 5-cat
                        granularity buys anything over 3-cat.
  - extreme_uniform:    [-1, 0, 0, 0, 1] for every dim. Only love/skip
                        contribute. Tests whether middle categories are noise.

Important: post-rescaling (fit_btl_with_rescaled_prior), only the SHAPE of the
prior matters — its L2 norm is normalized to match the data-fit β. So
{-2,-1,0,1,2} and {-1,-0.5,0,0.5,1} give identical results. Schemes differ in
relative dim weighting and relative category spacing, not absolute magnitude.

Usage:
    python experiments/dilemmas/calibrate_methods.py
    python experiments/dilemmas/calibrate_methods.py --data path/to/data.csv
    python experiments/dilemmas/calibrate_methods.py --lambda-sweep    # adds λ axis
    python experiments/dilemmas/calibrate_methods.py --schemes quintile_midpoints linear_uniform

Outputs (to analysis_outputs/):
    calibration_sweep.png   — per-condition heatmaps (α × scheme)
    calibration_sweep.json  — full per-cell results
    calibration_summary.md  — shareable markdown report
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from analyze import (  # noqa: E402
    load_qualtrics_csv, parse_participants, load_domain_assets,
    compute_dim_midpoints, build_design_matrices, build_beta_prior,
    loo_accuracy, is_complete, t_ci,
    LAMBDA_PARTIAL, N_CATS,
    DATA_PATH, INFERENCE_CONDITIONS,
)


# ============================================================================
# Search grid
# ============================================================================
ALPHA_GRID = [0.0, 0.01, 0.03, 0.1, 0.3, 1.0, 2.0, 5.0]
LAMBDA_GRID_DEFAULT = [0.01]
LAMBDA_GRID_SWEEP = [0.001, 0.01, 0.1, 1.0]

SCHEMES = [
    "quintile_midpoints",
    "linear_variance",
    "linear_uniform",
    "sign_uniform",
    "extreme_uniform",
]

SCHEME_LABELS = {
    "quintile_midpoints": "Quintile\nmidpoints\n(current)",
    "linear_variance":    "Linear\nvariance",
    "linear_uniform":     "Linear\nuniform",
    "sign_uniform":       "Sign\nonly",
    "extreme_uniform":    "Extreme\nonly",
}

COND_LABELS = {
    "inference_affirm":     "Affirm/remove",
    "inference_categories": "Category select",
}


# ============================================================================
# Multiplier schemes
# ============================================================================
def midpoints_for_scheme(scheme, dim_ids, tp, n_cats=N_CATS):
    """Return {dim_id: [c0, c1, ..., c_{n_cats-1}]} under the given scheme.

    Plugged into build_beta_prior as the `midpoints_by_did` argument, so
    callers can swap schemes without touching the prior-construction code.
    """
    K = len(dim_ids)
    if scheme == "quintile_midpoints":
        return compute_dim_midpoints(tp, dim_ids, n_cats=n_cats)

    if scheme == "linear_variance":
        # Per-dim std from the raw_projection distribution; linear spacing.
        by_dim = {did: [] for did in dim_ids}
        for entry in tp:
            rp = entry.get("raw_projection")
            if not rp or len(rp) != K:
                continue
            for k in range(K):
                v = rp[k]
                if np.isfinite(v):
                    by_dim[dim_ids[k]].append(v)
        out = {}
        for did, arr in by_dim.items():
            if len(arr) < 2:
                out[did] = None
            else:
                sd = float(np.std(arr, ddof=1))
                out[did] = [-2 * sd, -sd, 0.0, sd, 2 * sd]
        return out

    # Uniform schemes (same per-dim list).
    if scheme == "linear_uniform":
        vals = [-2.0, -1.0, 0.0, 1.0, 2.0]
    elif scheme == "sign_uniform":
        vals = [-1.0, -1.0, 0.0, 1.0, 1.0]
    elif scheme == "extreme_uniform":
        vals = [-1.0, 0.0, 0.0, 0.0, 1.0]
    else:
        raise ValueError(f"Unknown scheme: {scheme}")
    return {did: list(vals) for did in dim_ids}


# ============================================================================
# Per-participant LOO at a (α, λ, scheme) setting
# ============================================================================
def loo_at_setting(participant, domain_assets, midpoints, alpha, lam):
    """Returns (loo_proj_only, loo_proj_alpha) for this participant under
    these (α, λ) and the specified midpoints. At α=0 the augmented fit
    collapses to the baseline by construction (post-rescaling)."""
    tp = domain_assets["trial_projections"]
    dim_ids = domain_assets["dim_ids"]
    categories = domain_assets["categories"]
    n_dims = domain_assets["n_dims"]

    out = build_design_matrices(participant, tp)
    if out is None:
        return None, None
    U, _, y = out

    # Baseline: projection_only at this λ (no prior).
    loo_base = loo_accuracy(U, y, lam=lam, beta_prior_fn=None, mu_prior=0.0)

    if alpha <= 0:
        return loo_base, loo_base

    bp_fn = lambda idxs: build_beta_prior(
        participant, dim_ids, midpoints, n_dims, categories, train_indices=idxs)
    loo_aug = loo_accuracy(U, y, lam=lam, beta_prior_fn=bp_fn, mu_prior=alpha,
                           rescale_prior=True)
    return loo_base, loo_aug


# ============================================================================
# Markdown summary
# ============================================================================
def write_calibration_md(cell_summary, optimal, cond_counts, schemes,
                         alpha_grid, lambdas, out_path, data_path):
    """Self-contained shareable markdown of the calibration sweep."""

    L = []
    L.append("# Method calibration summary")
    L.append("")
    L.append(f"_Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} "
             f"by `calibrate_methods.py` from `{Path(data_path).name}`._")
    L.append("")
    L.append("![Calibration sweep](calibration_sweep.png)")
    L.append("")
    L.append("## What this is")
    L.append("")
    L.append("For each inference method, search over (α, multiplier scheme) "
             "to find the combination that maximizes mean LOO accuracy lift "
             "(`projection_alpha − projection_only`). Reported with 95% CIs.")
    L.append("")
    L.append("**Schemes compared:**")
    L.append("")
    L.append("| Scheme | Dim weighting | Category spacing |")
    L.append("|---|---|---|")
    L.append("| `quintile_midpoints` | variance-weighted | quintile-derived (nonlinear) |")
    L.append("| `linear_variance` | variance-weighted | linear |")
    L.append("| `linear_uniform` | uniform | linear |")
    L.append("| `sign_uniform` | uniform | binary (love=like, skip=not_into) |")
    L.append("| `extreme_uniform` | uniform | only love/skip count |")
    L.append("")
    L.append(f"**α grid:** {alpha_grid}")
    L.append(f"**λ grid:** {list(lambdas)}")
    L.append("")
    L.append("Note: post-rescaling, only the *shape* of the prior matters "
             "(its L2 norm is normalized). So schemes differ in relative dim "
             "weighting and relative category spacing, not absolute magnitude.")
    L.append("")

    # Optimal per condition
    L.append("## Optimal hyperparameters per method")
    L.append("")
    L.append("| Method | N | scheme | α | λ | Δacc | 95% CI |")
    L.append("|---|---|---|---|---|---|---|")
    for cond in INFERENCE_CONDITIONS:
        b = optimal.get(cond)
        n = cond_counts.get(cond, 0)
        if not b:
            L.append(f"| {COND_LABELS[cond]} | {n} | — | — | — | — | — |")
            continue
        ci_lo = b["mean_diff"] - b["ci_half"]
        ci_hi = b["mean_diff"] + b["ci_half"]
        L.append(f"| {COND_LABELS[cond]} | {n} | `{b['scheme']}` | "
                 f"{b['alpha']} | {b['lam']} | "
                 f"{b['mean_diff']:+.4f} | "
                 f"[{ci_lo:+.4f}, {ci_hi:+.4f}] |")
    L.append("")

    # Per-method top-5 cells
    for cond in INFERENCE_CONDITIONS:
        L.append(f"## {COND_LABELS[cond]}: top settings")
        L.append("")
        L.append(f"_N = {cond_counts.get(cond, 0)}. Sorted by mean Δacc, "
                 "top 8 cells shown._")
        L.append("")
        L.append("| scheme | α | λ | Δacc | 95% CI |")
        L.append("|---|---|---|---|---|")
        cond_cells = [(k, v) for k, v in cell_summary.items() if k[0] == cond]
        cond_cells.sort(key=lambda x: x[1]["mean_diff"], reverse=True)
        for (_, scheme, alpha, lam), s in cond_cells[:8]:
            mean = s["mean_diff"]
            ci = s["ci_half"]
            L.append(f"| `{scheme}` | {alpha} | {lam} | "
                     f"{mean:+.4f} | "
                     f"[{mean - ci:+.4f}, {mean + ci:+.4f}] |")
        L.append("")

    L.append("## Reading the heatmap")
    L.append("")
    L.append("- Rows: α (feedback prior strength). Columns: multiplier scheme.")
    L.append("- Cell color: mean LOO Δacc. Blue = prior helps; red = prior hurts.")
    L.append("- Black box: argmax cell for that condition.")
    L.append("- α=0 row is the post-rescaling sanity check: must be exactly 0.")
    L.append("")
    L.append("## Notes")
    L.append("")
    L.append("- **Metric:** mean LOO accuracy lift (augmented − baseline) "
             "across participants in the condition.")
    L.append("- **CIs:** 95%, t-distribution with df = n−1.")
    L.append("- **Inclusion:** participants who completed all 20 trials, "
             "the summary comparison, and both prediction ratings.")
    L.append("- **Caveat:** the argmax over a discrete grid has selection "
             "bias relative to the true optimum, especially when many cells "
             "have overlapping CIs. The heatmap is more informative than a "
             "single-cell winner.")
    L.append("")

    with open(out_path, "w") as f:
        f.write("\n".join(L))


# ============================================================================
# Main
# ============================================================================
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(DATA_PATH),
                        help=f"Qualtrics CSV path (default: {DATA_PATH})")
    parser.add_argument("--out-dir", default=str(SCRIPT_DIR / "analysis_outputs"),
                        help="Where to write outputs.")
    parser.add_argument("--lambda-sweep", action="store_true",
                        help="Also sweep λ over [0.001, 0.01, 0.1, 1.0]. "
                             "~4× slower; off by default.")
    parser.add_argument("--schemes", nargs="+", default=SCHEMES,
                        choices=SCHEMES,
                        help="Subset of schemes to evaluate.")
    args = parser.parse_args()

    data_path = Path(args.data).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(exist_ok=True, parents=True)
    schemes_to_run = list(args.schemes)
    lambdas = LAMBDA_GRID_SWEEP if args.lambda_sweep else LAMBDA_GRID_DEFAULT

    print(f"Reading {data_path}")
    df = load_qualtrics_csv(data_path)
    participants = [p for p in parse_participants(df) if is_complete(p)]
    inf_p = [p for p in participants if p["condition"] in INFERENCE_CONDITIONS]
    print(f"  {len(participants)} complete participants, "
          f"{len(inf_p)} in inference conditions")

    cond_counts = defaultdict(int)
    for p in inf_p:
        cond_counts[p["condition"]] += 1
    for c in INFERENCE_CONDITIONS:
        print(f"    {c}: N = {cond_counts[c]}")

    n_cells = (len(schemes_to_run) * len(ALPHA_GRID)
               * len(lambdas) * len(INFERENCE_CONDITIONS))
    print(f"\nSchemes: {schemes_to_run}")
    print(f"α grid:  {ALPHA_GRID}")
    print(f"λ grid:  {list(lambdas)}")
    print(f"Total cells: {n_cells}\n")

    # Domain assets and per-(scheme, domain) midpoints
    domains = sorted({p.get("domain") for p in inf_p if p.get("domain")})
    domain_assets = {}
    midpoints_by_scheme = defaultdict(dict)
    for d in domains:
        a = load_domain_assets(d)
        domain_assets[d] = a
        for scheme in schemes_to_run:
            midpoints_by_scheme[scheme][d] = midpoints_for_scheme(
                scheme, a["dim_ids"], a["trial_projections"])

    # Sweep
    results = defaultdict(list)  # (cond, scheme, α, λ) -> [{pid, base, aug, diff}]
    print("Sweeping ...")
    cell_idx = 0
    for cond in INFERENCE_CONDITIONS:
        cond_p = [p for p in inf_p if p["condition"] == cond]
        for scheme in schemes_to_run:
            for alpha in ALPHA_GRID:
                for lam in lambdas:
                    cell_idx += 1
                    for p in cond_p:
                        domain = p.get("domain")
                        if domain not in domain_assets:
                            continue
                        base, aug = loo_at_setting(
                            p, domain_assets[domain],
                            midpoints_by_scheme[scheme][domain],
                            alpha, lam)
                        if base is None:
                            continue
                        results[(cond, scheme, alpha, lam)].append({
                            "pid": p.get("participant_id"),
                            "loo_base": base,
                            "loo_aug": aug,
                            "diff": aug - base,
                        })
                    n_done = len(results[(cond, scheme, alpha, lam)])
                    print(f"  [{cell_idx:>3d}/{n_cells}] {cond:22s} "
                          f"{scheme:20s} α={alpha:>5.2f} λ={lam:>5.3f}  "
                          f"N={n_done}")

    # Aggregate per cell + find optimal per condition
    cell_summary = {}
    optimal = {}
    for cond in INFERENCE_CONDITIONS:
        best = None
        for scheme in schemes_to_run:
            for alpha in ALPHA_GRID:
                for lam in lambdas:
                    rows = results[(cond, scheme, alpha, lam)]
                    if not rows:
                        continue
                    diffs = np.array([r["diff"] for r in rows])
                    mean, ci = t_ci(diffs)
                    n = len(diffs)
                    sem = (float(diffs.std(ddof=1) / np.sqrt(n))
                           if n > 1 else 0.0)
                    cell_summary[(cond, scheme, alpha, lam)] = {
                        "n": n, "mean_diff": mean, "sem": sem, "ci_half": ci,
                    }
                    # Best by mean_diff
                    if best is None or mean > best["mean_diff"]:
                        best = {
                            "scheme": scheme, "alpha": alpha, "lam": lam,
                            "mean_diff": mean, "ci_half": ci,
                            "sem": sem, "n": n,
                        }
        optimal[cond] = best

    # Print summary table
    print()
    print("=" * 80)
    print("CALIBRATION SWEEP — optimal (α, scheme) per method via LOO accuracy")
    print("=" * 80)
    for cond in INFERENCE_CONDITIONS:
        print(f"\n{cond}  (N = {cond_counts[cond]})")
        print(f"  {'scheme':<22s} {'α':>5s} {'λ':>6s} {'Δacc':>9s} "
              f"{'95% CI':>22s}")
        cond_cells = [(k, v) for k, v in cell_summary.items() if k[0] == cond]
        cond_cells.sort(key=lambda x: x[1]["mean_diff"], reverse=True)
        for (_, scheme, alpha, lam), s in cond_cells[:8]:
            mean = s["mean_diff"]
            ci = s["ci_half"]
            print(f"  {scheme:<22s} {alpha:>5.2f} {lam:>6.3f} "
                  f"{mean:>+9.4f} [{mean - ci:>+7.4f}, {mean + ci:>+7.4f}]")
        if optimal[cond]:
            b = optimal[cond]
            print(f"  → BEST: scheme={b['scheme']}  α={b['alpha']}  "
                  f"λ={b['lam']}")
            print(f"     Δacc = {b['mean_diff']:+.4f}  "
                  f"95% CI [{b['mean_diff'] - b['ci_half']:+.4f}, "
                  f"{b['mean_diff'] + b['ci_half']:+.4f}]")

    # Heatmap (default λ panel only)
    main_lam = lambdas[0] if LAMBDA_PARTIAL not in lambdas else LAMBDA_PARTIAL
    n_panels = len(INFERENCE_CONDITIONS)
    fig, axes = plt.subplots(1, n_panels,
                              figsize=(6.5 * n_panels, 5.2),
                              squeeze=False)
    axes = axes[0]

    # Common color scale across panels — symmetric around 0
    all_vals = [s["mean_diff"]
                for k, s in cell_summary.items() if k[3] == main_lam]
    absmax = float(max(0.005, np.nanmax(np.abs(all_vals)) if all_vals else 0.01))

    for ax, cond in zip(axes, INFERENCE_CONDITIONS):
        grid = np.full((len(ALPHA_GRID), len(schemes_to_run)), np.nan)
        for i, alpha in enumerate(ALPHA_GRID):
            for j, scheme in enumerate(schemes_to_run):
                key = (cond, scheme, alpha, main_lam)
                if key in cell_summary:
                    grid[i, j] = cell_summary[key]["mean_diff"]

        im = ax.imshow(grid, cmap="RdBu_r", vmin=-absmax, vmax=absmax,
                       aspect="auto")
        ax.set_xticks(np.arange(len(schemes_to_run)))
        ax.set_xticklabels([SCHEME_LABELS[s] for s in schemes_to_run],
                           fontsize=8)
        ax.set_yticks(np.arange(len(ALPHA_GRID)))
        ax.set_yticklabels([f"{a:g}" for a in ALPHA_GRID], fontsize=9)
        ax.set_xlabel("Multiplier scheme", fontsize=10)
        ax.set_ylabel("α  (mu_prior)", fontsize=10)
        ax.set_title(
            f"{COND_LABELS[cond]}  (N={cond_counts[cond]}, λ={main_lam})",
            fontsize=11)
        # Cell annotations
        for i in range(len(ALPHA_GRID)):
            for j in range(len(schemes_to_run)):
                v = grid[i, j]
                if np.isfinite(v):
                    color = "white" if abs(v) > 0.6 * absmax else "black"
                    ax.text(j, i, f"{v:+.3f}", ha="center", va="center",
                            fontsize=8, color=color)
        # Highlight argmax cell
        if optimal[cond] and optimal[cond]["lam"] == main_lam:
            b = optimal[cond]
            bi = ALPHA_GRID.index(b["alpha"])
            bj = schemes_to_run.index(b["scheme"])
            ax.add_patch(plt.Rectangle((bj - 0.5, bi - 0.5), 1, 1,
                                        fill=False, edgecolor="black",
                                        linewidth=2.5, zorder=3))
        plt.colorbar(im, ax=ax, label="Δacc (aug − base)", shrink=0.8)

    fig.suptitle("Per-method calibration: LOO Δacc by (α, scheme)",
                 fontsize=12, y=1.02)
    plt.tight_layout()
    fig_path = out_dir / "calibration_sweep.png"
    plt.savefig(fig_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\nWrote: {fig_path}")

    # JSON
    json_path = out_dir / "calibration_sweep.json"
    with open(json_path, "w") as f:
        json.dump({
            "data_path": str(data_path),
            "alpha_grid": ALPHA_GRID,
            "lambda_grid": list(lambdas),
            "schemes": schemes_to_run,
            "n_per_condition": dict(cond_counts),
            "optimal_per_condition": optimal,
            "cells": {
                f"{cond}|{scheme}|{alpha}|{lam}": s
                for (cond, scheme, alpha, lam), s in cell_summary.items()
            },
        }, f, indent=2)
    print(f"Wrote: {json_path}")

    # Markdown summary
    md_path = out_dir / "calibration_summary.md"
    write_calibration_md(cell_summary, optimal, cond_counts,
                         schemes_to_run, ALPHA_GRID, lambdas,
                         md_path, data_path)
    print(f"Wrote: {md_path}")

    print()
    print("Reading guide:")
    print("  - The heatmap shows mean Δacc per (α, scheme) cell for each condition.")
    print("  - The black box marks the argmax cell.")
    print("  - α=0 should be exactly 0 across all schemes (sanity check).")
    print("  - Cells with overlapping CIs are statistically indistinguishable;")
    print("    the argmax has selection bias and may not be the true optimum.")


if __name__ == "__main__":
    main()
