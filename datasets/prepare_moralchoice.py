#!/usr/bin/env python3
"""Prepare the MoralChoice high-ambiguity dataset.

Each scenario is a moral dilemma with a context and two mutually exclusive
actions where neither is clearly preferred (values in tension). We preserve
the pair structure analogously to scruples_dilemmas.

Outputs:
    datasets/moralchoice-pairs.csv     — one row per dilemma (pair-level)
    datasets/moralchoice-actions.csv   — one row per action (for embedding/scoring)

Source: Scherrer et al. (2023), "Evaluating the Moral Beliefs Encoded in
       LLMs", NeurIPS 2023.
Data:  https://huggingface.co/datasets/ninoscherrer/moralchoice
       scenarios/moralchoice_high_ambiguity.csv (680 hand-written + generated
       scenarios where neither action is clearly preferred)

Usage:
    python datasets/prepare_moralchoice.py
    python datasets/prepare_moralchoice.py --from-local datasets/moralchoice_high_ambiguity.csv
"""

import argparse
import csv
import os
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PAIRS_OUTPUT = os.path.join(SCRIPT_DIR, "moralchoice-pairs.csv")
ACTIONS_OUTPUT = os.path.join(SCRIPT_DIR, "moralchoice-actions.csv")
RAW_URL = "https://huggingface.co/datasets/ninoscherrer/moralchoice/resolve/main/scenarios/moralchoice_high_ambiguity.csv"
RAW_PATH = os.path.join(SCRIPT_DIR, "moralchoice_high_ambiguity.csv")

CONSEQUENCE_COLS = [
    "death", "pain", "disable", "freedom", "pleasure",
    "deceive", "cheat", "break_promise", "break_law", "duty",
]


def download_raw():
    if os.path.exists(RAW_PATH):
        return RAW_PATH
    print(f"Downloading from {RAW_URL}...")
    urllib.request.urlretrieve(RAW_URL, RAW_PATH)
    print(f"  Saved to {RAW_PATH}")
    return RAW_PATH


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--from-local", default=None,
                        help="Path to local moralchoice_high_ambiguity.csv (skip download)")
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

    pair_rows = []
    action_rows = []

    with open(src, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sid = row["scenario_id"]
            context = row["context"].strip()
            a0 = row["action1"].strip()
            a1 = row["action2"].strip()
            if not context or not a0 or not a1:
                continue

            aid0 = f"{sid}_a0"
            aid1 = f"{sid}_a1"

            cons0 = {c: row.get(f"a1_{c}", "") for c in CONSEQUENCE_COLS}
            cons1 = {c: row.get(f"a2_{c}", "") for c in CONSEQUENCE_COLS}

            pair_rows.append({
                "dilemma_id": sid,
                "context": context,
                "action_0_id": aid0,
                "action_1_id": aid1,
                "action_0_description": a0,
                "action_1_description": a1,
                "generation_type": row.get("generation_type", ""),
                "generation_rule": row.get("generation_rule", ""),
                "ambiguity": row.get("ambiguity", ""),
                **{f"a0_{k}": v for k, v in cons0.items()},
                **{f"a1_{k}": v for k, v in cons1.items()},
            })

            for aid, desc in [(aid0, a0), (aid1, a1)]:
                action_rows.append({
                    "action_id": aid,
                    "dilemma_id": sid,
                    "context": context,
                    "description": desc,
                    "text": f"Situation: {context}\nAction: {desc}",
                })

    pair_fields = (
        ["dilemma_id", "context",
         "action_0_id", "action_1_id",
         "action_0_description", "action_1_description",
         "generation_type", "generation_rule", "ambiguity"]
        + [f"a0_{c}" for c in CONSEQUENCE_COLS]
        + [f"a1_{c}" for c in CONSEQUENCE_COLS]
    )
    with open(args.pairs_output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=pair_fields)
        writer.writeheader()
        writer.writerows(pair_rows)

    action_fields = ["action_id", "dilemma_id", "context", "description", "text"]
    with open(args.actions_output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=action_fields)
        writer.writeheader()
        writer.writerows(action_rows)

    gen_types = {}
    rules = {}
    for r in pair_rows:
        gen_types[r["generation_type"]] = gen_types.get(r["generation_type"], 0) + 1
        rules[r["generation_rule"]] = rules.get(r["generation_rule"], 0) + 1

    print(f"\nWrote {len(pair_rows)} dilemma pairs to {args.pairs_output}")
    print(f"Wrote {len(action_rows)} actions to {args.actions_output}")
    print(f"  Generation types: {gen_types}")
    print(f"  Rules: {len(rules)} unique ({sorted(rules.items(), key=lambda x: -x[1])[:5]} ...)")


if __name__ == "__main__":
    main()
