#!/usr/bin/env python3
"""Download and prepare the Scruples dilemmas dataset for the pipeline.

The Scruples Dilemmas contain paired actions where crowd workers judged
which was less ethical. We extract the individual actions as our option set.

Usage:
    python datasets/prepare_scruples.py
    python datasets/prepare_scruples.py --from-local /path/to/dilemmas/

Output:
    datasets/scruples-dilemmas.csv  (action_id, description)
"""

import argparse
import csv
import json
import os
import sys
import tarfile
import tempfile
import urllib.request

# The Scruples data is hosted on Google Cloud Storage by AI2.
# If this URL stops working, check https://github.com/allenai/scruples
DATA_URL = "https://storage.googleapis.com/ai2-mosaic-public/projects/scruples/v1.0/data/dilemmas.tar.gz"
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scruples-dilemmas.csv")


def download_and_extract():
    """Download the dilemmas tarball and return the extracted directory."""
    print(f"Downloading Scruples dilemmas from {DATA_URL}...")
    tmpdir = tempfile.mkdtemp()
    tarpath = os.path.join(tmpdir, "dilemmas.tar.gz")
    urllib.request.urlretrieve(url=DATA_URL, filename=tarpath)
    print(f"Downloaded to {tarpath}")

    print("Extracting...")
    with tarfile.open(tarpath, "r:gz") as tar:
        tar.extractall(tmpdir, filter="data")

    return tmpdir


def load_jsonl(path):
    """Load a JSONL file into a list of dicts."""
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def extract_actions(data_dir):
    """Extract unique actions from the dilemmas splits.

    Each JSONL row looks like:
    {
      "id": "...",
      "actions": [
        {"id": "...", "description": "..."},
        {"id": "...", "description": "..."}
      ],
      "gold_label": 0,
      ...
    }
    """
    actions = {}  # action_id -> description

    for root, dirs, files in os.walk(data_dir):
        for fname in sorted(files):
            if not fname.endswith(".jsonl"):
                continue
            fpath = os.path.join(root, fname)
            print(f"  Reading {fname}...")
            try:
                rows = load_jsonl(fpath)
            except Exception as e:
                print(f"  Skipping {fname}: {e}")
                continue

            for row in rows:
                # Actions are in an "actions" list
                for action in row.get("actions", []):
                    aid = action.get("id", "")
                    desc = action.get("description", "")
                    if aid and desc and len(desc) > 5:
                        actions[aid] = desc

    return actions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-local", default=None,
                        help="Path to already-downloaded dilemmas directory")
    parser.add_argument("--output", default=OUTPUT_PATH,
                        help=f"Output CSV path (default: {OUTPUT_PATH})")
    args = parser.parse_args()

    output_path = args.output

    if os.path.exists(output_path):
        with open(output_path) as f:
            n = sum(1 for _ in f) - 1
        print(f"{output_path} already exists with {n} rows. Delete it to re-run.")
        return

    if args.from_local:
        data_dir = args.from_local
        cleanup = False
    else:
        data_dir = download_and_extract()
        cleanup = True

    actions = extract_actions(data_dir)
    print(f"\nExtracted {len(actions)} unique actions")

    if not actions:
        print("ERROR: No actions found.")
        sys.exit(1)

    # Write CSV
    sorted_actions = sorted(actions.items())
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["action_id", "description"])
        writer.writeheader()
        for aid, desc in sorted_actions:
            writer.writerow({"action_id": aid, "description": desc})

    print(f"Wrote {len(sorted_actions)} actions to {output_path}")

    if cleanup:
        import shutil
        shutil.rmtree(data_dir)
        print("Cleaned up temp files")

    print("\nFirst 5 actions:")
    for aid, desc in sorted_actions[:5]:
        print(f"  {aid}: {desc}")

    print(f"\nNext step:")
    print(f"  ./run_pipeline.sh configs/scruples_200.yaml")


if __name__ == "__main__":
    main()
