#!/usr/bin/env python3
"""Prepare the Scruples dilemmas dataset preserving pair structure.

Each scruples dilemma is a pair of actions from the same AITA post,
with crowd annotations on which action is less ethical. We preserve
this pairing for both dimension discovery and experiment trials.

Outputs:
    datasets/scruples-dilemmas-pairs.csv     — one row per dilemma (pair-level)
    datasets/scruples-dilemmas-actions.csv   — one row per action (for embedding/scoring)

Source: Lourie et al. (2021), "Scruples: A Corpus of Community Ethical
       Judgments on 32,000 Real-Life Anecdotes", AAAI 2021.
Data:  https://storage.googleapis.com/ai2-mosaic-public/projects/scruples/v1.0/data/dilemmas.tar.gz

Usage:
    python datasets/prepare_scruples_v2.py
    python datasets/prepare_scruples_v2.py --from-local datasets/dilemmas/
"""

import argparse
import csv
import json
import os
import sys
import tarfile
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PAIRS_OUTPUT = os.path.join(SCRIPT_DIR, "scruples-dilemmas-pairs.csv")
ACTIONS_OUTPUT = os.path.join(SCRIPT_DIR, "scruples-dilemmas-actions.csv")
TAR_URL = "https://storage.googleapis.com/ai2-mosaic-public/projects/scruples/v1.0/data/dilemmas.tar.gz"
TAR_PATH = os.path.join(SCRIPT_DIR, "dilemmas.tar.gz")


def download_and_extract():
    """Download and extract the dilemmas tarball."""
    extract_dir = os.path.join(SCRIPT_DIR, "dilemmas")
    if os.path.isdir(extract_dir):
        return extract_dir

    if not os.path.exists(TAR_PATH):
        print(f"Downloading from {TAR_URL}...")
        urllib.request.urlretrieve(TAR_URL, TAR_PATH)
        print(f"  Saved to {TAR_PATH}")

    print(f"Extracting to {extract_dir}...")
    with tarfile.open(TAR_PATH, "r:gz") as tar:
        tar.extractall(SCRIPT_DIR)
    return extract_dir


def load_jsonl_files(data_dir):
    """Load all dilemma JSONL files from the data directory."""
    dilemmas = []
    for fname in sorted(os.listdir(data_dir)):
        if not fname.endswith(".jsonl"):
            continue
        fpath = os.path.join(data_dir, fname)
        split = fname.replace(".scruples-dilemmas.jsonl", "")
        with open(fpath, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                row["_split"] = split
                dilemmas.append(row)
    print(f"  Loaded {len(dilemmas)} dilemmas across splits")
    return dilemmas


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--from-local", default=None,
                        help="Path to local dilemmas/ directory (skip download)")
    parser.add_argument("--pairs-output", default=PAIRS_OUTPUT)
    parser.add_argument("--actions-output", default=ACTIONS_OUTPUT)
    args = parser.parse_args()

    if os.path.exists(args.pairs_output) and os.path.exists(args.actions_output):
        import pandas as pd
        np = len(pd.read_csv(args.pairs_output))
        na = len(pd.read_csv(args.actions_output))
        print(f"Outputs already exist: {np} pairs, {na} actions. Delete to re-run.")
        return

    # Load data
    if args.from_local:
        data_dir = args.from_local
    else:
        data_dir = download_and_extract()

    dilemmas = load_jsonl_files(data_dir)

    # Build pair-level and action-level CSVs
    pair_rows = []
    action_rows = []
    seen_actions = set()

    for d in dilemmas:
        actions = d.get("actions", [])
        if len(actions) != 2:
            continue

        a0 = actions[0]
        a1 = actions[1]
        desc0 = a0.get("description", "").strip()
        desc1 = a1.get("description", "").strip()

        if not desc0 or not desc1:
            continue
        if len(desc0) < 10 or len(desc1) < 10:
            continue

        aid0 = a0["id"]
        aid1 = a1["id"]

        gold = d.get("gold_annotations", [0, 0])
        gold_label = d.get("gold_label", -1)
        controversial = d.get("controversial", False)

        pair_rows.append({
            "dilemma_id": d["id"],
            "action_0_id": aid0,
            "action_1_id": aid1,
            "action_0_description": desc0,
            "action_1_description": desc1,
            "gold_votes_0": gold[0] if len(gold) > 0 else 0,
            "gold_votes_1": gold[1] if len(gold) > 1 else 0,
            "gold_label": gold_label,
            "controversial": controversial,
            "split": d.get("_split", ""),
        })

        # Action-level rows (deduplicated — same action can appear in
        # multiple dilemmas in the original data)
        for aid, desc in [(aid0, desc0), (aid1, desc1)]:
            if aid not in seen_actions:
                seen_actions.add(aid)
                action_rows.append({
                    "action_id": aid,
                    "description": desc,
                    "text": f"Action: {desc}",
                })

    # Write pairs CSV
    pair_fields = ["dilemma_id", "action_0_id", "action_1_id",
                   "action_0_description", "action_1_description",
                   "gold_votes_0", "gold_votes_1", "gold_label",
                   "controversial", "split"]
    with open(args.pairs_output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=pair_fields)
        writer.writeheader()
        writer.writerows(pair_rows)

    # Write actions CSV
    action_fields = ["action_id", "description", "text"]
    with open(args.actions_output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=action_fields)
        writer.writeheader()
        writer.writerows(action_rows)

    # Stats
    n_controversial = sum(1 for r in pair_rows if r["controversial"])
    splits = {}
    for r in pair_rows:
        s = r["split"]
        splits[s] = splits.get(s, 0) + 1

    print(f"\nWrote {len(pair_rows)} dilemma pairs to {args.pairs_output}")
    print(f"Wrote {len(action_rows)} unique actions to {args.actions_output}")
    print(f"  Controversial: {n_controversial} ({100*n_controversial/len(pair_rows):.1f}%)")
    print(f"  Splits: {splits}")
    print(f"\nNext step:")
    print(f"  ./run_pipeline.sh configs/scruples_dilemmas.yaml")


if __name__ == "__main__":
    main()
