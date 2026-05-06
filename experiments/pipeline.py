"""
Unified analysis pipeline for the natural-language preference learning paper.

A single entry point that drives the four existing analysis scripts to produce
all per-domain results and joint paper figures from a single canonical
configuration.

Subcommands
-----------
    calibrate <dataset>          Find optimal (alpha, lambda, scheme) per condition
                                 AND a single-alpha optimum, save to optima.json.
    analyze   <dataset>          Run analyze.py + learning_curves.py at:
                                  - deployed hyperparameters (pre-reg analysis)
                                  - single-alpha optimum (paper headline)
                                  - per-condition optima (appendix)
    decomposition                Compute Coverage / Cov/PCA_K / mean Indep
                                 across all paper datasets, write LaTeX table.
    paper                        Assemble the joint paper figures and tables.
                                 Reads from each dataset's outputs; writes to
                                 outputs/paper/.
    all                          calibrate -> analyze -> decomposition -> paper,
                                 across every dataset flagged include_in_paper.

Examples
--------
    python experiments/pipeline.py all
    python experiments/pipeline.py calibrate dilemmas
    python experiments/pipeline.py analyze dilemmas
    python experiments/pipeline.py decomposition
    python experiments/pipeline.py paper

Design notes
------------
- Driven entirely by experiments/configs.py. Adding a new dataset is one
  edit there; the pipeline picks it up.
- Existing scripts (analyze.py, calibrate_methods.py, learning_curves.py,
  analyze_decomposition.py) are untouched. The pipeline shells out to them
  with appropriate flags rather than importing them directly, so any of the
  per-script commands shown in older docs continue to work standalone.
- Fail-fast: any subprocess error stops the pipeline immediately. Re-run the
  failed command to debug.
- Outputs are organized as:
    experiments/outputs/<dataset>/deployed/        # pre-reg analysis
    experiments/outputs/<dataset>/optimal_single/  # paper headline (one alpha)
    experiments/outputs/<dataset>/optimal_per/     # appendix (per-condition)
    experiments/outputs/<dataset>/calibration/     # sweep + optima.json
    experiments/outputs/decomposition/             # cross-domain Table 1
    experiments/outputs/paper/                     # joint figures + tables
"""

import argparse
import json
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from scipy import stats

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from configs import (  # noqa: E402
    DATASETS, REPO_ROOT, OUTPUTS_DIR,
    paper_datasets, output_dir, paper_output_dir, decomposition_output_dir,
)
from analyze import t_ci, COND_LABELS, COND_COLORS, CONDITIONS  # noqa: E402


# ============================================================================
# Subprocess helper (fail-fast)
# ============================================================================
def run(cmd, cwd=None, label=None):
    """Run a shell command. On failure, print details and exit immediately."""
    label = label or " ".join(str(c) for c in cmd[:3])
    print(f"\n>>> {label}")
    print(f"    {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(
        [str(c) for c in cmd], cwd=str(cwd) if cwd else None,
        capture_output=False, text=True,
    )
    if result.returncode != 0:
        print(f"\n[FAIL] {label}  (exit={result.returncode})")
        sys.exit(result.returncode)


