#!/usr/bin/env python3
"""Prepare the Community Alignment dataset for the within-choice-set pipeline.

Each prompt in CoAlign has 4 candidate LLM responses (letters A/B/C/D), and
each annotator picks their best — yielding 3 forced-choice rows per
(annotator, prompt) session: best vs each of the other 3 letters.

We treat each ``choice_set_id`` as analogous to a dailydilemmas situation:
a prompt + its 4 candidate responses, with all 6 within-set pair
comparisons valid. Cross-set pairs are not emitted (responses to different
prompts cannot be compared meaningfully at the option level).

Filters applied:
  - assigned_lang == 'en'
  - in_balanced_subset_10 == True

Outputs:
  datasets/coalign-options.csv  — one row per response (set x letter)
  datasets/coalign-pairs.csv    — one row per within-set pair (6 per set)

Source parquet (already on disk):
  datasets/coalign_pairwise_comparisons_ge10.parquet
  (curated >=10 raters/letter subset of facebookresearch/community-alignment-dataset)

Usage:
  python datasets/prepare_coalign.py
"""

import argparse
import csv
import os
from collections import defaultdict
from itertools import combinations

import pandas as pd
import pyarrow.parquet as pq

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT = os.path.join(SCRIPT_DIR, "coalign_pairwise_comparisons_ge10.parquet")
OPTIONS_OUTPUT = os.path.join(SCRIPT_DIR, "coalign-options.csv")
PAIRS_OUTPUT = os.path.join(SCRIPT_DIR, "coalign-pairs.csv")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--input-parquet", default=DEFAULT_INPUT)
    parser.add_argument("--options-output", default=OPTIONS_OUTPUT)
    parser.add_argument("--pairs-output", default=PAIRS_OUTPUT)
    parser.add_argument("--language", default="en")
    parser.add_argument("--balanced-column", default="in_balanced_subset_10",
                        help="Boolean column to filter by (set empty to skip)")
    args = parser.parse_args()

    if os.path.exists(args.options_output) and os.path.exists(args.pairs_output):
        no = len(pd.read_csv(args.options_output))
        np_ = len(pd.read_csv(args.pairs_output))
        print(f"Outputs already exist: {no} options, {np_} pairs. Delete to re-run.")
        return

    print(f"Loading {args.input_parquet}...")
    df = pq.read_table(args.input_parquet).to_pandas()
    print(f"  {len(df)} total rows")

    df = df[df["assigned_lang"] == args.language].copy()
    print(f"  {len(df)} after language filter ({args.language})")

    if args.balanced_column:
        df = df[df[args.balanced_column] == True].copy()
        print(f"  {len(df)} after {args.balanced_column} filter")

    set_to_letters = defaultdict(dict)
    set_to_prompt = {}

    for _, row in df.iterrows():
        sid = row["choice_set_id"]
        set_to_prompt.setdefault(sid, row["prompt_text"])
        for letter_col, text_col in [("preferred_letter", "preferred_text"),
                                     ("other_letter", "other_text")]:
            letter = row[letter_col]
            text = row[text_col]
            if letter and text:
                set_to_letters[sid].setdefault(letter, text)

    pair_votes = defaultdict(int)
    set_annotators = defaultdict(set)
    for _, row in df.iterrows():
        sid = row["choice_set_id"]
        winner = row["preferred_letter"]
        loser = row["other_letter"]
        pair_votes[(sid, winner, loser)] += 1
        set_annotators[sid].add(row["annotator_id"])

    eligible = [sid for sid, letters in set_to_letters.items()
                if set(letters.keys()) >= {"A", "B", "C", "D"}]
    print(f"  {len(eligible)} choice sets with all 4 letters present")

    option_rows = []
    pair_rows = []
    for sid in eligible:
        prompt = set_to_prompt[sid]
        n_annotators = len(set_annotators[sid])
        sid_short = sid[:12]

        for letter in ["A", "B", "C", "D"]:
            response = set_to_letters[sid][letter]
            option_id = f"co_{sid_short}_{letter}"
            option_rows.append({
                "action_id": option_id,
                "set_id": sid,
                "letter": letter,
                "prompt": prompt,
                "description": response,
                "text": f"Prompt: {prompt}\nResponse: {response}",
            })

        for la, lb in combinations(["A", "B", "C", "D"], 2):
            aid = f"co_{sid_short}_{la}"
            bid = f"co_{sid_short}_{lb}"
            n_a_over_b = pair_votes.get((sid, la, lb), 0)
            n_b_over_a = pair_votes.get((sid, lb, la), 0)
            pair_rows.append({
                "set_id": sid,
                "dilemma_id": sid,  # alias for downstream tooling that reads dilemma_id
                "situation": prompt,  # rendered as shared context above option cards
                "action_0_id": aid,
                "action_1_id": bid,
                "action_0_letter": la,
                "action_1_letter": lb,
                "action_0_description": set_to_letters[sid][la],
                "action_1_description": set_to_letters[sid][lb],
                "n_annotators_pref_0": n_a_over_b,
                "n_annotators_pref_1": n_b_over_a,
                "n_annotators_set": n_annotators,
            })

    option_fields = ["action_id", "set_id", "letter", "prompt", "description", "text"]
    with open(args.options_output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=option_fields)
        writer.writeheader()
        writer.writerows(option_rows)

    pair_fields = ["set_id", "dilemma_id", "situation",
                   "action_0_id", "action_1_id",
                   "action_0_letter", "action_1_letter",
                   "action_0_description", "action_1_description",
                   "n_annotators_pref_0", "n_annotators_pref_1", "n_annotators_set"]
    with open(args.pairs_output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=pair_fields)
        writer.writeheader()
        writer.writerows(pair_rows)

    print(f"\nWrote {len(option_rows)} options to {args.options_output}")
    print(f"Wrote {len(pair_rows)} pairs to {args.pairs_output}")
    print(f"  ({len(eligible)} sets x 4 options = {len(eligible)*4}, "
          f"x 6 pairs = {len(eligible)*6})")


if __name__ == "__main__":
    main()
