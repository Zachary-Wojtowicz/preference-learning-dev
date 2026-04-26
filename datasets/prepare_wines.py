#!/usr/bin/env python3
"""Prepare the wine-130k dataset for the pipeline.

Adds a wine_id column (since the raw CSV only has a pandas index)
and drops rows with missing descriptions or prices.

Usage:
    python datasets/prepare_wines.py

Output:
    datasets/wines-prepared.csv
"""

import os
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_PATH = os.path.join(SCRIPT_DIR, "wine-130k.csv")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "wines-prepared.csv")


def main():
    if os.path.exists(OUTPUT_PATH):
        n = len(pd.read_csv(OUTPUT_PATH))
        print(f"{OUTPUT_PATH} already exists with {n} rows. Delete to re-run.")
        return

    df = pd.read_csv(INPUT_PATH, index_col=0)
    print(f"Loaded {len(df)} wines from {INPUT_PATH}")

    # Drop rows with missing critical fields
    before = len(df)
    df = df.dropna(subset=["description", "title", "variety"])
    print(f"  Dropped {before - len(df)} rows with missing description/title/variety")

    # Fill missing price with empty string (for template rendering)
    df["price"] = df["price"].fillna("")
    df["province"] = df["province"].fillna("")
    df["country"] = df["country"].fillna("")

    # Add wine_id column
    df = df.reset_index(drop=True)
    df.insert(0, "wine_id", [f"wine_{i}" for i in range(len(df))])

    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Wrote {len(df)} wines to {OUTPUT_PATH}")
    print(f"\nNext step:")
    print(f"  ./run_pipeline.sh configs/wines_100.yaml")


if __name__ == "__main__":
    main()