# ============================================================================
# Subcommand: calibrate
# ============================================================================
def find_single_alpha_optimum(sweep_json):
    """From a calibration_sweep.json, find the single (scheme, alpha, lambda)
    that maximizes mean lift POOLED across affirm + categories.

    The sweep file already has per-(condition, scheme, alpha, lambda) cells.
    We pool by averaging the per-cell mean lifts of affirm and categories at
    each shared (scheme, alpha, lambda).
    """
    cells = sweep_json["cells"]
    pooled = defaultdict(list)  # (scheme, alpha, lambda) -> [(n, mean), ...]
    for key_str, cell in cells.items():
        cond, scheme, alpha, lam = key_str.split("|")
        if cond not in ("inference_affirm", "inference_categories"):
            continue
        pooled[(scheme, float(alpha), float(lam))].append(
            (cell["n"], cell["mean_diff"])
        )
    best = None
    for (scheme, alpha, lam), entries in pooled.items():
        if len(entries) < 2:
            continue  # need both conditions to count as "pooled"
        # Sample-size-weighted mean across conditions
        total_n = sum(n for n, _ in entries)
        if total_n == 0:
            continue
        pooled_mean = sum(n * m for n, m in entries) / total_n
        if best is None or pooled_mean > best["pooled_mean"]:
            best = {
                "scheme": scheme,
                "alpha": alpha,
                "lambda": lam,
                "pooled_mean": pooled_mean,
                "per_condition": [
                    {"n": n, "mean_diff": m} for n, m in entries
                ],
            }
    return best


def cmd_calibrate(dataset_key):
    if dataset_key not in DATASETS:
        sys.exit(f"Unknown dataset: {dataset_key}")
    cfg = DATASETS[dataset_key]
    out = output_dir(dataset_key, "calibration")
    out.mkdir(parents=True, exist_ok=True)

    # 1. Run the calibration sweep into the dataset's calibration/ folder.
    run([
        sys.executable, SCRIPT_DIR / "calibrate_methods.py",
        "--data", cfg["data"],
        "--out-dir", out,
    ], cwd=REPO_ROOT, label=f"calibrate({dataset_key})")

    # 2. Read sweep results, derive both per-condition and single-alpha optima.
    sweep_json_path = out / "calibration_sweep.json"
    if not sweep_json_path.exists():
        sys.exit(f"calibrate_methods did not produce {sweep_json_path}")
    sweep = json.loads(sweep_json_path.read_text())

    per_condition = sweep.get("optimal_per_condition", {}) or {}
    single = find_single_alpha_optimum(sweep)

    optima = {
        "dataset": dataset_key,
        "deployed": cfg["deployed"],
        "per_condition_optimum": per_condition,
        "single_alpha_optimum": single,
    }
    optima_path = out / "optima.json"
    optima_path.write_text(json.dumps(optima, indent=2))
    print(f"\n>>> Wrote: {optima_path}")
    if single is not None:
        print(f"    Single-alpha optimum: scheme={single['scheme']}, "
              f"alpha={single['alpha']}, lambda={single['lambda']}, "
              f"pooled mean Δacc={single['pooled_mean']:+.4f}")
    if per_condition:
        for cond, b in per_condition.items():
            if not b:
                continue
            print(f"    {cond}: alpha={b['alpha']}, lambda={b['lam']}, "
                  f"scheme={b['scheme']}, Δacc={b['mean_diff']:+.4f}")


