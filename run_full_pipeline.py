#!/usr/bin/env python3
"""
run_full_pipeline.py

End-to-end pipeline: CSV → embeddings → dimensions → directions → BT scores.

Stages (each skipped if its sentinel output already exists):
  0:  embed CSV              → embeddings_parquet (skipped if parquet exists)
  A:  method_llm_examples   → {out}/examples/dimensions.json
  B:  method_llm_directions → {out}/directions/selected_axes.json
  B2: evaluate_basis         → {out}/directions/basis_evaluation.md
  C:  score-options          → {out}/judging/direct_scores.csv
  D:  judge-pairs            → {out}/judging/pairwise_judgments.csv
  E:  fit-bt                 → {out}/judging/bt_scores.csv
  F:  final_report.md        → {out}/final_report.md

Usage:
  python run_full_pipeline.py --config configs/movies_200_full.json
"""

import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

REPO   = Path(__file__).resolve().parent
PYTHON = str(REPO / ".venv/bin/python")


# ─── helpers ──────────────────────────────────────────────────────────────────

def load_json(path):
    return json.loads(Path(path).read_text("utf-8"))

def save_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")

def sep(title):
    print(f"\n{'='*60}\n{title}\n{'='*60}", flush=True)

def skip(stage, reason):
    print(f"[{stage}] Skipping — {reason}", flush=True)

def run(cmd, stage):
    sep(stage)
    subprocess.run([str(c) for c in cmd], check=True)

def resolve(base, path):
    """Resolve a config path relative to REPO if not absolute."""
    p = Path(path)
    return str(p if p.is_absolute() else base / p)


def parse_force_stages(spec: str) -> list[str]:
    """Parse a compact force-stage spec like 'B2F' or 'A, C, F'."""
    tokens: list[str] = []
    i = 0
    spec = spec.upper().replace(",", " ")
    while i < len(spec):
        ch = spec[i]
        if ch.isspace():
            i += 1
            continue
        if spec.startswith("B2", i):
            tokens.append("B2")
            i += 2
            continue
        if ch in {"0", "A", "B", "C", "D", "E", "F"}:
            tokens.append(ch)
        i += 1
    return tokens


# ─── stage implementations ────────────────────────────────────────────────────

def stage_0_embed(cfg):
    """Embed the input CSV if the parquet doesn't exist yet."""
    parquet = Path(cfg["_embeddings_parquet"])
    if parquet.exists():
        skip("0", f"embeddings parquet already exists ({parquet.name})")
        return

    em = cfg.get("embed", {})
    base_url = em.get("base_url", "")
    model    = em.get("model", "")
    api_key  = em.get("api_key", "dummy")
    if not base_url or not model:
        raise ValueError("Config missing embed.base_url or embed.model — needed to generate embeddings.")

    cmd = [
        PYTHON, "embed/embedder/embed_csv.py",
        "--base-url",   base_url,
        "--model",      model,
        "--api-key",    api_key,
        "--input-csv",  cfg["input_path"],
        "--output",     str(parquet),
        "--batch-size", str(em.get("batch_size", 128)),
    ]
    if cfg.get("template_path"):
        cmd += ["--template-file", cfg["template_path"]]

    run(cmd, "Stage 0: embed CSV → parquet")


def stage_a_examples(cfg, examples_dir, base_url, model, api_key):
    sentinel = examples_dir / "dimensions.json"
    if sentinel.exists():
        skip("A", "dimensions.json exists")
        return

    ex = cfg.get("examples", {})
    run([
        PYTHON, "method_llm_examples/pipeline.py",
        "--config", cfg["_config_path"],
        "--embeddings-parquet", cfg["_embeddings_parquet"],
        "--base-url", base_url,
        "--model", model,
        "--api-key", api_key,
        "--output-dir", str(examples_dir),
        "--num-pairs",      str(ex.get("num_pairs", 200)),
        "--strata",         str(ex.get("strata", 5)),
        "--num-dimensions", str(ex.get("num_dimensions", 10)),
        "--num-themes",     str(ex.get("num_themes", 50)),
        "--max-workers",    str(ex.get("max_workers", 32)),
        "--skip-coverage",
    ], "Stage A: method_llm_examples")


