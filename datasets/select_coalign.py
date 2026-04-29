#!/usr/bin/env python3
"""Select diverse coalign choice sets via farthest-first traversal.

Each "choice set" is a prompt + 4 candidate responses (4 options).
We compute a per-set embedding as the mean of its 4 option embeddings,
then run farthest-first on those set-level embeddings to pick a diverse
subset.

Outputs:
    <output_dir>/selected_options.csv               — 4 x N option rows
    <output_dir>/selected_options-embedded.parquet  — option embeddings
    <output_dir>/selected_pairs.csv                 — 6 x N pair rows
    <output_dir>/predefined_pairs.json              — flat list of within-set pairs

Usage:
    python datasets/select_coalign.py \\
        --pairs-csv datasets/coalign-pairs.csv \\
        --options-parquet datasets/coalign-options-embedded.parquet \\
        --num-sets 50 \\
        --output-dir datasets/coalign_50 \\
        --seed 42
"""

import argparse
import json
import os

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


def farthest_first(embeddings, n, seed):
    rng = np.random.RandomState(seed)
    M = len(embeddings)
    n = min(n, M)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normed = embeddings / norms
    start = rng.randint(M)
    selected = [start]
    min_dist = 1.0 - (normed @ normed[start])
    for _ in range(1, n):
        i = int(np.argmax(min_dist))
        selected.append(i)
        new_dist = 1.0 - (normed @ normed[i])
        min_dist = np.minimum(min_dist, new_dist)
        min_dist[selected] = -1
    return selected


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--pairs-csv", required=True)
    ap.add_argument("--options-parquet", required=True)
    ap.add_argument("--id-column", default="action_id")
    ap.add_argument("--embedding-column", default="embedding")
    ap.add_argument("--num-sets", type=int, default=50)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    pairs_df = pd.read_csv(args.pairs_csv)
    print(f"Loaded {len(pairs_df)} pairs across "
          f"{pairs_df['set_id'].nunique()} sets")

    options_df = pq.read_table(args.options_parquet).to_pandas()
    options_df[args.id_column] = options_df[args.id_column].astype(str)
    print(f"Loaded {len(options_df)} options with embeddings")

    emb_lookup = {
        str(row[args.id_column]): np.array(row[args.embedding_column], dtype=np.float64)
        for _, row in options_df.iterrows()
    }

    set_ids = []
    set_embeddings = []
    for sid, grp in pairs_df.groupby("set_id"):
        action_ids = set(grp["action_0_id"].astype(str)) | set(grp["action_1_id"].astype(str))
        embs = [emb_lookup[a] for a in action_ids if a in emb_lookup]
        if len(embs) != 4:
            continue
        set_ids.append(sid)
        set_embeddings.append(np.mean(embs, axis=0))

    set_embeddings = np.array(set_embeddings)
    print(f"  {len(set_ids)} sets with all 4 embeddings")

    if len(set_ids) < args.num_sets:
        print(f"  Warning: only {len(set_ids)} eligible, requested {args.num_sets}")
        args.num_sets = len(set_ids)

    print(f"Selecting {args.num_sets} diverse sets...")
    selected_idx = farthest_first(set_embeddings, args.num_sets, args.seed)
    selected_set_ids = {set_ids[i] for i in selected_idx}

    selected_pairs_df = (pairs_df[pairs_df["set_id"].isin(selected_set_ids)]
                         .reset_index(drop=True))
    selected_action_ids = (set(selected_pairs_df["action_0_id"].astype(str))
                           | set(selected_pairs_df["action_1_id"].astype(str)))
    selected_options_df = (options_df[options_df[args.id_column].astype(str).isin(selected_action_ids)]
                           .reset_index(drop=True))

    predefined_pairs = [
        {
            "option_a_id": str(row["action_0_id"]),
            "option_b_id": str(row["action_1_id"]),
            "set_id": str(row["set_id"]),
        }
        for _, row in selected_pairs_df.iterrows()
    ]

    os.makedirs(args.output_dir, exist_ok=True)
    pairs_path = os.path.join(args.output_dir, "selected_pairs.csv")
    selected_pairs_df.to_csv(pairs_path, index=False)

    options_csv_path = os.path.join(args.output_dir, "selected_options.csv")
    csv_cols = [c for c in selected_options_df.columns if c != args.embedding_column]
    selected_options_df[csv_cols].to_csv(options_csv_path, index=False)

    options_pq_path = os.path.join(args.output_dir, "selected_options-embedded.parquet")
    selected_options_df.to_parquet(options_pq_path, index=False)

    pairs_json_path = os.path.join(args.output_dir, "predefined_pairs.json")
    with open(pairs_json_path, "w", encoding="utf-8") as f:
        json.dump(predefined_pairs, f, indent=2)

    print(f"\nWrote {len(selected_pairs_df)} pairs to {pairs_path}")
    print(f"Wrote {len(selected_options_df)} options to {options_csv_path}")
    print(f"Wrote {len(selected_options_df)} options to {options_pq_path}")
    print(f"Wrote {len(predefined_pairs)} pairs to {pairs_json_path}")
    print(f"  Unique sets selected: {len(selected_set_ids)}")


if __name__ == "__main__":
    main()