# ============================================================================
# Subcommand: analyze
# ============================================================================
def cmd_analyze(dataset_key):
    if dataset_key not in DATASETS:
        sys.exit(f"Unknown dataset: {dataset_key}")
    cfg = DATASETS[dataset_key]

    # --- 1. deployed: pre-registered hyperparameters ---
    deployed_out = output_dir(dataset_key, "deployed")
    deployed_out.mkdir(parents=True, exist_ok=True)
    run([
        sys.executable, SCRIPT_DIR / "analyze.py",
        "--data", cfg["data"],
        "--out-dir", deployed_out,
        "--alpha", cfg["deployed"]["alpha"],
        "--lambda-partial", cfg["deployed"]["lambda"],
    ], cwd=REPO_ROOT, label=f"analyze({dataset_key}, deployed)")
    run([
        sys.executable, SCRIPT_DIR / "learning_curves.py",
        "--data", cfg["data"],
        "--out-dir", deployed_out,
    ], cwd=REPO_ROOT, label=f"learning_curves({dataset_key}, deployed)")

    # --- 2 + 3. optimal variants (if calibration has been run) ---
    optima_path = output_dir(dataset_key, "calibration") / "optima.json"
    if not optima_path.exists():
        print(f"\n[WARN] No calibration found for {dataset_key} at {optima_path}.")
        print("       Run `pipeline.py calibrate` first to also produce optimal-config analyses.")
        return
    optima = json.loads(optima_path.read_text())

    # Single-alpha (paper headline)
    single = optima.get("single_alpha_optimum")
    if single is not None:
        single_out = output_dir(dataset_key, "optimal_single")
        single_out.mkdir(parents=True, exist_ok=True)
        run([
            sys.executable, SCRIPT_DIR / "analyze.py",
            "--data", cfg["data"],
            "--out-dir", single_out,
            "--alpha", single["alpha"],
            "--lambda-partial", single["lambda"],
        ], cwd=REPO_ROOT, label=f"analyze({dataset_key}, optimal_single)")

    # Per-condition (appendix)
    per_cond = optima.get("per_condition_optimum") or {}
    aff = per_cond.get("inference_affirm") or {}
    cat = per_cond.get("inference_categories") or {}
    if aff and cat:
        # The two conditions may have different lambdas. analyze.py supports
        # only one lambda per run, so when they differ we bias to the affirm
        # lambda and warn (the alternative would be to invoke analyze.py
        # twice, but the resulting figure splices wouldn't be honest about
        # what mu_prior values the random/projection_only fits actually used).
        per_out = output_dir(dataset_key, "optimal_per")
        per_out.mkdir(parents=True, exist_ok=True)
        if aff.get("lam") != cat.get("lam"):
            print(f"\n[WARN] Per-condition optima have different lambdas: "
                  f"affirm={aff['lam']}, categories={cat['lam']}. "
                  f"Using affirm's lambda for the joint analyze.py run.")
        run([
            sys.executable, SCRIPT_DIR / "analyze.py",
            "--data", cfg["data"],
            "--out-dir", per_out,
            "--alpha-affirm", aff["alpha"],
            "--alpha-categories", cat["alpha"],
            "--lambda-partial", aff.get("lam", cfg["deployed"]["lambda"]),
        ], cwd=REPO_ROOT, label=f"analyze({dataset_key}, optimal_per)")


# ============================================================================
# Subcommand: decomposition
# ============================================================================
def cmd_decomposition():
    out = decomposition_output_dir()
    out.mkdir(parents=True, exist_ok=True)
    domains_arg = []
    for ds_key in paper_datasets():
        d = DATASETS[ds_key]["domain"]
        if d not in domains_arg:
            domains_arg.append(d)
    cmd = [
        sys.executable, SCRIPT_DIR / "analyze_decomposition.py",
        "--domains", *domains_arg,
        "--latex-out", out / "decomposition_table.tex",
    ]
    run(cmd, cwd=REPO_ROOT, label="decomposition")


# ============================================================================
# Subcommand: paper (joint figures + tables)
# ============================================================================
def _load_summary(dataset_key, variant):
    """Load summary.json from a given variant dir, or None if absent."""
    p = output_dir(dataset_key, variant) / "summary.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


def _load_learning_curves(dataset_key, variant):
    """Load learning_curves.json from a given variant dir, or None."""
    p = output_dir(dataset_key, variant) / "learning_curves.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


def _sig_marker(p):
    if p is None:
        return ""
    if p < 0.001: return "***"
    if p < 0.01:  return "**"
    if p < 0.05:  return "*"
    return ""