def stage_b_directions(cfg, directions_dir, output_dir, base_url, model, api_key):
    sentinel = directions_dir / "selected_axes.json"
    if sentinel.exists():
        skip("B", "selected_axes.json exists")
        return

    dr = cfg.get("directions", {})
    dir_cfg = {
        "domain":          cfg["domain"],
        "choice_context":  cfg["choice_context"],
        "input_path":      cfg["_embeddings_parquet"],
        "embedding_column": cfg.get("embedding_column", "embedding"),
        "id_column":       cfg.get("id_column", "movie_id"),
        "text_column":     cfg.get("text_column", "plot_summary"),
        "n_score_sample":  dr.get("n_score_sample", 100),
        "n_select":        dr.get("n_select", 10),
        "max_wines_sample": cfg.get("max_options", dr.get("max_wines_sample", 5000)),
        "score_workers":   dr.get("score_workers", 4),
        "max_workers":     dr.get("max_workers", 8),
    }
    dir_cfg_path = output_dir / "_directions_config.json"
    save_json(dir_cfg_path, dir_cfg)

    run([
        PYTHON, "method_llm_directions/pipeline.py", "run-all",
        "--config",      str(dir_cfg_path),
        "--output-dir",  str(directions_dir),
        "--base-url",    base_url,
        "--model",       model,
        "--api-key",     api_key,
        "--provider",    "local",
        "--max-workers", str(dr.get("max_workers", 8)),
    ], "Stage B: method_llm_directions")


def stage_b2_evaluate_basis(cfg, directions_dir):
    sentinel = directions_dir / "basis_evaluation.md"
    if sentinel.exists():
        skip("B2", "basis_evaluation.md exists")
        return

    selected_path = directions_dir / "selected_directions.npz"
    if not selected_path.exists():
        print("[B2] selected_directions.npz not found — skipping basis evaluation", flush=True)
        return

    axes_path = directions_dir / "selected_axes.json"
    dim_names = []
    if axes_path.exists():
        sel = load_json(axes_path)
        dim_names = [ax["name"] for ax in sel.get("selected_axes", [])]

    cmd = [
        PYTHON, "method_directions/evaluate_basis.py",
        "--embeddings-parquet", cfg["_embeddings_parquet"],
        "--directions",         str(selected_path),
        "--output-dir",         str(directions_dir),
        "--embedding-column",   cfg.get("embedding_column", "embedding"),
    ]
    if dim_names:
        cmd += ["--dim-names"] + dim_names

    run(cmd, "Stage B2: evaluate_basis")


def _ensure_judging_dims(examples_dir, judging_dir):
    src = examples_dir / "dimensions.json"
    dst = judging_dir / "dimensions.json"
    if not dst.exists():
        shutil.copy(src, dst)
        print(f"[judging] Copied dimensions.json → {dst}", flush=True)


def stage_c_score_options(cfg, judging_dir, base_url, model, api_key):
    sentinel = judging_dir / "direct_scores.csv"
    if sentinel.exists():
        skip("C", "direct_scores.csv exists")
        return

    # Write a judging-specific config with max_workers from judging section
    jcfg = _judging_config(cfg, judging_dir)
    run([
        PYTHON, "method_llm_gen/pipeline.py", "score-options",
        "--config",      str(jcfg),
        "--base-url",    base_url,
        "--model",       model,
        "--api-key",     api_key,
        "--api-provider", "local",
        "--output-dir",  str(judging_dir),
    ], "Stage C: score-options")


def stage_d_judge_pairs(cfg, judging_dir, base_url, model, api_key):
    sentinel = judging_dir / "pairwise_judgments.csv"
    if sentinel.exists():
        skip("D", "pairwise_judgments.csv exists")
        return

    jg = cfg.get("judging", {})
    jcfg = _judging_config(cfg, judging_dir)
    run([
        PYTHON, "method_llm_gen/pipeline.py", "judge-pairs",
        "--config",                str(jcfg),
        "--base-url",              base_url,
        "--model",                 model,
        "--api-key",               api_key,
        "--api-provider",          "local",
        "--output-dir",            str(judging_dir),
        "--appearances-per-option", str(jg.get("appearances_per_option", 10)),
    ], "Stage D: judge-pairs")


