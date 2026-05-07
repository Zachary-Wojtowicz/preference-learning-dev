"""
pilot_check.py — quick diagnostics for the movies pilot.

With a small N pilot, formal hypothesis testing is underpowered. This script
instead focuses on diagnostics that answer:

  1. Is the pipeline working end-to-end on movies data?
     (any malformed responses, missing trials, broken design matrices?)
  2. Is feedback actually being captured?
     (in inference conditions, are participants engaging with the UI?)
  3. Is the choice_only manipulation check directionally correct?
     (semantic projection > random projection)
  4. Is the deployed calibration (α=1, λ=0.005, quintile_midpoints) producing
     a positive lift, and does the pattern match what we saw on dilemmas?

Outputs:
    pilot_check_report.md  — shareable markdown report
    (also prints summary to stdout)

Usage:
    python experiments/pilot_check.py --data experiments/movies/data.csv
    python experiments/pilot_check.py --data experiments/movies_pilot/data.csv
"""

import argparse
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from analyze import (  # noqa: E402
    load_qualtrics_csv, parse_participants, load_domain_assets,
    build_design_matrices, build_beta_prior,
    fit_btl, fit_btl_with_rescaled_prior, predict_p_a, loo_accuracy,
    is_complete, t_ci,
    INFERENCE_CONDITIONS, CONDITIONS,
)
from calibrate_methods import midpoints_for_scheme  # noqa: E402


# ============================================================================
# Calibration cells to evaluate
# ============================================================================
# Each cell: (label, scheme, alpha, lam). The "_movies_deployed" cell is what
# the JS actually used at runtime; the rest are reference points.
CELLS = [
    {"label": "movies_deployed",         "scheme": "quintile_midpoints", "alpha": 1.0,  "lam": 0.005},
    {"label": "dilemmas_deployed",       "scheme": "quintile_midpoints", "alpha": 2.0,  "lam": 0.01 },
    {"label": "scheme_switch_only",      "scheme": "linear_uniform",     "alpha": 1.0,  "lam": 0.005},
    {"label": "dilemmas_optimum",        "scheme": "linear_uniform",     "alpha": 0.3,  "lam": 0.001},
]

COND_LABELS = {
    "choice_only":          "Choice only",
    "inference_affirm":     "Affirm/remove",
    "inference_categories": "Category select",
}


# ============================================================================
# Diagnostics
# ============================================================================
def data_integrity(participants_all, participants_kept):
    """Tallies + integrity checks. Returns dict of stats."""
    excluded = len(participants_all) - len(participants_kept)
    cond_counts = defaultdict(int)
    domain_counts = defaultdict(int)
    durations = []
    for p in participants_kept:
        cond_counts[p.get("condition", "?")] += 1
        domain_counts[p.get("domain", "?")] += 1
        d = p.get("_qualtrics_duration_s")
        try:
            d = float(d)
            if d > 0:
                durations.append(d)
        except (TypeError, ValueError):
            pass
    # Choice balance per condition (% chose A)
    pct_a_by_cond = {}
    for cond in CONDITIONS:
        pct_a = []
        for p in participants_kept:
            if p.get("condition") != cond:
                continue
            resps = p.get("responses") or []
            if not resps:
                continue
            n_a = sum(1 for r in resps if r.get("chosen") == "a")
            pct_a.append(n_a / len(resps))
        if pct_a:
            pct_a_by_cond[cond] = (float(np.mean(pct_a)), float(np.std(pct_a, ddof=1)) if len(pct_a) > 1 else 0.0)

    return {
        "n_total": len(participants_all),
        "n_complete": len(participants_kept),
        "n_excluded": excluded,
        "cond_counts": dict(cond_counts),
        "domain_counts": dict(domain_counts),
        "duration_s_mean": float(np.mean(durations)) if durations else None,
        "duration_s_median": float(np.median(durations)) if durations else None,
        "pct_a_by_cond": pct_a_by_cond,
    }


def feedback_engagement(participants_kept):
    """For inference participants, summarize how often they engaged with
    the feedback UI vs left things at defaults / zeroed them out."""
    out = {}
    for cond in INFERENCE_CONDITIONS:
        p_in_cond = [p for p in participants_kept if p.get("condition") == cond]
        if not p_in_cond:
            out[cond] = None
            continue
        # Per participant: fraction of inference items with action != "remove" / "none"
        engagement_per_p = []
        nontrivial_priors = []  # how many participants produced non-zero priors
        for p in p_in_cond:
            n_items = 0
            n_nonremove = 0
            for r in (p.get("responses") or []):
                iv = r.get("inference_values") or {}
                for did, info in iv.items():
                    n_items += 1
                    action = (info or {}).get("action", "none")
                    if action != "remove" and action != "none":
                        n_nonremove += 1
            if n_items > 0:
                engagement_per_p.append(n_nonremove / n_items)
            # Did this participant produce ANY non-zero feedback?
            any_nontrivial = n_nonremove > 0
            nontrivial_priors.append(any_nontrivial)
        out[cond] = {
            "n_participants":           len(p_in_cond),
            "n_with_any_feedback":      int(sum(nontrivial_priors)),
            "frac_with_any_feedback":   float(np.mean(nontrivial_priors)) if nontrivial_priors else 0.0,
            "mean_engagement_rate":     float(np.mean(engagement_per_p)) if engagement_per_p else 0.0,
        }
    return out