def _bar_panel(ax, datasets_data, ylabel, title, layout):
    """Render H1/H2/H3 bar panel. layout in {'side_by_side', 'overlaid'}.

    datasets_data: list of (dataset_label, vals_per_cond, p_per_cond) tuples,
    one per dataset to render.
    """
    n_ds = len(datasets_data)
    n_cond = len(CONDITIONS)
    width = 0.8 / max(n_ds, 1) if layout == "side_by_side" else 0.6
    x_base = np.arange(n_cond)

    all_means_for_ylim, all_cis_for_ylim = [], []

    for di, (label, vals_per_cond, p_per_cond) in enumerate(datasets_data):
        means, cis, ns, sigs = [], [], [], []
        for cond in CONDITIONS:
            vs = vals_per_cond.get(cond) or []
            mean, ci = t_ci(vs)
            means.append(mean); cis.append(ci); ns.append(len(vs))
            sigs.append(_sig_marker(p_per_cond.get(cond)))
        all_means_for_ylim.extend(means); all_cis_for_ylim.extend(cis)

        if layout == "side_by_side":
            x = x_base + (di - (n_ds - 1) / 2) * width
            colors = [COND_COLORS[c] for c in CONDITIONS]
            alpha_face = 0.92 - di * 0.18  # slight alpha shift to differentiate
            ax.bar(x, means, width=width * 0.95, yerr=cis, capsize=4,
                   color=colors, alpha=alpha_face,
                   edgecolor="white", linewidth=1.0,
                   error_kw={"linewidth": 1.2, "ecolor": "#1a1a1a"},
                   label=label)
        else:  # overlaid
            x = x_base
            face = ["#3b82f6", "#dc2626"][di % 2]
            ax.bar(x, means, width=width, yerr=cis, capsize=5,
                   color=face, alpha=0.55, edgecolor="white", linewidth=1.0,
                   error_kw={"linewidth": 1.2, "ecolor": "#1a1a1a"},
                   label=label)

        # significance markers
        for xi, mean, ci, sig in zip(x, means, cis, sigs):
            if not sig:
                continue
            if mean >= 0:
                y = mean + ci + 0.02 * (max(all_means_for_ylim + [0.01]))
                va = "bottom"
            else:
                y = mean - ci - 0.02 * (max(all_means_for_ylim + [0.01]))
                va = "top"
            ax.text(xi, y, sig, ha="center", va=va, fontsize=10,
                    fontweight="bold", color="#1a1a1a")

    ax.axhline(0, color="black", linewidth=0.7, linestyle="-", alpha=0.6)
    ax.set_xticks(x_base)
    ax.set_xticklabels([COND_LABELS[c] for c in CONDITIONS], fontsize=9)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_title(title, fontsize=11)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if all_means_for_ylim:
        lows  = [m - c for m, c in zip(all_means_for_ylim, all_cis_for_ylim)] + [0]
        highs = [m + c for m, c in zip(all_means_for_ylim, all_cis_for_ylim)] + [0]
        lo, hi = min(lows), max(highs)
        span = (hi - lo) if hi > lo else 0.1
        ax.set_ylim(lo - span * 0.18, hi + span * 0.32)
    ax.legend(loc="upper right", fontsize=8, framealpha=0.92)