def stage_e_fit_bt(cfg, judging_dir, base_url, model, api_key):
    sentinel = judging_dir / "bt_scores.csv"
    if sentinel.exists():
        skip("E", "bt_scores.csv exists")
        return

    jg = cfg.get("judging", {})
    jcfg = _judging_config(cfg, judging_dir)
    run([
        PYTHON, "method_llm_gen/pipeline.py", "fit-bt",
        "--config",       str(jcfg),
        "--base-url",     base_url,
        "--model",        model,
        "--api-key",      api_key,
        "--api-provider", "local",
        "--output-dir",   str(judging_dir),
        "--learning-rate", str(jg.get("lr", 0.05)),
        "--steps",         str(jg.get("steps", 1500)),
    ], "Stage E: fit-bt + summary")


def _judging_config(cfg, judging_dir):
    """Write a per-run config for method_llm_gen with judging max_workers."""
    jg = cfg.get("judging", {})
    merged = {k: v for k, v in cfg.items() if not isinstance(v, dict) and not k.startswith("_")}
    merged["max_workers"] = jg.get("max_workers", 16)
    merged["pair_appearances_per_option"] = jg.get("appearances_per_option", 10)
    path = judging_dir / "_judging_config.json"
    save_json(path, merged)
    return path


# ─── final report ─────────────────────────────────────────────────────────────

def stage_f_final_report(cfg, examples_dir, directions_dir, judging_dir, output_dir):
    sentinel = output_dir / "final_report.md"
    if sentinel.exists():
        skip("F", "final_report.md exists")
        return

    sep("Stage F: final report")
    lines = [
        f"# Pipeline Report: {cfg['domain']}",
        "",
        f"**Choice context:** {cfg['choice_context']}",
        "",
    ]

    # ── Dimensions ──
    dims_path = examples_dir / "dimensions.json"
    if dims_path.exists():
        dims_data = load_json(dims_path)
        dims = dims_data.get("dimensions", [])
        lines += [
            "## Preference Dimensions",
            f"*Discovered from {cfg.get('examples', {}).get('num_pairs', '?')} pairwise examples.*",
            "",
            "| # | Name | Low → High | Articulability | Est. Variance |",
            "|---|------|-----------|----------------|---------------|",
        ]
        for d in dims:
            lp = d.get("low_pole", {})
            hp = d.get("high_pole", {})
            lines.append(
                f"| {d['id']} | {d['name']} | "
                f"{lp.get('label','')} → {hp.get('label','')} | "
                f"{d.get('articulability','')} | "
                f"{d.get('estimated_variance','')} |"
            )
        lines.append("")

        lines.append("### Dimension Details")
        for d in dims:
            lp = d.get("low_pole", {})
            hp = d.get("high_pole", {})
            lines += [
                f"#### {d['id']}. {d['name']}",
                f"- **Low** ({lp.get('label','')}) — {lp.get('description','')}",
                f"- **High** ({hp.get('label','')}) — {hp.get('description','')}",
                f"- Scoring: {d.get('scoring_guidance','')}",
                "",
            ]

    # ── Embedding directions ──
    basis_path   = directions_dir / "basis_metrics.json"
    selected_path = directions_dir / "selected_axes.json"
    if basis_path.exists() and selected_path.exists():
        metrics   = load_json(basis_path)
        selected  = load_json(selected_path)
        sel_axes  = selected.get("selected_axes", [])
        var_j     = metrics.get("var_j", [])
        indep     = metrics.get("independence", [])

        valid_indep = [x for x in indep if not math.isnan(x)]
        mean_indep  = sum(valid_indep) / len(valid_indep) if valid_indep else float("nan")

        lines += [
            "## Embedding Direction Analysis",
            "",
            "| Metric | Greedy (selected) | Naive top-K |",
            "|--------|:-----------------:|:-----------:|",
            f"| Coverage tr(VCV')/tr(C) | **{metrics.get('coverage', 0):.4f}** | {metrics.get('naive_coverage', 0):.4f} |",
            f"| PCA upper bound         | {metrics.get('pca_coverage', 0):.4f} | {metrics.get('pca_coverage', 0):.4f} |",
            f"| Mean independence       | {mean_indep:.4f} | — |",
            "",
            "### Selected Axes — Variance Breakdown",
            "",
            "| Rank | Axis Name | Variance | Ridge R² | Strategy |",
            "|------|-----------|:--------:|:--------:|----------|",
        ]
        for ax in sel_axes:
            lines.append(
                f"| {ax['rank']} | {ax['name']} | {ax['variance']:.5f} "
                f"| {ax['r2_cv']:.3f} | {ax.get('_strategy','')} |"
            )
        lines.append("")

        lines.append("### Axis Descriptions")
        for ax in sel_axes:
            lines += [
                f"#### {ax['rank']}. {ax['name']}",
                f"- **Low** ({ax.get('low_label','')}) — {ax.get('low_description','')}",
                f"- **High** ({ax.get('high_label','')}) — {ax.get('high_description','')}",
                f"- Variance: `{ax['variance']:.5f}` | Ridge R²: `{ax['r2_cv']:.3f}` | Strategy: `{ax.get('_strategy','')}`",
                "",
            ]

        # Full directions report (coverage, independence, correlation matrix from method_llm_directions)
        full_report_path = directions_dir / "report.md"
        if full_report_path.exists():
            lines += [
                "### Directions Report",
                "",
                full_report_path.read_text("utf-8"),
            ]

    # ── Basis evaluation (method_directions/evaluate_basis.py) ──
    basis_eval_path = directions_dir / "basis_evaluation.md"
    if basis_eval_path.exists():
        lines += [
            "## Basis Evaluation (method_directions)",
            "",
            basis_eval_path.read_text("utf-8"),
        ]

    # ── BT summary ──
    summary_path = judging_dir / "summary.md"
    if summary_path.exists():
        lines += [
            "## Bradley-Terry Scoring & Cross-Variant Consistency",
            "",
            summary_path.read_text("utf-8"),
        ]

    sentinel.write_text("\n".join(lines), "utf-8")
    print(f"[stage-F] → {sentinel}", flush=True)


