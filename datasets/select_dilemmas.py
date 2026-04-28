#!/usr/bin/env python3
"""Select diverse dilemma pairs from the Scruples dataset.

Unlike select_options.py (which selects individual options), this operates
at the dilemma level: it computes a dilemma embedding as the mean of the
two action embeddings, then runs farthest-first traversal on dilemma
embeddings to select a diverse subset.

Outputs:
    <output_dir>/selected_pairs.csv       — selected dilemma pairs
    <output_dir>/selected_actions.csv     — individual actions from selected pairs
    <output_dir>/selected_actions-embedded.parquet — embeddings for selected actions
    <output_dir>/predefined_pairs.json    — pairs in the format expected by dimension discovery

Usage:
    python datasets/select_dilemmas.py \
        --pairs-csv datasets/scruples-dilemmas-pairs.csv \
        --actions-parquet datasets/scruples-dilemmas-actions-embedded.parquet \
        --id-column action_id \
        --num-dilemmas 150 \
        --output-dir datasets/scruples_dilemmas \
        --seed 42
"""

import argparse
import csv
import json
import os
import sys

import numpy as np
import pyarrow.parquet as pq
import pandas as pd


def farthest_first(embeddings, indices, n, seed):
    """Farthest-first traversal on embeddings.

    Args:
        embeddings: (M, d) matrix
        indices: list of M candidate indices
        n: number to select
        seed: random seed

    Returns:
        list of n selected indices
    """
    rng = np.random.RandomState(seed)
    M = len(indices)
    n = min(n, M)

    # Normalize for cosine distance
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normed = embeddings / norms

    # Start with random point
    start = rng.randint(M)
    selected = [start]
    min_dist = 1.0 - (normed @ normed[start])  # cosine distance to first point

    for _ in range(1, n):
        # Pick the candidate farthest from all selected
        best = np.argmax(min_dist)
        selected.append(best)
        # Update min distances
        new_dist = 1.0 - (normed @ normed[best])
        min_dist = np.minimum(min_dist, new_dist)
        min_dist[selected] = -1  # don't re-select

    return [indices[i] for i in selected]


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--pairs-csv", required=True,
                        help="Path to scruples-dilemmas-pairs.csv")
    parser.add_argument("--actions-parquet", required=True,
                        help="Path to embedded actions parquet")
    parser.add_argument("--id-column", default="action_id")
    parser.add_argument("--embedding-column", default="embedding")
    parser.add_argument("--num-dilemmas", type=int, default=150,
                        help="Number of dilemma pairs to select")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    # Load pairs
    pairs_df = pd.read_csv(args.pairs_csv)
    print(f"Loaded {len(pairs_df)} dilemma pairs")

    # Load action embeddings
    actions_pq = pq.read_table(args.actions_parquet)
    actions_df = actions_pq.to_pandas()
    actions_df[args.id_column] = actions_df[args.id_column].astype(str)

    # Build embedding lookup: action_id -> embedding vector
    emb_lookup = {}
    for _, row in actions_df.iterrows():
        aid = str(row[args.id_column])
        vec = row[args.embedding_column]
        if isinstance(vec, (list, np.ndarray)):
            emb_lookup[aid] = np.array(vec, dtype=np.float64)

    print(f"  {len(emb_lookup)} action embeddings loaded")

    # Compute dilemma-level embeddings (mean of two action embeddings)
    valid_pairs = []
    dilemma_embeddings = []

    for idx, row in pairs_df.iterrows():
        aid0 = str(row["action_0_id"])
        aid1 = str(row["action_1_id"])
        if aid0 in emb_lookup and aid1 in emb_lookup:
            mean_emb = (emb_lookup[aid0] + emb_lookup[aid1]) / 2.0
            valid_pairs.append(idx)
            dilemma_embeddings.append(mean_emb)

    print(f"  {len(valid_pairs)} pairs have both actions embedded")

    if len(valid_pairs) < args.num_dilemmas:
        print(f"  Warning: only {len(valid_pairs)} valid pairs, "
              f"requested {args.num_dilemmas}")
        args.num_dilemmas = len(valid_pairs)

    dilemma_embeddings = np.array(dilemma_embeddings)

    # Farthest-first selection
    print(f"Selecting {args.num_dilemmas} diverse dilemmas...")
    selected_local = farthest_first(
        dilemma_embeddings,
        list(range(len(valid_pairs))),
        args.num_dilemmas,
        args.seed,
    )
    selected_pair_indices = [valid_pairs[i] for i in selected_local]
    selected_pairs_df = pairs_df.iloc[selected_pair_indices].reset_index(drop=True)

    # Extract unique actions from selected pairs
    selected_action_ids = set()
    for _, row in selected_pairs_df.iterrows():
        selected_action_ids.add(str(row["action_0_id"]))
        selected_action_ids.add(str(row["action_1_id"]))

    selected_actions_df = actions_df[
        actions_df[args.id_column].isin(selected_action_ids)
    ].reset_index(drop=True)

    # Build predefined_pairs.json for dimension discovery
    has_gold = "gold_label" in selected_pairs_df.columns
    has_controversial = "controversial" in selected_pairs_df.columns
    predefined_pairs = []
    for _, row in selected_pairs_df.iterrows():
        entry = {
            "option_a_id": str(row["action_0_id"]),
            "option_b_id": str(row["action_1_id"]),
            "dilemma_id": str(row["dilemma_id"]),
        }
        if has_gold:
            entry["gold_label"] = int(row["gold_label"]) if pd.notna(row["gold_label"]) else -1
        if has_controversial:
            entry["controversial"] = bool(row["controversial"])
        predefined_pairs.append(entry)

    # Write outputs
    os.makedirs(args.output_dir, exist_ok=True)

    pairs_path = os.path.join(args.output_dir, "selected_pairs.csv")
    selected_pairs_df.to_csv(pairs_path, index=False)

    actions_csv_path = os.path.join(args.output_dir, "selected_actions.csv")
    # Write CSV without embedding column
    csv_cols = [c for c in selected_actions_df.columns
                if c != args.embedding_column]
    selected_actions_df[csv_cols].to_csv(actions_csv_path, index=False)

    actions_pq_path = os.path.join(args.output_dir, "selected_actions-embedded.parquet")
    selected_actions_df.to_parquet(actions_pq_path, index=False)

    pairs_json_path = os.path.join(args.output_dir, "predefined_pairs.json")
    with open(pairs_json_path, "w", encoding="utf-8") as f:
        json.dump(predefined_pairs, f, indent=2)

    # Summary
    print(f"\nWrote {len(selected_pairs_df)} pairs to {pairs_path}")
    print(f"Wrote {len(selected_actions_df)} actions to {actions_csv_path}")
    print(f"Wrote {len(selected_actions_df)} actions to {actions_pq_path}")
    print(f"Wrote {len(predefined_pairs)} pairs to {pairs_json_path}")
    if has_controversial:
        n_controversial = sum(1 for _, r in selected_pairs_df.iterrows()
                              if r["controversial"])
        print(f"  Controversial: {n_controversial} "
              f"({100*n_controversial/len(selected_pairs_df):.1f}%)")
    print(f"  Unique actions: {len(selected_action_ids)}")


if __name__ == "__main__":
    main()