def _joint_dv_figure(variant, layout, out_path):
    """Joint figure with H1/H2/H3 panels covering both paper datasets."""
    datasets = paper_datasets()
    summaries = {ds: _load_summary(ds, variant) for ds in datasets}
    if any(s is None for s in summaries.values()):
        missing = [ds for ds, s in summaries.items() if s is None]
        print(f"[WARN] joint DV ({variant}, {layout}): missing summaries for {missing}; skipping.")
        return False

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5))

    # H1
    h1_ds_data = []
    for ds in datasets:
        s = summaries[ds]
        h1 = s.get("h1", {})
        vals = {c: [r["diff"] for r in (h1.get(c, {}).get("rows") or [])] for c in CONDITIONS}
        ps = {c: h1.get(c, {}).get("p_one_sided") for c in CONDITIONS}
        h1_ds_data.append((DATASETS[ds]["label"], vals, ps))
    _bar_panel(axes[0], h1_ds_data,
               "LOO accuracy: augmented − baseline",
               "H1: predictive accuracy lift", layout)

    # H2
    h2_ds_data = []
    for ds in datasets:
        s = summaries[ds]
        h2 = s.get("h2", {})
        vals = {c: [r["signed"] for r in (h2.get(c, {}).get("rows") or [])] for c in CONDITIONS}
        ps = {c: h2.get(c, {}).get("p_one_sided") for c in CONDITIONS}
        h2_ds_data.append((DATASETS[ds]["label"], vals, ps))
    _bar_panel(axes[1], h2_ds_data,
               "Signed Likert (+ = preferred augmented)",
               "H2: summary preference", layout)

    # H3
    h3_ds_data = []
    for ds in datasets:
        s = summaries[ds]
        h3 = s.get("h3", {})
        vals = {c: [r["diff"] for r in (h3.get(c, {}).get("rows") or [])] for c in CONDITIONS}
        ps = {c: h3.get(c, {}).get("p_one_sided") for c in CONDITIONS}
        h3_ds_data.append((DATASETS[ds]["label"], vals, ps))
    _bar_panel(axes[2], h3_ds_data,
               "Augmented − baseline rating",
               "H3: prediction endorsement", layout)

    fig.suptitle(
        f"DV results across domains ({variant}, layout={layout})  "
        f"   * p<.05  ** p<.01  *** p<.001  one-sided, unadjusted",
        fontsize=10, y=1.02)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    return True


def _joint_learning_curves_figure(variant, out_path):
    """Side-by-side learning curves for both paper datasets, three conditions
    each.

    learning_curves.py writes learning_curves_deployed.png and
    learning_curves_optimal.png (and the JSON we read here)."""
    datasets = paper_datasets()
    lcs = {ds: _load_learning_curves(ds, variant) for ds in datasets}
    if any(v is None for v in lcs.values()):
        missing = [ds for ds, v in lcs.items() if v is None]
        print(f"[WARN] joint learning curves ({variant}): missing for {missing}; skipping.")
        return False

    # learning_curves.json structure (per its writer):
    #   summary[config_name][cond][model] = {n_participants, train_sizes, mean, ci_half}
    # The 'config' here in learning_curves' world corresponds to the
    # learning_curves.py CONFIGS dict ('deployed' or 'optimal'); we always
    # read the 'deployed' key from that JSON since that's what learning_curves
    # writes when invoked with default args (regardless of whether THIS
    # pipeline variant is named 'deployed' or 'optimal_single').
    # For per-pipeline-variant differentiation, we rely on the directory.
    n_ds = len(datasets)
    fig, axes = plt.subplots(n_ds, 3, figsize=(15, 4.0 * n_ds), sharey=True,
                             squeeze=False)

    for di, ds in enumerate(datasets):
        lc = lcs[ds]
        # Try 'deployed' first, then 'optimal'; learning_curves writes both
        # when called with --config both, otherwise only the requested one.
        lc_summary = lc.get("summary", {})
        lc_config_name = "deployed" if "deployed" in lc_summary else (
            "optimal" if "optimal" in lc_summary else None)
        if lc_config_name is None:
            print(f"[WARN] learning_curves.json for {ds} has no recognized config keys; "
                  f"got {list(lc_summary.keys())}")
            continue
        per_cond = lc_summary[lc_config_name]
        for ci, cond in enumerate(CONDITIONS):
            ax = axes[di][ci]
            cond_data = per_cond.get(cond, {})
            for model, color in [
                ("random_projection", "#9ca3af"),
                ("projection_only",   "#3b82f6"),
                ("projection_alpha",  "#dc2626"),
            ]:
                m = cond_data.get(model)
                if not m:
                    continue
                xs = m["train_sizes"]
                mean = np.array(m["mean"])
                ci_half = np.array(m["ci_half"])
                ax.plot(xs, mean, marker="o", linewidth=2, color=color,
                        markersize=4, label=model.replace("_", " "))
                ax.fill_between(xs, mean - ci_half, mean + ci_half,
                                alpha=0.18, color=color, linewidth=0)
            ax.axhline(0.5, color="black", linewidth=0.5, linestyle="--", alpha=0.4)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            if di == 0:
                ax.set_title(COND_LABELS[cond], fontsize=11)
            if di == n_ds - 1:
                ax.set_xlabel("Training trials")
            if ci == 0:
                ax.set_ylabel(f"{DATASETS[ds]['label']}\nLOO accuracy", fontsize=10)
            ax.legend(loc="lower right", fontsize=7, framealpha=0.9)

    fig.suptitle(f"Learning curves ({variant})", fontsize=12, y=1.00)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    return True


