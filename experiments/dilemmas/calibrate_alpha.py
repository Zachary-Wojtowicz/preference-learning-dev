"""
α-calibration sweep for the feedback prior.

Sweeps mu_prior (= α) over a grid and reports the per-condition mean LOO
accuracy lift (projection_alpha − projection_only) on inference-condition
participants. Identifies the α̂ that maximizes pooled mean lift.

After the rescaling fix in analyze.py:
  - At α=0, projection_alpha == projection_only by definition (sanity check
    that should print exactly Δacc=0).
  - The expected curve shape is an inverted U: rises from 0 at α=0, peaks
    at some α̂, then decays as the prior overwhelms the data.
  - If the curve never rises above 0, the prior isn't helping at any α
    and the issue is feedback quality, not tuning.

Usage:
    python experiments/dilemmas/calibrate_alpha.py
    python experiments/dilemmas/calibrate_alpha.py --data path/to/new_pilot.csv

Reuses the helpers from analyze.py (so the rescaling and prior construction
stay synchronized with the main analysis).
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from analyze import (  # noqa: E402
    load_qualtrics_csv, parse_participants, load_domain_assets,
    compute_dim_midpoints, build_design_matrices, build_beta_prior,
    loo_accuracy, is_complete,
    LAMBDA_PARTIAL, N_CATS,
    DATA_PATH, INFERENCE_CONDITIONS,
)


# Compact grid spanning ~4 orders of magnitude. α=0 is the critical sanity
# check (Δacc must be exactly 0 there, post-rescaling). Coverage is dense
# in [0.1, 3.0] where the optimum is most likely to sit given the diagnostic.
ALPHA_GRID = [0.0, 0.01, 0.03, 0.1, 0.3, 1.0, 2.0, 5.0]

# Color/label mapping
COND_LABELS = {
    "inference_affirm":     "Affirm/remove",
    "inference_categories": "Category select",
}
COND_COLORS = {
    "inference_affirm":     "#3b82f6",
    "inference_categories": "#10b981",
}


def loo_at_alpha(participant, domain_assets, midpoints, alpha):
    """Return (loo_proj_only, loo_proj_alpha) for one participant at one α.

    Always uses rescale_prior=True (the post-fix behavior). At α=0, the
    augmented fit reduces to projection_only and (loo_aug - loo_base) is
    exactly 0."""
    tp = domain_assets["trial_projections"]
    dim_ids = domain_assets["dim_ids"]
    categories = domain_assets["categories"]
    n_dims = domain_assets["n_dims"]

    out = build_design_matrices(participant, tp)
    if out is None:
        return None, None
    U, _, y = out

    # projection_only baseline (α=0 collapses to this)
    loo_base = loo_accuracy(U, y, lam=LAMBDA_PARTIAL,
                             beta_prior_fn=None, mu_prior=0.0)

    if alpha <= 0:
        # By construction, augmented = baseline at α=0.
        return loo_base, loo_base

    bp_fn = lambda idxs: build_beta_prior(
        participant, dim_ids, midpoints, n_dims, categories, train_indices=idxs)
    loo_aug = loo_accuracy(U, y, lam=LAMBDA_PARTIAL,
                            beta_prior_fn=bp_fn, mu_prior=alpha,
                            rescale_prior=True)
    return loo_base, loo_aug


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(DATA_PATH),
                        help=f"Qualtrics CSV path (default: {DATA_PATH})")
    parser.add_argument("--out-dir", default=str(SCRIPT_DIR / "analysis_outputs"),
                        help="Where to write figures and JSON.")
    args = parser.parse_args()

    data_path = Path(args.data).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(exist_ok=True, parents=True)

    print(f"Reading {data_path}")
    df = load_qualtrics_csv(data_path)
    participants = [p for p in parse_participants(df) if is_complete(p)]
    inf_p = [p for p in participants if p["condition"] in INFERENCE_CONDITIONS]
    print(f"  {len(participants)} complete participants total, "
          f"{len(inf_p)} in inference conditions")
    cond_counts = defaultdict(int)
    for p in inf_p:
        cond_counts[p["condition"]] += 1
    for c in INFERENCE_CONDITIONS:
        print(f"    {c}: N = {cond_counts[c]}")

    # Load domain assets
    domains = sorted({p.get("domain") for p in inf_p if p.get("domain")})
    domain_assets, midpoints = {}, {}
    for d in domains:
        a = load_domain_assets(d)
        domain_assets[d] = a
        midpoints[d] = compute_dim_midpoints(a["trial_projections"], a["dim_ids"])

    # Sweep
    # results[alpha][condition] -> list of dicts {pid, loo_base, loo_aug, diff}
    results = defaultdict(lambda: defaultdict(list))
    print(f"\nSweeping α over {ALPHA_GRID} ...")
    for alpha in ALPHA_GRID:
        for p in inf_p:
            domain = p.get("domain")
            if domain not in domain_assets:
                continue
            base, aug = loo_at_alpha(p, domain_assets[domain],
                                      midpoints[domain], alpha)
            if base is None:
                continue
            results[alpha][p["condition"]].append({
                "pid": p.get("participant_id"),
                "loo_base": base, "loo_aug": aug, "diff": aug - base,
            })
        n_done = sum(len(v) for v in results[alpha].values())
        print(f"  α = {alpha:>7.3f}  (N evaluated = {n_done})")

    # Aggregate: per-(alpha,condition) and pooled
    summary = {}
    for alpha in ALPHA_GRID:
        cell = {}
        all_diffs = []
        for cond in INFERENCE_CONDITIONS:
            rows = results[alpha].get(cond, [])
            diffs = np.array([r["diff"] for r in rows]) if rows else np.array([])
            if len(diffs) == 0:
                cell[cond] = {"n": 0, "mean_diff": None, "sem": None,
                              "mean_aug": None, "mean_base": None}
                continue
            cell[cond] = {
                "n": int(len(diffs)),
                "mean_diff": float(diffs.mean()),
                "sem": float(diffs.std(ddof=1) / np.sqrt(len(diffs)))
                       if len(diffs) > 1 else 0.0,
                "mean_aug":  float(np.mean([r["loo_aug"]  for r in rows])),
                "mean_base": float(np.mean([r["loo_base"] for r in rows])),
            }
            all_diffs.extend(diffs.tolist())
        if all_diffs:
            arr = np.array(all_diffs)
            cell["pooled"] = {
                "n": int(len(arr)),
                "mean_diff": float(arr.mean()),
                "sem": float(arr.std(ddof=1) / np.sqrt(len(arr)))
                       if len(arr) > 1 else 0.0,
            }
        else:
            cell["pooled"] = {"n": 0, "mean_diff": None, "sem": None}
        summary[alpha] = cell

    # Print table
    print()
    print("=" * 78)
    print("α SWEEP — H1 LOO accuracy lift (projection_alpha − projection_only)")
    print("=" * 78)
    print(f"  {'α':>7}  {'cond':<22} {'N':>3} {'Δacc':>9} {'SEM':>8} "
          f"{'aug':>7} {'base':>7}")
    for alpha in ALPHA_GRID:
        for cond in INFERENCE_CONDITIONS:
            r = summary[alpha].get(cond, {})
            if not r.get("n"):
                continue
            print(f"  {alpha:>7.3f}  {cond:<22} {r['n']:>3} "
                  f"{r['mean_diff']:>+9.4f} {r['sem']:>8.4f} "
                  f"{r['mean_aug']:>7.3f} {r['mean_base']:>7.3f}")
        rp = summary[alpha].get("pooled", {})
        if rp.get("n"):
            print(f"  {alpha:>7.3f}  {'POOLED':<22} {rp['n']:>3} "
                  f"{rp['mean_diff']:>+9.4f} {rp['sem']:>8.4f}")
        print()

    # Sanity check at α=0
    pooled_at_zero = summary[0.0]["pooled"]["mean_diff"]
    if pooled_at_zero is not None and abs(pooled_at_zero) > 1e-9:
        print(f"  ⚠ WARNING: at α=0, pooled Δacc = {pooled_at_zero:.6f} "
              "(should be exactly 0). Possible bug in rescaling/LOO.")
    else:
        print(f"  ✓ Sanity check: pooled Δacc(α=0) = 0 (exact).")

    # Identify pooled argmax
    valid_alphas = [a for a in ALPHA_GRID
                    if summary[a]["pooled"]["mean_diff"] is not None]
    if valid_alphas:
        best_alpha = max(valid_alphas,
                         key=lambda a: summary[a]["pooled"]["mean_diff"])
        best_lift = summary[best_alpha]["pooled"]["mean_diff"]
        print(f"  Pooled argmax: α̂ = {best_alpha}, "
              f"mean Δacc = {best_lift:+.4f}")
        if best_lift <= 0:
            print(f"  ⚠ Best α gives non-positive lift — prior isn't helping "
                  "at any swept value.")
    else:
        best_alpha = None

    # ------------------------------------------------------------------ figure
    fig, ax = plt.subplots(figsize=(9, 5.5))

    # x-axis fudge: log scale can't show 0; place α=0 at 1e-3 visually.
    def x_for(a):
        return a if a > 0 else 1e-3

    # Per-condition curves
    for cond in INFERENCE_CONDITIONS:
        means = [summary[a][cond].get("mean_diff") for a in ALPHA_GRID]
        sems  = [summary[a][cond].get("sem", 0) or 0 for a in ALPHA_GRID]
        means = [m if m is not None else np.nan for m in means]
        ax.errorbar([x_for(a) for a in ALPHA_GRID], means, yerr=sems,
                    marker="o", capsize=3, linewidth=1.8, markersize=6,
                    color=COND_COLORS[cond], label=COND_LABELS[cond],
                    alpha=0.85)

    # Pooled curve (heavier)
    pooled_means = [summary[a]["pooled"].get("mean_diff") for a in ALPHA_GRID]
    pooled_sems  = [summary[a]["pooled"].get("sem", 0) or 0 for a in ALPHA_GRID]
    pooled_means = [m if m is not None else np.nan for m in pooled_means]
    ax.errorbar([x_for(a) for a in ALPHA_GRID], pooled_means, yerr=pooled_sems,
                marker="s", capsize=4, linewidth=2.5, markersize=8,
                color="#1a1a1a", label="Pooled", zorder=10)

    ax.set_xscale("log")
    ax.set_xlabel("α  (mu_prior)")
    ax.set_ylabel("Mean LOO Δacc  (projection_alpha − projection_only)")
    ax.axhline(0, color="black", linewidth=0.6, linestyle="--", alpha=0.4)

    if best_alpha is not None and best_alpha > 0:
        ax.axvline(best_alpha, color="#dc2626", linewidth=1.0, linestyle=":",
                   alpha=0.7,
                   label=f"α̂ = {best_alpha} (Δ={summary[best_alpha]['pooled']['mean_diff']:+.3f})")

    # Annotate the α=0 sanity-check point
    if pooled_at_zero is not None:
        ax.annotate("α=0\n(sanity)", xy=(1e-3, pooled_at_zero),
                    xytext=(1.3e-3, pooled_at_zero - 0.03),
                    fontsize=8, color="#666",
                    arrowprops=dict(arrowstyle="-", color="#999", lw=0.5))

    n_inf = len(inf_p)
    ax.set_title(f"α sweep on pilot data (post-rescaling, N={n_inf} "
                 f"inference participants)")
    ax.legend(loc="best", framealpha=0.9, fontsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig_path = out_dir / "alpha_sweep.png"
    plt.tight_layout()
    plt.savefig(fig_path, dpi=150, bbox_inches="tight")
    plt.close()

    # Save JSON
    json_path = out_dir / "alpha_sweep.json"
    with open(json_path, "w") as f:
        json.dump({
            "data_path": str(data_path),
            "alpha_grid": ALPHA_GRID,
            "n_inference_participants": len(inf_p),
            "n_per_condition": dict(cond_counts),
            "best_alpha_pooled": best_alpha,
            "summary": summary,
            # Per-participant rows for downstream re-analysis
            "per_alpha": {
                str(a): {cond: results[a][cond] for cond in INFERENCE_CONDITIONS}
                for a in ALPHA_GRID
            },
        }, f, indent=2)

    print(f"\nWrote: {fig_path}")
    print(f"Wrote: {json_path}")
    print()
    print("Curve interpretation (post-rescaling):")
    print("  - Δacc(α=0) should be exactly 0 (and is shown for sanity)")
    print("  - Inverted-U with peak in [0.1, 3] — typical, picks the right α")
    print("  - Monotonic decline from α=0 — feedback is hurting at all α; "
          "tuning won't fix it")
    print("  - Peak very close to α=0 with small lift — feedback adds little")
    print("  - Peak far above 2 — would surprise me; investigate")


if __name__ == "__main__":
    main()
