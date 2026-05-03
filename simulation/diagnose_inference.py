"""
Inference-channel diagnostics for the LLM persona simulation.

Reads llm_cache.json from a previous run and answers:
  - H1 (anchoring): does Qwen mostly "affirm" the system's pre-categorization?
  - H3 (silencing): how often does Qwen pick the indifferent category (mult=0)?
  - Per-position bias: do positions 1-5 of the prompt get systematically
    different responses?
  - Per-persona response-concentration: is each persona giving the same
    answer for every visible dim (low information per trial)?
  - JSON parse failure rate (silent fallback to "affirm" / idx=2 defaults)

Usage:
  python simulation/diagnose_inference.py simulation/outputs/movies_100_llm
  python simulation/diagnose_inference.py simulation/outputs/dailydilemmas_llm \\
      --category-labels "reject|disapprove of|are indifferent to|understand|endorse"
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd


CATEGORY_LABELS_DEFAULT = ["prefer to skip", "aren't into",
                           "are indifferent to", "like", "love"]
MULTS = [-1.5, -1.0, 0.0, 1.0, 1.5]
AFFIRM_ACTIONS = ["affirm", "moderate", "remove"]


def parse_json_response(text):
    """Best-effort JSON extraction. Mirrors the parser used in run_llm_simulation.py."""
    if not isinstance(text, str):
        return None, "not_str"
    # Strip code-fence wrappers
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```\s*$", "", s)
    try:
        return json.loads(s), None
    except Exception:
        pass
    # Fall back to first {...} block
    m = re.search(r"\{.*\}", s, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0)), None
        except Exception as e:
            return None, f"json_err:{type(e).__name__}"
    return None, "no_json_block"


def parse_persona_id(key, prefix):
    """Cache keys look like 'affirm_3_0' (prefix_personaId_trialIdx)."""
    parts = key[len(prefix) + 1:].split("_")
    if len(parts) >= 2:
        try:
            return int(parts[0]), int(parts[1])
        except ValueError:
            pass
    return None, None


def collect_affirm(cache):
    """Returns (rows_df, parse_fail_count, total_count). Each row: persona, trial, position, action, raw."""
    rows = []
    parse_fail = 0
    total = 0
    for key, val in cache.items():
        if not key.startswith("affirm_"):
            continue
        total += 1
        pid, trial = parse_persona_id(key, "affirm")
        parsed, err = parse_json_response(val)
        if parsed is None:
            parse_fail += 1
            continue
        actions = parsed.get("actions", {}) or {}
        for pos_str, raw_action in actions.items():
            try:
                pos = int(pos_str)
            except (ValueError, TypeError):
                continue
            a = str(raw_action).strip().lower()
            normalized = a if a in AFFIRM_ACTIONS else "OTHER"
            rows.append({"persona": pid, "trial": trial, "position": pos,
                         "action": normalized, "raw": a})
    return pd.DataFrame(rows), parse_fail, total


def collect_categories(cache, category_labels):
    """Returns (rows_df, parse_fail_count, total_count)."""
    rows = []
    parse_fail = 0
    total = 0
    label_to_idx = {lbl.lower(): i for i, lbl in enumerate(category_labels)}
    for key, val in cache.items():
        if not key.startswith("cats_"):
            continue
        total += 1
        pid, trial = parse_persona_id(key, "cats")
        parsed, err = parse_json_response(val)
        if parsed is None:
            parse_fail += 1
            continue
        cats = parsed.get("categories", {}) or {}
        for pos_str, raw_cat in cats.items():
            try:
                pos = int(pos_str)
            except (ValueError, TypeError):
                continue
            c = str(raw_cat).strip().lower()
            idx = label_to_idx.get(c, None)
            rows.append({"persona": pid, "trial": trial, "position": pos,
                         "category_idx": idx if idx is not None else -1,
                         "raw": c})
    return pd.DataFrame(rows), parse_fail, total


def concentration_index(values):
    """Herfindahl-style concentration: 1.0 = all same, 1/N = uniform.
    Use to detect personas/trials where Qwen gives the same answer everywhere."""
    if not len(values):
        return float("nan")
    vc = pd.Series(values).value_counts(normalize=True)
    return float((vc ** 2).sum())


def report_affirm(df, parse_fail, total):
    print("=" * 72)
    print("INFERENCE_AFFIRM diagnostics — H1 (anchoring to 'affirm')")
    print("=" * 72)
    print(f"Total cached affirm trials: {total}")
    print(f"  JSON parse failures:       {parse_fail} ({parse_fail/max(total,1):.1%}) "
          f"[these silently default to 'affirm' in the sim]")
    print(f"  Successful trials parsed:  {total - parse_fail}")
    if df.empty:
        print("  (no parsed rows — nothing more to report)")
        return

    print(f"  Total per-dim picks:       {len(df)}")
    print()

    counts = df["action"].value_counts()
    n = len(df)
    print("Overall action distribution:")
    for a in AFFIRM_ACTIONS:
        c = counts.get(a, 0)
        print(f"  {a:10s} {c:5d}  ({c/n:6.1%})")
    other = counts.get("OTHER", 0)
    if other:
        print(f"  OTHER      {other:5d}  ({other/n:6.1%})  [unexpected raw values]")
    print()

    # Per-position breakdown
    print("Per-position breakdown (does Qwen treat positions differently?):")
    pos_df = df.pivot_table(index="position", columns="action",
                            values="trial", aggfunc="count", fill_value=0)
    pos_df_pct = pos_df.div(pos_df.sum(axis=1), axis=0)
    print(pos_df_pct.applymap(lambda x: f"{x:.1%}").to_string())
    print()

    # Per-persona affirm rate
    pp = df.groupby("persona")["action"].apply(
        lambda s: (s == "affirm").mean()).sort_values()
    print(f"Per-persona affirm rate: min={pp.min():.1%} median={pp.median():.1%} "
          f"max={pp.max():.1%}")
    if (pp > 0.95).sum():
        print(f"  ⚠  {(pp > 0.95).sum()} personas affirm >95% of the time "
              f"(rubber-stamp behavior)")
    print()

    # Within-trial concentration: are all 5 positions the same answer?
    trial_concs = df.groupby(["persona", "trial"])["action"].apply(concentration_index)
    homogeneous = (trial_concs >= 0.999).sum()
    print(f"Per-trial homogeneity (all 5 visible dims same answer):")
    print(f"  Trials with all-same answer: {homogeneous}/{len(trial_concs)} "
          f"({homogeneous/max(len(trial_concs),1):.1%})")
    print(f"  Mean concentration: {trial_concs.mean():.3f}  "
          f"(0.20=uniform across 3 actions, 1.00=all-same)")
    print()

    # Verdict
    affirm_pct = counts.get("affirm", 0) / n
    print(f"H1 VERDICT — Affirm rate: {affirm_pct:.1%}")
    if affirm_pct > 0.75:
        print("  ⚠  H1 SUPPORTED: heavy anchoring. Channel collapses to "
              "amplifying the choice signal rather than introducing new info.")
    elif affirm_pct < 0.45:
        print("  ✓  H1 REFUTED: balanced distribution — Qwen is using the "
              "moderate/remove options too.")
    else:
        print("  ~  Mixed evidence — affirm dominant but not exclusively.")


def report_categories(df, parse_fail, total, category_labels):
    print()
    print("=" * 72)
    print("INFERENCE_CATEGORIES diagnostics — H3 (indifferent sink)")
    print("=" * 72)
    print(f"Total cached cats trials:   {total}")
    print(f"  JSON parse failures:      {parse_fail} ({parse_fail/max(total,1):.1%}) "
          f"[these silently default to idx=2 'indifferent' in the sim]")
    print(f"  Successful trials parsed: {total - parse_fail}")
    if df.empty:
        print("  (no parsed rows)")
        return

    valid = df[df["category_idx"] >= 0]
    invalid = df[df["category_idx"] < 0]
    print(f"  Total per-dim picks:      {len(df)} ({len(valid)} valid, "
          f"{len(invalid)} unrecognized)")
    print()

    n = len(valid)
    if n == 0:
        print("  (no valid category picks)")
        return

    counts = valid["category_idx"].value_counts().sort_index()
    print("Overall category distribution (5 buckets, mults in {-1.5,-1,0,1,1.5}):")
    for i, lbl in enumerate(category_labels):
        c = int(counts.get(i, 0))
        bar = "█" * int(40 * c / n) if n > 0 else ""
        print(f"  [{i}] {lbl:25s} mult={MULTS[i]:+.1f}  {c:5d} ({c/n:6.1%})  {bar}")
    print()

    # Indifferent rate (the silencing pole)
    idx2_pct = counts.get(2, 0) / n
    neg_pct = (counts.get(0, 0) + counts.get(1, 0)) / n
    pos_pct = (counts.get(3, 0) + counts.get(4, 0)) / n
    extreme_pct = (counts.get(0, 0) + counts.get(4, 0)) / n
    print(f"Pole summary:")
    print(f"  Negative (mult < 0): {neg_pct:.1%}")
    print(f"  Indifferent (mult=0): {idx2_pct:.1%}  [silences gradient for that dim]")
    print(f"  Positive (mult > 0): {pos_pct:.1%}")
    print(f"  Extreme (idx 0 or 4, |mult|=1.5): {extreme_pct:.1%}")
    print()

    # Per-trial concentration
    trial_concs = valid.groupby(["persona", "trial"])["category_idx"].apply(
        concentration_index)
    homogeneous = (trial_concs >= 0.999).sum()
    print(f"Per-trial homogeneity (all 5 visible dims same category):")
    print(f"  Trials with all-same answer: {homogeneous}/{len(trial_concs)} "
          f"({homogeneous/max(len(trial_concs),1):.1%})")
    print(f"  Mean concentration: {trial_concs.mean():.3f}  "
          f"(0.20=uniform, 1.00=all-same)")
    print()

    # Per-position bias
    print("Per-position breakdown (mean category index, 0=most negative, 4=most positive):")
    pos_means = valid.groupby("position")["category_idx"].agg(["mean", "std", "count"])
    print(pos_means.to_string(float_format=lambda x: f"{x:.2f}"))
    print()

    # Verdict
    print(f"H3 VERDICT — Indifferent rate: {idx2_pct:.1%}")
    if idx2_pct > 0.40:
        print("  ⚠  H3 SUPPORTED: many feedback signals get zeroed out. "
              "Effective rank of Ũ drops, prior dominates.")
    elif idx2_pct < 0.10:
        print("  ✓  H3 REFUTED: indifferent rate is low; gradient signal "
              "passes through.")
    else:
        print("  ~  Mixed: nontrivial indifferent rate but not dominant.")

    if extreme_pct > 0.7:
        print()
        print("  ⚠  ADDITIONAL: extreme-category rate is "
              f"{extreme_pct:.1%}. With mults={MULTS[0]}/{MULTS[4]}, this "
              "amplifies any miscategorization aggressively. "
              "Consider shrinking multiplier scale.")


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("output_dir", type=Path,
                   help="LLM sim output dir containing llm_cache.json")
    p.add_argument("--category-labels", default=None,
                   help="Pipe-separated 5 labels (default: movies/wines language)")
    p.add_argument("--save-csv", action="store_true",
                   help="Write per-trial decoded picks to CSV in output_dir")
    args = p.parse_args()

    cache_path = args.output_dir / "llm_cache.json"
    if not cache_path.exists():
        print(f"FATAL: {cache_path} not found", file=sys.stderr)
        sys.exit(1)
    with open(cache_path) as f:
        cache = json.load(f)
    print(f"Loaded {len(cache)} cache entries from {cache_path}\n")

    aff_df, aff_fail, aff_total = collect_affirm(cache)
    report_affirm(aff_df, aff_fail, aff_total)

    cat_labels = (args.category_labels.split("|") if args.category_labels
                  else CATEGORY_LABELS_DEFAULT)
    cat_df, cat_fail, cat_total = collect_categories(cache, cat_labels)
    report_categories(cat_df, cat_fail, cat_total, cat_labels)

    if args.save_csv:
        if not aff_df.empty:
            aff_path = args.output_dir / "diagnose_affirm.csv"
            aff_df.to_csv(aff_path, index=False)
            print(f"\nWrote {aff_path} ({len(aff_df)} rows)")
        if not cat_df.empty:
            cat_path = args.output_dir / "diagnose_categories.csv"
            cat_df.to_csv(cat_path, index=False)
            print(f"Wrote {cat_path} ({len(cat_df)} rows)")


if __name__ == "__main__":
    main()