def per_participant_loo(participant, domain_assets, midpoints_by_cell):
    """For one participant, return LOO accuracies under each cell:
        {cell_label: {"random_projection": acc, "projection_only": acc,
                       "projection_alpha": acc_or_None}}.
    The random_projection / projection_only accuracies depend only on λ, so
    they're shared across cells with the same λ."""
    tp = domain_assets["trial_projections"]
    dim_ids = domain_assets["dim_ids"]
    categories = domain_assets["categories"]
    n_dims = domain_assets["n_dims"]
    cond = participant.get("condition", "")
    is_inf = cond in INFERENCE_CONDITIONS

    out = build_design_matrices(participant, tp)
    if out is None:
        return None
    U, U_rand, y = out

    # Cache LOO results by λ (for random/projection_only) since cells differ.
    base_cache = {}
    results = {}
    for cell in CELLS:
        lam = cell["lam"]
        if lam not in base_cache:
            loo_rp = loo_accuracy(U_rand, y, lam=lam,
                                   beta_prior_fn=None, mu_prior=0.0)
            loo_po = loo_accuracy(U,      y, lam=lam,
                                   beta_prior_fn=None, mu_prior=0.0)
            base_cache[lam] = (loo_rp, loo_po)
        loo_rp, loo_po = base_cache[lam]

        loo_pa = None
        if is_inf:
            mids = midpoints_by_cell[cell["label"]]
            bp_fn = lambda idxs, _mids=mids: build_beta_prior(
                participant, dim_ids, _mids, n_dims, categories,
                train_indices=idxs)
            loo_pa = loo_accuracy(U, y, lam=lam,
                                   beta_prior_fn=bp_fn, mu_prior=cell["alpha"],
                                   rescale_prior=True)
        results[cell["label"]] = {
            "random_projection": loo_rp,
            "projection_only":   loo_po,
            "projection_alpha":  loo_pa,
        }
    return results


def aggregate_by_condition(participants_kept, domain_assets,
                            midpoints_by_cell_by_domain):
    """Returns nested: results[cell_label][cond][model] = list of per-participant accs."""
    results = {cell["label"]: {cond: defaultdict(list) for cond in CONDITIONS}
               for cell in CELLS}
    for p in participants_kept:
        cond = p.get("condition")
        domain = p.get("domain")
        if cond not in CONDITIONS or domain not in domain_assets:
            continue
        midpoints_by_cell = {label: m_by_dom[domain]
                              for label, m_by_dom in midpoints_by_cell_by_domain.items()}
        per_p = per_participant_loo(p, domain_assets[domain], midpoints_by_cell)
        if per_p is None:
            continue
        for cell_label, models in per_p.items():
            for model, acc in models.items():
                if acc is not None:
                    results[cell_label][cond][model].append(acc)
    return results


# ============================================================================
# Reporting
# ============================================================================
def fmt_mean_ci(vals, dec=3):
    if not vals:
        return "—"
    mean, hw = t_ci(vals)
    if len(vals) < 2:
        return f"{mean:+.{dec}f}  (N=1)"
    return f"{mean:+.{dec}f}  [{mean - hw:+.{dec}f}, {mean + hw:+.{dec}f}]  (N={len(vals)})"


def fmt_acc(vals, dec=3):
    if not vals:
        return "—"
    mean = float(np.mean(vals))
    if len(vals) < 2:
        return f"{mean:.{dec}f}  (N=1)"
    _, hw = t_ci(vals)
    return f"{mean:.{dec}f}  [{mean - hw:.{dec}f}, {mean + hw:.{dec}f}]  (N={len(vals)})"


