#!/usr/bin/env python3
"""Auto-restart wrapper for method_adaptive_directions/pipeline.py.

Runs the pipeline repeatedly with --resume until judgments_total is reached.
"""

import argparse
import csv
import subprocess
import time
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", required=True)
    p.add_argument("--max-restarts", type=int, default=50)
    p.add_argument("--restart-sleep-seconds", type=int, default=15)
    p.add_argument("pipeline_args", nargs=argparse.REMAINDER)
    return p.parse_args()


def completed_judgments(output_dir: Path) -> int:
    path = output_dir / "judgments.csv"
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        return sum(1 for _ in r)


def target_judgments(pipeline_args) -> int:
    if "--judgments-total" in pipeline_args:
        i = pipeline_args.index("--judgments-total")
        if i + 1 < len(pipeline_args):
            return int(pipeline_args[i + 1])
    return 120


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    pipeline_args = list(args.pipeline_args)
    if pipeline_args and pipeline_args[0] == "--":
        pipeline_args = pipeline_args[1:]
    tgt = target_judgments(pipeline_args)

    restarts = 0
    while True:
        done = completed_judgments(output_dir)
        if done >= tgt:
            print(f"[monitor] Completed {done}/{tgt}. Exiting monitor.", flush=True)
            return

        if restarts > args.max_restarts:
            raise RuntimeError(f"Exceeded max restarts ({args.max_restarts}). Progress: {done}/{tgt}")

        cmd = [".venv/bin/python", "method_adaptive_directions/pipeline.py", "--resume"] + pipeline_args
        print(f"[monitor] launch #{restarts + 1}: {' '.join(cmd)}", flush=True)
        proc = subprocess.run(cmd)
        restarts += 1

        done = completed_judgments(output_dir)
        if done >= tgt:
            print(f"[monitor] Completed {done}/{tgt}. Exiting monitor.", flush=True)
            return

        print(
            f"[monitor] pipeline exited rc={proc.returncode}; progress {done}/{tgt}; "
            f"sleeping {args.restart_sleep_seconds}s then restart",
            flush=True,
        )
        time.sleep(args.restart_sleep_seconds)


if __name__ == "__main__":
    main()