def _joint_dv_table(variant, out_path):
    """LaTeX table summarizing H1/H2/H3 across both paper datasets."""
    datasets = paper_datasets()
    summaries = {ds: _load_summary(ds, variant) for ds in datasets}
    if any(s is None for s in summaries.values()):
        return False

    L = []
    L.append(r"% Joint DV results table — variant=" + variant)
    L.append(r"\begin{table}[t]")
    L.append(r"  \centering")
    L.append(r"  \small")
    L.append(r"  \caption{Pre-registered behavioral results across domains "
             r"(variant: " + variant.replace("_", r"\_") + r"). "
             r"H1: LOO accuracy lift (augmented $-$ baseline); H2: signed "
             r"Likert summary preference; H3: paired prediction-rating "
             r"difference. All $p$-values are one-sided; $p_{\text{holm}}$ "
             r"adjusted within each hypothesis family.}")
    L.append(r"  \label{tab:dv_results_" + variant + r"}")
    L.append(r"  \begin{tabular}{@{}llrrrr@{}}")
    L.append(r"    \toprule")
    L.append(r"    Domain & Condition & $N$ & H1 ($\Delta$acc, $p_{\text{holm}}$) "
             r"& H2 (mean, $p_{\text{holm}}$) & H3 (mean $\Delta$, $p_{\text{holm}}$) \\")
    L.append(r"    \midrule")
    for di, ds in enumerate(datasets):
        s = summaries[ds]
        h1 = s.get("h1", {}); h2 = s.get("h2", {}); h3 = s.get("h3", {})
        for ci, cond in enumerate(CONDITIONS):
            r1 = h1.get(cond, {}); r2 = h2.get(cond, {}); r3 = h3.get(cond, {})
            domain_cell = DATASETS[ds]["label"] if ci == 0 else ""
            n = r1.get("n", r2.get("n", 0))
            h1_str = (f"${r1.get('mean_diff', 0):+.3f}$, "
                      f"${r1.get('p_holm', float('nan')):.3f}$"
                      if r1.get('p_holm') is not None else "—")
            mc = " (mc)" if r2.get("is_manipulation_check") else ""
            h2_str = (f"${r2.get('mean', 0):+.2f}$, "
                      f"${r2.get('p_holm', r2.get('p_one_sided', float('nan'))):.3f}${mc}"
                      if r2.get('p_one_sided') is not None else "—")
            h3_str = (f"${r3.get('mean', 0):+.2f}$, "
                      f"${r3.get('p_holm', float('nan')):.3f}$"
                      if r3.get('p_holm') is not None else "—")
            L.append(f"    {domain_cell} & {COND_LABELS[cond]} & {n} & "
                     f"{h1_str} & {h2_str} & {h3_str} \\\\")
        if di < len(datasets) - 1:
            L.append(r"    \midrule")
    L.append(r"    \bottomrule")
    L.append(r"  \end{tabular}")
    L.append(r"\end{table}")
    out_path.write_text("\n".join(L) + "\n")
    return True


