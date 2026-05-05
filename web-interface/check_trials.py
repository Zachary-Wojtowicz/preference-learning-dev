#!/usr/bin/env python3
"""Quick diagnostic: count unique dim IDs and sliders per trial in trials.json."""
import json
import sys
from collections import Counter
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print("Usage: python check_trials.py <experiment_dir>")
        sys.exit(1)
    out_dir = Path(sys.argv[1])

    with open(out_dir / "experiment_config.json") as f:
        cfg = json.load(f)
    cfg_dim_ids = sorted(d["id"] for d in cfg["dimensions"])
    print(f"experiment_config.json: {len(cfg_dim_ids)} dimensions")
    print(f"  IDs: {cfg_dim_ids}")
    print()

    with open(out_dir / "trials.json") as f:
        trials = json.load(f)

    n_trials = len(trials)
    slider_counts = Counter()
    all_dim_ids = set()
    for trial in trials:
        sl = trial.get("sliders") or []
        slider_counts[len(sl)] += 1
        for s in sl:
            all_dim_ids.add(s.get("id"))

    print(f"trials.json: {n_trials} trials")
    print(f"  Sliders per trial:")
    for n, c in sorted(slider_counts.items()):
        print(f"    {n} sliders: {c} trials")
    print(f"  Unique dim IDs across all sliders: {len(all_dim_ids)}")
    print(f"  IDs: {sorted(all_dim_ids)}")
    print()

    # Check trial_projections.json
    with open(out_dir / "trial_projections.json") as f:
        tp = json.load(f)
    raw_lens = Counter(len(t.get("raw_projection", [])) for t in tp)
    rand_lens = Counter(len(t.get("random_projection", [])) for t in tp)
    print(f"trial_projections.json: {len(tp)} entries")
    print(f"  raw_projection lengths: {dict(raw_lens)}")
    print(f"  random_projection lengths: {dict(rand_lens)}")

    # Cross-check
    extra_in_trials = all_dim_ids - set(cfg_dim_ids)
    missing_in_trials = set(cfg_dim_ids) - all_dim_ids
    if extra_in_trials:
        print(f"\nWARNING: trials.json has dim IDs NOT in experiment_config.json:")
        print(f"  {sorted(extra_in_trials)}")
        print(f"  -> Run select_top_dims.py (or fix_trials_sliders.py) to filter.")
    if missing_in_trials:
        print(f"\nNOTE: experiment_config.json has dim IDs missing from trials.json:")
        print(f"  {sorted(missing_in_trials)}")
    if not extra_in_trials and not missing_in_trials:
        print(f"\nOK: trials.json and experiment_config.json have matching dim IDs.")


if __name__ == "__main__":
    main()