# ─── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", required=True, help="Path to unified pipeline config JSON")
    parser.add_argument("--force-stage", help="Re-run a specific stage even if output exists (A/B/C/D/E/F)")
    args = parser.parse_args()

    cfg = load_json(args.config)

    # Resolve paths relative to REPO
    cfg["_config_path"]        = str(Path(args.config).resolve())
    cfg["_embeddings_parquet"] = resolve(REPO, cfg["embeddings_parquet"])
    cfg["input_path"]          = resolve(REPO, cfg["input_path"])
    if "template_path" in cfg:
        cfg["template_path"]   = resolve(REPO, cfg["template_path"])

    output_dir    = REPO / cfg["output_dir"]
    examples_dir  = output_dir / "examples"
    directions_dir = output_dir / "directions"
    judging_dir   = output_dir / "judging"
    for d in [examples_dir, directions_dir, judging_dir]:
        d.mkdir(parents=True, exist_ok=True)

    llm       = cfg.get("llm", {})
    base_url  = llm.get("base_url", "")
    model     = llm.get("model", "")
    api_key   = llm.get("api_key", "dummy")

    # Allow forcing re-run of a stage by deleting its sentinel
    if args.force_stage:
        sentinels = {
            "0": Path(cfg["_embeddings_parquet"]),
            "A": examples_dir / "dimensions.json",
            "B": directions_dir / "selected_axes.json",
            "B2": directions_dir / "basis_evaluation.md",
            "C": judging_dir / "direct_scores.csv",
            "D": judging_dir / "pairwise_judgments.csv",
            "E": judging_dir / "bt_scores.csv",
            "F": output_dir / "final_report.md",
        }
        for s in parse_force_stages(args.force_stage):
            p = sentinels.get(s)
            if p and p.exists():
                p.unlink()
                print(f"[force] Removed sentinel for stage {s}: {p}", flush=True)

    stage_0_embed(cfg)
    stage_a_examples(cfg, examples_dir, base_url, model, api_key)
    stage_b_directions(cfg, directions_dir, output_dir, base_url, model, api_key)
    stage_b2_evaluate_basis(cfg, directions_dir)

    _ensure_judging_dims(examples_dir, judging_dir)

    stage_c_score_options(cfg, judging_dir, base_url, model, api_key)
    stage_d_judge_pairs(cfg, judging_dir, base_url, model, api_key)
    stage_e_fit_bt(cfg, judging_dir, base_url, model, api_key)
    stage_f_final_report(cfg, examples_dir, directions_dir, judging_dir, output_dir)

    sep("Done")
    print(f"Output root:   {output_dir}", flush=True)
    print(f"Dimensions:    {examples_dir / 'dimensions.json'}", flush=True)
    print(f"Directions:    {directions_dir / 'report.md'}", flush=True)
    print(f"BT summary:    {judging_dir / 'summary.md'}", flush=True)
    print(f"Final report:  {output_dir / 'final_report.md'}", flush=True)


if __name__ == "__main__":
    main()