def write_report(stats, engage, results, out_path, data_path):
    L = []
    L.append("# Movies pilot — quick check")
    L.append("")
    L.append(f"_Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} from `{Path(data_path).name}`._")
    L.append("")
    L.append("Small-N diagnostic. Numbers are point estimates with 95% t-CIs where N>1; "
             "no inferential testing — sample size is too small.")
    L.append("")
    L.append("## 1. Data integrity")
    L.append("")
    L.append(f"- Total responses: **{stats['n_total']}**")
    L.append(f"- Complete (passed inclusion): **{stats['n_complete']}** "
             f"(excluded {stats['n_excluded']})")
    if stats["domain_counts"]:
        domains_str = ", ".join(f"{d}: {n}" for d, n in stats["domain_counts"].items())
        L.append(f"- Domains: {domains_str}")
    if stats["duration_s_median"]:
        L.append(f"- Duration (s): median={stats['duration_s_median']:.0f}, "
                 f"mean={stats['duration_s_mean']:.0f}")
    L.append("")
    L.append("**Per-condition counts and choice balance:**")
    L.append("")
    L.append("| Condition | N | mean % chose A | sd |")
    L.append("|---|---|---|---|")
    for cond in CONDITIONS:
        n = stats["cond_counts"].get(cond, 0)
        if cond in stats["pct_a_by_cond"]:
            mean_a, sd_a = stats["pct_a_by_cond"][cond]
            L.append(f"| {COND_LABELS[cond]} | {n} | {mean_a*100:.1f}% | {sd_a*100:.1f}% |")
        else:
            L.append(f"| {COND_LABELS[cond]} | {n} | — | — |")
    L.append("")
    L.append("Sanity: mean % A should be near 50% (no display-side bias). "
             "Within-participant SD of choices is not shown here.")
    L.append("")

    L.append("## 2. Feedback engagement (inference conditions)")
    L.append("")
    L.append("| Condition | N | participants who gave any feedback | mean engagement rate |")
    L.append("|---|---|---|---|")
    for cond in INFERENCE_CONDITIONS:
        e = engage.get(cond)
        if e is None:
            L.append(f"| {COND_LABELS[cond]} | 0 | — | — |")
            continue
        L.append(f"| {COND_LABELS[cond]} | {e['n_participants']} | "
                 f"{e['n_with_any_feedback']}/{e['n_participants']} "
                 f"({e['frac_with_any_feedback']*100:.0f}%) | "
                 f"{e['mean_engagement_rate']*100:.1f}% |")
    L.append("")
    L.append("Engagement rate = fraction of inference items where action ≠ 'remove'/'none'. "
             "Low values mean the prior collapses toward 0 → projection_alpha ≈ projection_only.")
    L.append("")

    L.append("## 3. LOO accuracy at each parameter cell")
    L.append("")
    L.append("Each cell defines (scheme, α, λ) used to compute the feedback prior and "
             "fit BTL. `random_projection` and `projection_only` depend only on λ, so they "
             "are shared across cells with the same λ. `projection_alpha` is the augmented "
             "model that uses the feedback prior.")
    L.append("")
    L.append("| Cell label | scheme | α | λ |")
    L.append("|---|---|---|---|")
    for cell in CELLS:
        L.append(f"| `{cell['label']}` | `{cell['scheme']}` | {cell['alpha']} | {cell['lam']} |")
    L.append("")

    # 3a. choice_only manipulation check (depends only on λ)
    L.append("### 3a. Choice-only manipulation check")
    L.append("")
    L.append("Does the LLM-derived semantic projection beat random projection? "
             "Independent of (scheme, α). Reported per λ used in this sweep.")
    L.append("")
    L.append("| λ | random_projection | projection_only | lift (proj_only − random) |")
    L.append("|---|---|---|---|")
    seen_lams = set()
    for cell in CELLS:
        lam = cell["lam"]
        if lam in seen_lams:
            continue
        seen_lams.add(lam)
        rp = results[cell["label"]]["choice_only"].get("random_projection", [])
        po = results[cell["label"]]["choice_only"].get("projection_only", [])
        if rp and po and len(rp) == len(po):
            diffs = [p - r for p, r in zip(po, rp)]
            L.append(f"| {lam} | {fmt_acc(rp)} | {fmt_acc(po)} | {fmt_mean_ci(diffs)} |")
        else:
            L.append(f"| {lam} | — | — | — |")
    L.append("")

    # 3b. Per-cell projection_alpha lift in inference conditions
    L.append("### 3b. Inference conditions: projection_alpha vs projection_only")
    L.append("")
    L.append("This is the headline calibration check. The lift = "
             "projection_alpha − projection_only at each cell. Positive = the prior "
             "is helping. With small N the CIs will be wide; look at point estimates "
             "and direction-of-effect.")
    L.append("")
    for cond in INFERENCE_CONDITIONS:
        L.append(f"**{COND_LABELS[cond]}**")
        L.append("")
        L.append("| Cell | projection_only | projection_alpha | Lift |")
        L.append("|---|---|---|---|")
        for cell in CELLS:
            r = results[cell["label"]][cond]
            po = r.get("projection_only", [])
            pa = r.get("projection_alpha", [])
            if po and pa and len(po) == len(pa):
                diffs = [a - b for a, b in zip(pa, po)]
                L.append(f"| `{cell['label']}` | {fmt_acc(po)} | {fmt_acc(pa)} | {fmt_mean_ci(diffs)} |")
            else:
                L.append(f"| `{cell['label']}` | — | — | — |")
        L.append("")

    L.append("## 4. Reading guide")
    L.append("")
    L.append("**Pipeline working** if:")
    L.append("- (1) reports show participants distributed across conditions and complete=N_total")
    L.append("- (2) shows engagement rate >50% in inference cells (else feedback isn't reaching the model)")
    L.append("- (3a) choice-only lift is positive (manipulation check transfers from dilemmas)")
    L.append("")
    L.append("**Calibration on target** if:")
    L.append("- The `movies_deployed` cell shows a positive lift in inference conditions")
    L.append("- The `dilemmas_optimum` cell ≈ or > the `movies_deployed` cell "
             "(suggesting the dilemmas optimum transfers)")
    L.append("- The `scheme_switch_only` cell ≥ the `movies_deployed` cell "
             "(suggesting linear_uniform > quintile_midpoints holds for movies too)")
    L.append("")
    L.append("**Caveats:**")
    L.append("- With small N, CIs will be wide and signs may flip on noise.")
    L.append("- This is *not* an inferential test — just a directional sanity check.")
    L.append("- Any clearly negative lift across multiple cells suggests something is "
             "broken upstream (data, JS, prior construction); investigate before scaling.")
    L.append("")

    with open(out_path, "w") as f:
        f.write("\n".join(L))


