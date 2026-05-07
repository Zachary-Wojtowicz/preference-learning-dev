#!/usr/bin/env python3
"""Aggregate metrics from the alpha sweep simulation outputs.

For each (alpha_affirm, alpha_categories) cell, extracts:
  - LOO accuracy of projection_alpha for each condition
  - Spearman of projection_alpha vs ground truth
  - Predicted DV mean (rating: partial preferred over standard)
  - LLM proj advantage over random (delta acc)

Produces three matrices: one for each metric of interest, indexed by
(alpha_affirm, alpha_categories). The diagonal of the matrix recovers
the symmetric case (alpha_affirm = alpha_categories).

Usage: python simulation/analyze_alpha_sweep.py [sweep_dir]
"""

import re
import sys
from pathlib import Path
from collections import defaultdict


def parse_summary(path):
    """Parse the relevant tables from a summary.md file."""
    text = path.read_text()
    out = {}

    # Predicted Rating
    pred_match = re.search(
        r'## Predicted Rating.*?\n\| Condition \|.*?\n\|.*?\n((?:\|.*?\n)+)',
        text, re.DOTALL)
    if pred_match:
        for line in pred_match.group(1).strip().split('\n'):
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if len(cells) < 2:
                continue
            cond, m, sd, pct = cells[0], cells[1], cells[2], cells[3]
            try:
                out[f'{cond}_dv_mean'] = float(m)
            except ValueError:
                pass

    # Summary-Quality Means table
    sq_match = re.search(
        r'## Summary-Quality Means.*?\n\| Condition \|.*?\n\|.*?\n((?:\|.*?\n)+)',
        text, re.DOTALL)
    if sq_match:
        for line in sq_match.group(1).strip().split('\n'):
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if len(cells) < 6:
                continue
            cond, fit, spearman, topn_sign, topn_overlap, combined = cells[:6]
            try:
                key = f'{cond}_{fit}_spearman'
                out[key] = float(spearman)
            except ValueError:
                pass

    # LOO Choice Accuracy table
    acc_match = re.search(
        r'## LOO Choice Accuracy at T.*?\n\| Condition \|.*?\n\|.*?\n((?:\|.*?\n)+)',
        text, re.DOTALL)
    if acc_match:
        for line in acc_match.group(1).strip().split('\n'):
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if len(cells) < 4:
                continue
            cond, rand, proj, alpha = cells[0], cells[1], cells[2], cells[3]
            try:
                out[f'{cond}_acc_random'] = float(rand)
                out[f'{cond}_acc_proj'] = float(proj)
                out[f'{cond}_acc_alpha'] = float(alpha)
            except ValueError:
                pass

    return out