def cmd_paper():
    paper_dir = paper_output_dir()
    paper_dir.mkdir(parents=True, exist_ok=True)
    domain_subdir = paper_dir / "domains"
    domain_subdir.mkdir(parents=True, exist_ok=True)

    # 1. Joint DV bar figures: 2 variants x 2 layouts = 4 figures
    for variant in ("deployed", "optimal_single"):
        for layout in ("side_by_side", "overlaid"):
            out = paper_dir / f"dv_bars_{variant}_{layout}.png"
            ok = _joint_dv_figure(variant, layout, out)
            if ok:
                print(f">>> Wrote: {out}")

    # 2. Joint learning curves: 2 variants x 1 layout
    for variant in ("deployed", "optimal_single"):
        out = paper_dir / f"learning_curves_{variant}.png"
        ok = _joint_learning_curves_figure(variant, out)
        if ok:
            print(f">>> Wrote: {out}")

    # 3. DV results tables (LaTeX)
    for variant in ("deployed", "optimal_single"):
        out = paper_dir / f"dv_results_{variant}.tex"
        ok = _joint_dv_table(variant, out)
        if ok:
            print(f">>> Wrote: {out}")

    # 4. Copy per-domain figures into domains/ (for the appendix)
    for ds in paper_datasets():
        for variant in ("deployed", "optimal_single", "optimal_per"):
            src_dir = output_dir(ds, variant)
            for fname in ("main_figure.png", "learning_curves_deployed.png",
                          "learning_curves_optimal.png", "summary.md"):
                src = src_dir / fname
                if src.exists():
                    dst = domain_subdir / f"{ds}_{variant}__{fname}"
                    shutil.copy2(src, dst)
        # Per-domain calibration heatmap
        cal_src = output_dir(ds, "calibration") / "calibration_sweep.png"
        if cal_src.exists():
            shutil.copy2(cal_src, domain_subdir / f"{ds}_calibration_sweep.png")

    # 5. Copy decomposition table
    dec_src = decomposition_output_dir() / "decomposition_table.tex"
    if dec_src.exists():
        shutil.copy2(dec_src, paper_dir / "decomposition_table.tex")
        print(f">>> Wrote: {paper_dir / 'decomposition_table.tex'}")

    print(f"\nPaper artefacts in: {paper_dir}")
    print(f"Per-domain copies in: {domain_subdir}")


# ============================================================================
# Subcommand: all
# ============================================================================
def cmd_all():
    datasets = paper_datasets()
    print(f"\n=== PIPELINE: all ===")
    print(f"Datasets included in paper: {datasets}")

    for ds in datasets:
        print(f"\n--- {ds}: calibrate ---")
        cmd_calibrate(ds)
    for ds in datasets:
        print(f"\n--- {ds}: analyze ---")
        cmd_analyze(ds)
    print(f"\n--- decomposition ---")
    cmd_decomposition()
    print(f"\n--- paper ---")
    cmd_paper()
    print(f"\n=== DONE ===")
    print(f"Outputs: {OUTPUTS_DIR}")


# ============================================================================
# CLI
# ============================================================================
def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_cal = sub.add_parser("calibrate", help="Find optimal hyperparameters for a dataset")
    p_cal.add_argument("dataset", choices=list(DATASETS.keys()))

    p_ana = sub.add_parser("analyze", help="Run analyze.py + learning_curves.py for a dataset")
    p_ana.add_argument("dataset", choices=list(DATASETS.keys()))

    sub.add_parser("decomposition", help="Compute per-domain decomposition stats")

    sub.add_parser("paper", help="Assemble joint paper figures + tables")

    sub.add_parser("all", help="calibrate + analyze + decomposition + paper")

    args = parser.parse_args()

    if args.cmd == "calibrate":
        cmd_calibrate(args.dataset)
    elif args.cmd == "analyze":
        cmd_analyze(args.dataset)
    elif args.cmd == "decomposition":
        cmd_decomposition()
    elif args.cmd == "paper":
        cmd_paper()
    elif args.cmd == "all":
        cmd_all()


if __name__ == "__main__":
    main()