# ============================================================================
# Main
# ============================================================================
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True,
                        help="Path to the Qualtrics CSV (e.g. "
                             "experiments/movies/data.csv)")
    parser.add_argument("--out", default=None,
                        help="Output path for the markdown report. "
                             "Default: <data parent>/pilot_check_report.md")
    args = parser.parse_args()

    data_path = Path(args.data).resolve()
    if args.out is None:
        out_path = data_path.parent / "pilot_check_report.md"
    else:
        out_path = Path(args.out).resolve()

    print(f"Reading {data_path}")
    df = load_qualtrics_csv(data_path)
    parsed = parse_participants(df)
    kept = [p for p in parsed if is_complete(p)]
    print(f"  {len(parsed)} parsed responses, {len(kept)} complete\n")

    if not kept:
        print("No complete participants — nothing to analyze.")
        return

    stats = data_integrity(parsed, kept)
    engage = feedback_engagement(kept)

    # Load domain assets and precompute midpoints per cell per domain
    domains = sorted({p.get("domain") for p in kept if p.get("domain")})
    print(f"Loading domain assets: {domains}")
    domain_assets = {d: load_domain_assets(d) for d in domains}
    midpoints_by_cell_by_domain = {}
    for cell in CELLS:
        midpoints_by_cell_by_domain[cell["label"]] = {
            d: midpoints_for_scheme(cell["scheme"], domain_assets[d]["dim_ids"],
                                     domain_assets[d]["trial_projections"])
            for d in domains
        }

    print("Computing LOO at each cell ...")
    results = aggregate_by_condition(kept, domain_assets, midpoints_by_cell_by_domain)

    # Quick stdout summary
    print()
    print("=" * 70)
    print("PILOT CHECK SUMMARY")
    print("=" * 70)
    print(f"\nSample: N={stats['n_complete']} complete")
    for c in CONDITIONS:
        n = stats["cond_counts"].get(c, 0)
        print(f"  {c}: {n}")
    print()
    for c in INFERENCE_CONDITIONS:
        e = engage.get(c)
        if e:
            print(f"  Feedback engagement in {c}: "
                  f"{e['n_with_any_feedback']}/{e['n_participants']} pp gave any, "
                  f"mean rate = {e['mean_engagement_rate']*100:.1f}%")
    print()
    print("Choice-only lift (proj_only − random) by λ:")
    seen = set()
    for cell in CELLS:
        if cell["lam"] in seen:
            continue
        seen.add(cell["lam"])
        rp = results[cell["label"]]["choice_only"].get("random_projection", [])
        po = results[cell["label"]]["choice_only"].get("projection_only", [])
        if rp and po and len(rp) == len(po):
            diffs = [p - r for p, r in zip(po, rp)]
            print(f"  λ={cell['lam']}: {fmt_mean_ci(diffs)}")

    print("\nInference lift (proj_alpha − proj_only) per cell:")
    for cond in INFERENCE_CONDITIONS:
        print(f"  {cond}:")
        for cell in CELLS:
            r = results[cell["label"]][cond]
            po = r.get("projection_only", [])
            pa = r.get("projection_alpha", [])
            if po and pa and len(po) == len(pa):
                diffs = [a - b for a, b in zip(pa, po)]
                print(f"    {cell['label']:25s}: {fmt_mean_ci(diffs)}")

    write_report(stats, engage, results, out_path, data_path)
    print(f"\nWrote: {out_path}")


if __name__ == "__main__":
    main()