def main():
    sweep_dir = Path(sys.argv[1] if len(sys.argv) > 1
                     else 'simulation/outputs/dailydilemmas_sweep')
    if not sweep_dir.exists():
        print(f"Error: {sweep_dir} not found")
        sys.exit(1)

    # Parse all cells
    grid = {}
    cells = sorted([d for d in sweep_dir.iterdir() if d.is_dir()])
    for cell in cells:
        m = re.match(r'a([\d.]+)_c([\d.]+)', cell.name)
        if not m:
            continue
        aa = float(m.group(1))
        ac = float(m.group(2))
        summary = cell / 'summary.md'
        if not summary.exists():
            continue
        grid[(aa, ac)] = parse_summary(summary)

    if not grid:
        print(f"No cells parsed under {sweep_dir}")
        sys.exit(1)

    alphas_a = sorted(set(k[0] for k in grid))
    alphas_c = sorted(set(k[1] for k in grid))

    def heatmap(metric_key, label, decimals=3):
        print(f"\n=== {label} ===")
        # Header
        header = "α_affirm \\ α_cat |" + " ".join(f"{a:>7.2f}" for a in alphas_c)
        print(header)
        print("-" * len(header))
        for aa in alphas_a:
            row = f"     α_a={aa:<7.2f} |"
            for ac in alphas_c:
                v = grid.get((aa, ac), {}).get(metric_key)
                if v is None:
                    row += "       –"
                else:
                    row += f" {v:>7.{decimals}f}"
            print(row)

    print(f"Sweep directory: {sweep_dir}")
    print(f"Cells: {len(grid)}")
    print(f"alpha_affirm values: {alphas_a}")
    print(f"alpha_categories values: {alphas_c}")

    # ----- inference_affirm: depends on alpha_affirm ONLY -----
    heatmap("inference_affirm_acc_alpha",
            "inference_affirm: LOO acc (proj_alpha)")
    heatmap("inference_affirm_inference_affirm_spearman",
            "inference_affirm: Spearman (proj_alpha) — note this is sometimes blank if name collapsed")
    # Probably the cond_fit_spearman key uses different formatting; let me try alt
    heatmap("inference_affirm_projection_alpha_spearman",
            "inference_affirm: Spearman of projection_alpha")
    heatmap("inference_affirm_dv_mean",
            "inference_affirm: predicted DV mean")

    # ----- inference_categories: depends on alpha_categories ONLY -----
    heatmap("inference_categories_acc_alpha",
            "inference_categories: LOO acc (proj_alpha)")
    heatmap("inference_categories_projection_alpha_spearman",
            "inference_categories: Spearman of projection_alpha")
    heatmap("inference_categories_dv_mean",
            "inference_categories: predicted DV mean")

    # ----- choice_only: should be invariant to BOTH alphas -----
    heatmap("choice_only_acc_alpha",
            "choice_only: LOO acc (proj_alpha) — should be ~constant (no feedback)")
    heatmap("choice_only_acc_proj",
            "choice_only: LOO acc (proj_only) — should be ~constant")

    # ----- 1D summaries: best alpha for each condition -----
    print("\n=== Optimal alpha per condition (mean over the OTHER alpha) ===")

    # For inference_affirm, average across alpha_categories (which shouldn't matter)
    aff_acc = {}
    aff_sp = {}
    for aa in alphas_a:
        accs, sps = [], []
        for ac in alphas_c:
            d = grid.get((aa, ac), {})
            if 'inference_affirm_acc_alpha' in d:
                accs.append(d['inference_affirm_acc_alpha'])
            if 'inference_affirm_projection_alpha_spearman' in d:
                sps.append(d['inference_affirm_projection_alpha_spearman'])
        if accs: aff_acc[aa] = sum(accs) / len(accs)
        if sps: aff_sp[aa] = sum(sps) / len(sps)

    # For inference_categories, average across alpha_affirm (which shouldn't matter)
    cat_acc = {}
    cat_sp = {}
    for ac in alphas_c:
        accs, sps = [], []
        for aa in alphas_a:
            d = grid.get((aa, ac), {})
            if 'inference_categories_acc_alpha' in d:
                accs.append(d['inference_categories_acc_alpha'])
            if 'inference_categories_projection_alpha_spearman' in d:
                sps.append(d['inference_categories_projection_alpha_spearman'])
        if accs: cat_acc[ac] = sum(accs) / len(accs)
        if sps: cat_sp[ac] = sum(sps) / len(sps)

    print("\nINFERENCE_AFFIRM (averaged across alpha_categories):")
    print(f"{'alpha_affirm':>12} | {'LOO acc':>8} | {'Spearman':>9}")
    for aa in alphas_a:
        a = aff_acc.get(aa)
        s = aff_sp.get(aa)
        print(f"{aa:>12.2f} | {a:>8.3f} | {s:>9.3f}"
              if a is not None and s is not None else f"{aa:>12.2f} | -- | --")
    if aff_acc:
        best_acc = max(aff_acc, key=aff_acc.get)
        print(f"  -> best by LOO acc: alpha_affirm = {best_acc:.2f} (acc = {aff_acc[best_acc]:.3f})")
    if aff_sp:
        best_sp = max(aff_sp, key=aff_sp.get)
        print(f"  -> best by Spearman: alpha_affirm = {best_sp:.2f} (spearman = {aff_sp[best_sp]:.3f})")

    print("\nINFERENCE_CATEGORIES (averaged across alpha_affirm):")
    print(f"{'alpha_cat':>12} | {'LOO acc':>8} | {'Spearman':>9}")
    for ac in alphas_c:
        a = cat_acc.get(ac)
        s = cat_sp.get(ac)
        print(f"{ac:>12.2f} | {a:>8.3f} | {s:>9.3f}"
              if a is not None and s is not None else f"{ac:>12.2f} | -- | --")
    if cat_acc:
        best_acc = max(cat_acc, key=cat_acc.get)
        print(f"  -> best by LOO acc: alpha_categories = {best_acc:.2f} (acc = {cat_acc[best_acc]:.3f})")
    if cat_sp:
        best_sp = max(cat_sp, key=cat_sp.get)
        print(f"  -> best by Spearman: alpha_categories = {best_sp:.2f} (spearman = {cat_sp[best_sp]:.3f})")


if __name__ == "__main__":
    main()
