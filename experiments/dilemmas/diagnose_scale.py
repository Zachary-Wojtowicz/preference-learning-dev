"""
Scale-mismatch diagnostic for the feedback prior.

Hypothesis: dim midpoints (the basis for beta_prior) live on the
raw_projection scale, which is O(0.01–0.2) for dailydilemmas. The fitted
beta from data alone (projection_only) lives on whatever scale makes
U @ beta produce logits of order 1, which given U values O(0.1) means
beta is O(10). If those scales are off by 50–100x, then mu_prior=2.0 is
effectively a strong shrinkage prior pulling beta toward ~zero, and we'd
expect projection_alpha to underperform projection_only — exactly what
we saw in the dry-run inference conditions.

This script prints, per inference-condition participant:
  - ||β_prior||₂          (built from their feedback)
  - ||β_no_prior||₂       (projection_only fit on all T trials)
  - ||β_with_prior||₂     (projection_alpha fit, mu=FEEDBACK_ALPHA)
  - ratio ||β_no_prior|| / ||β_prior||   — how big is the scale gap?
  - cos(β_no_prior, β_prior)             — does the prior point the right way?
  - max|·| of each — to check whether the gap is uniform or driven by tails.

Aggregates per condition and writes a JSON.

Run:
    python experiments/dilemmas/diagnose_scale.py
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

# Reuse the analysis pipeline
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from analyze import (  # noqa: E402
    load_qualtrics_csv, parse_participants, load_domain_assets,
    compute_dim_midpoints, build_design_matrices, build_beta_prior,
    fit_btl, is_complete,
    LAMBDA_PARTIAL, FEEDBACK_ALPHA,
    DATA_PATH, INFERENCE_CONDITIONS,
)


def cos_sim(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return float("nan")
    return float(np.dot(a, b) / (na * nb))


def diagnose_one(participant, domain_assets, midpoints):
    tp = domain_assets["trial_projections"]
    dim_ids = domain_assets["dim_ids"]
    categories = domain_assets["categories"]
    n_dims = domain_assets["n_dims"]

    out = build_design_matrices(participant, tp)
    if out is None:
        return None
    U, _, y = out

    bp = build_beta_prior(participant, dim_ids, midpoints, n_dims, categories,
                          train_indices=None)
    beta_no = fit_btl(U, y, lam=LAMBDA_PARTIAL, beta_prior=None, mu_prior=0.0)
    beta_w  = fit_btl(U, y, lam=LAMBDA_PARTIAL, beta_prior=bp,
                      mu_prior=FEEDBACK_ALPHA)

    n_norm_bp = float(np.linalg.norm(bp))
    n_norm_no = float(np.linalg.norm(beta_no))

    return {
        "pid": participant.get("participant_id"),
        "condition": participant.get("condition"),
        "n_visible_dims_with_feedback": int(np.sum(bp != 0)),
        "norm_beta_prior":      n_norm_bp,
        "norm_beta_no_prior":   n_norm_no,
        "norm_beta_with_prior": float(np.linalg.norm(beta_w)),
        "ratio_no_to_prior": (n_norm_no / n_norm_bp) if n_norm_bp > 1e-12 else float("inf"),
        "cos_no_prior_vs_prior": cos_sim(beta_no, bp),
        "max_abs_beta_prior":   float(np.max(np.abs(bp))),
        "max_abs_beta_no":      float(np.max(np.abs(beta_no))),
        "max_abs_beta_w":       float(np.max(np.abs(beta_w))),
        # Per-dim arrays kept in JSON, not printed
        "beta_prior":    bp.tolist(),
        "beta_no_prior": beta_no.tolist(),
        "beta_w_prior":  beta_w.tolist(),
    }


def fmt(x, spec=".3f"):
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "—" if x is None or np.isnan(x) else "inf"
    return format(x, spec)


def main():
    df = load_qualtrics_csv(DATA_PATH)
    participants = [p for p in parse_participants(df) if is_complete(p)]
    print(f"Loaded {len(participants)} complete participants "
          f"(filtering to inference conditions only)")

    # Load all domains in use
    domains = sorted({p.get("domain") for p in participants if p.get("domain")})
    domain_assets, midpoints = {}, {}
    for d in domains:
        a = load_domain_assets(d)
        domain_assets[d] = a
        midpoints[d] = compute_dim_midpoints(a["trial_projections"], a["dim_ids"])

    rows = []
    for p in participants:
        if p["condition"] not in INFERENCE_CONDITIONS:
            continue
        domain = p.get("domain")
        if domain not in domain_assets:
            continue
        r = diagnose_one(p, domain_assets[domain], midpoints[domain])
        if r is not None:
            rows.append(r)

    if not rows:
        print("No inference-condition participants found.")
        return

    # ----- Per-participant table -----
    print()
    print("=" * 118)
    print("PER-PARTICIPANT SCALE DIAGNOSTIC")
    print("=" * 118)
    print(f"  {'pid':<22} {'condition':<22} {'n_fb':>4} "
          f"{'||β_pri||':>10} {'||β_no||':>10} {'||β_w||':>10} "
          f"{'ratio':>8} {'cos':>7} "
          f"{'max|β_no|':>11} {'max|β_pri|':>11}")
    for r in rows:
        print(f"  {r['pid']:<22} {r['condition']:<22} "
              f"{r['n_visible_dims_with_feedback']:>4} "
              f"{fmt(r['norm_beta_prior']):>10} "
              f"{fmt(r['norm_beta_no_prior']):>10} "
              f"{fmt(r['norm_beta_with_prior']):>10} "
              f"{fmt(r['ratio_no_to_prior'], '.1f'):>8} "
              f"{fmt(r['cos_no_prior_vs_prior'], '+.2f'):>7} "
              f"{fmt(r['max_abs_beta_no']):>11} "
              f"{fmt(r['max_abs_beta_prior']):>11}")

    # ----- Per-condition aggregates -----
    print()
    print("=" * 118)
    print("PER-CONDITION SUMMARY")
    print("=" * 118)
    by_cond = defaultdict(list)
    for r in rows:
        by_cond[r["condition"]].append(r)

    summary_keys = [
        "norm_beta_prior",
        "norm_beta_no_prior",
        "norm_beta_with_prior",
        "ratio_no_to_prior",
        "cos_no_prior_vs_prior",
    ]
    for cond in INFERENCE_CONDITIONS:
        cond_rows = by_cond.get(cond) or []
        if not cond_rows:
            continue
        print(f"\n{cond}  (N={len(cond_rows)})")
        print(f"  {'metric':<26}  {'mean':>9} {'median':>9} {'min':>9} {'max':>9}")
        for k in summary_keys:
            vals = np.array([r[k] for r in cond_rows], dtype=float)
            vals = vals[np.isfinite(vals)]
            if len(vals) == 0:
                continue
            print(f"  {k:<26}  {vals.mean():>9.3f} {np.median(vals):>9.3f} "
                  f"{vals.min():>9.3f} {vals.max():>9.3f}")

    # ----- Interpretation -----
    print()
    print("=" * 118)
    print("INTERPRETATION")
    print("=" * 118)
    all_ratios = np.array([r["ratio_no_to_prior"] for r in rows], dtype=float)
    all_ratios = all_ratios[np.isfinite(all_ratios)]
    all_cos    = np.array([r["cos_no_prior_vs_prior"] for r in rows], dtype=float)
    all_cos    = all_cos[~np.isnan(all_cos)]

    if len(all_ratios):
        print(f"  Median ratio ||β_no_prior|| / ||β_prior||: {np.median(all_ratios):.1f}")
        print(f"    Interpretation:")
        print(f"      ~1     prior is on the right scale → mu_prior=2.0 reasonable")
        print(f"      ~10    moderate mismatch → mu_prior likely too aggressive")
        print(f"      ~100+  severe mismatch → prior shrinks β toward ~0, hurts fit")
    if len(all_cos):
        print()
        print(f"  Median cos(β_no_prior, β_prior): {np.median(all_cos):+.2f}")
        print(f"    Interpretation:")
        print(f"      close to +1   prior points the same direction as the data fit")
        print(f"      near 0        prior is uncorrelated with the right answer")
        print(f"      negative      prior actively points the wrong way")
        n_misaligned = int(np.sum(all_cos < 0))
        print(f"    {n_misaligned} of {len(all_cos)} participants have a misaligned prior "
              f"(cos < 0).")

    # ----- Save JSON -----
    out_dir = SCRIPT_DIR / "analysis_outputs"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "scale_diagnostic.json"
    with open(out_path, "w") as f:
        json.dump(rows, f, indent=2)
    print(f"\nWrote: {out_path}")


if __name__ == "__main__":
    main()
