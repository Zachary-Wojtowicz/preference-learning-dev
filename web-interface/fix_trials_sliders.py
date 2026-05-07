#!/usr/bin/env python3
"""Fix already-trimmed experiment outputs by also filtering trials.json's
sliders to match experiment_config.json's reduced dimension set.

Use this when select_top_dims.py was run before the trials.json filtering
fix was added. Reads the dimension IDs from experiment_config.json and
trims each trial's sliders array accordingly. In-place update.

Usage:
  python web-interface/fix_trials_sliders.py web-interface/outputs/movies_100
"""
import json
import sys
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print("Usage: python fix_trials_sliders.py <experiment_dir>")
        sys.exit(1)
    out_dir = Path(sys.argv[1])
    cfg_path = out_dir / "experiment_config.json"
    trials_path = out_dir / "trials.json"

    with open(cfg_path) as f:
        cfg = json.load(f)
    keep_ids = set(d["id"] for d in cfg["dimensions"])
    print(f"Experiment config has {len(keep_ids)} dimensions: {sorted(keep_ids)}")

    with open(trials_path) as f:
        trials = json.load(f)

    n_trials = len(trials)
    n_orig_total, n_kept_total = 0, 0
    sample_orig = sample_kept = None
    for trial in trials:
        sl = trial.get("sliders") or []
        n_orig_total += len(sl)
        if sample_orig is None:
            sample_orig = [s.get("id") for s in sl]
        kept = [s for s in sl if s.get("id") in keep_ids]
        if sample_kept is None:
            sample_kept = [s.get("id") for s in kept]
        trial["sliders"] = kept
        n_kept_total += len(kept)

    print(f"Trials: {n_trials}")
    print(f"Sliders: {n_orig_total} -> {n_kept_total} "
          f"({n_kept_total // max(n_trials, 1)} per trial on average)")
    print(f"Sample trial 0 original IDs: {sample_orig}")
    print(f"Sample trial 0 kept IDs:     {sample_kept}")

    with open(trials_path, "w") as f:
        json.dump(trials, f)
    print(f"Wrote: {trials_path}")


if __name__ == "__main__":
    main()
