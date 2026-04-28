#!/usr/bin/env python3
"""Prepare the DailyDilemmas dataset.

Each dilemma is an everyday-life situation with two opposing actions
(to_do / not_to_do) annotated with the human values they invoke. We pair
the two action rows by dilemma_idx into a pair-level CSV analogous to
scruples_dilemmas.

Outputs:
    datasets/dailydilemmas-pairs.csv     — one row per dilemma (pair-level)
    datasets/dailydilemmas-actions.csv   — one row per action (for embedding/scoring)

Source: Chiu et al. (2024), "DailyDilemmas: Revealing Value Preferences of
       LLMs with Quandaries of Daily Life", ICLR 2025.
Data:  https://huggingface.co/datasets/kellycyy/daily_dilemmas
       dilemma_to_action_to_values_aggregated.csv (2,720 rows = 1,360
       dilemmas × 2 actions, with values_aggregated annotations)

Usage:
    python datasets/prepare_dailydilemmas.py
    python datasets/prepare_dailydilemmas.py --from-local datasets/dilemma_to_action_to_values_aggregated.csv
"""

import argparse
import ast
import csv
import os
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PAIRS_OUTPUT = os.path.join(SCRIPT_DIR, "dailydilemmas-pairs.csv")
ACTIONS_OUTPUT = os.path.join(SCRIPT_DIR, "dailydilemmas-actions.csv")
RAW_URL = "https://huggingface.co/datasets/kellycyy/daily_dilemmas/resolve/main/dilemma_to_action_to_values_aggregated.csv"
RAW_PATH = os.path.join(SCRIPT_DIR, "dilemma_to_action_to_values_aggregated.csv")


def download_raw():
    if os.path.exists(RAW_PATH):
        return RAW_PATH
    print(f"Downloading from {RAW_URL}...")
    urllib.request.urlretrieve(RAW_URL, RAW_PATH)
    print(f"  Saved to {RAW_PATH}")
    return RAW_PATH


def parse_values(raw):
    """Parse the values_aggregated field (Python-list-as-string) into
    a comma-joined string for CSV-friendly storage."""
    if not raw:
        return ""
    try:
        vals = ast.literal_eval(raw)
        if isinstance(vals, list):
            return ", ".join(str(v) for v in vals)
    except (SyntaxError, ValueError):
        pass
    return raw


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--from-local", default=None,
                        help="Path to local CSV (skip download)")
    parser.add_argument("--pairs-output", default=PAIRS_OUTPUT)
    parser.add_argument("--actions-output", default=ACTIONS_OUTPUT)
    args = parser.parse_args()

    if os.path.exists(args.pairs_output) and os.path.exists(args.actions_output):
        import pandas as pd
        np_ = len(pd.read_csv(args.pairs_output))
        na = len(pd.read_csv(args.actions_output))
        print(f"Outputs already exist: {np_} pairs, {na} actions. Delete to re-run.")
        return

    src = args.from_local or download_raw()

    # Group rows by dilemma_idx
    by_dilemma = {}
    with open(src, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            did = row["dilemma_idx"]
            by_dilemma.setdefault(did, []).append(row)

    pair_rows = []
    action_rows = []
    skipped = 0

    for did, rows in by_dilemma.items():
        if len(rows) != 2:
            skipped += 1
            continue

        # Sort so to_do comes first (action_0), not_to_do second (action_1)
        rows_sorted = sorted(rows, key=lambda r: 0 if r["action_type"] == "to_do" else 1)
        r0, r1 = rows_sorted
        if r0["action_type"] != "to_do" or r1["action_type"] != "not_to_do":
            skipped += 1
            continue

        situation = r0["dilemma_situation"].strip()
        basic = r0.get("basic_situation", "").strip()
        topic_group = r0.get("topic_group", "")
        topic = r0.get("topic", "")

        a0 = r0["action"].strip()
        a1 = r1["action"].strip()
        cons0 = r0.get("negative_consequence", "").strip()
        cons1 = r1.get("negative_consequence", "").strip()
        vals0 = parse_values(r0.get("values_aggregated", ""))
        vals1 = parse_values(r1.get("values_aggregated", ""))

        if not situation or not a0 or not a1:
            skipped += 1
            continue

        aid0 = f"dd_{did}_to_do"
        aid1 = f"dd_{did}_not_to_do"

        pair_rows.append({
            "dilemma_id": f"dd_{did}",
            "basic_situation": basic,
            "dilemma_situation": situation,
            "topic": topic,
            "topic_group": topic_group,
            "action_0_id": aid0,
            "action_1_id": aid1,
            "action_0_description": a0,
            "action_1_description": a1,
            "action_0_consequence": cons0,
            "action_1_consequence": cons1,
            "action_0_values": vals0,
            "action_1_values": vals1,
        })

        for aid, desc, cons, vals in [
            (aid0, a0, cons0, vals0),
            (aid1, a1, cons1, vals1),
        ]:
            action_rows.append({
                "action_id": aid,
                "dilemma_id": f"dd_{did}",
                "situation": situation,
                "description": desc,
                "consequence": cons,
                "values": vals,
                "topic_group": topic_group,
                "text": f"Situation: {situation}\nAction: {desc}\nConsequence: {cons}",
            })

    pair_fields = [
        "dilemma_id", "basic_situation", "dilemma_situation",
        "topic", "topic_group",
        "action_0_id", "action_1_id",
        "action_0_description", "action_1_description",
        "action_0_consequence", "action_1_consequence",
        "action_0_values", "action_1_values",
    ]
    with open(args.pairs_output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=pair_fields)
        writer.writeheader()
        writer.writerows(pair_rows)

    action_fields = [
        "action_id", "dilemma_id", "situation", "description",
        "consequence", "values", "topic_group", "text",
    ]
    with open(args.actions_output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=action_fields)
        writer.writeheader()
        writer.writerows(action_rows)

    topic_counts = {}
    for r in pair_rows:
        tg = r["topic_group"]
        topic_counts[tg] = topic_counts.get(tg, 0) + 1

    print(f"\nWrote {len(pair_rows)} dilemma pairs to {args.pairs_output}")
    print(f"Wrote {len(action_rows)} actions to {args.actions_output}")
    if skipped:
        print(f"  Skipped {skipped} dilemmas (not exactly 2 actions or missing fields)")
    print(f"  Topic groups: {sorted(topic_counts.items(), key=lambda x: -x[1])[:8]} ...")


if __name__ == "__main__":
    main()
