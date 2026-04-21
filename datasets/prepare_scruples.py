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
# for the current download link.
DATA_URL = "https://storage.googleapis.com/ai2-mosaic-public/projects/scruples/v1.0/data/dilemmas.tar.gz"
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scruples-dilemmas.csv")


def download_and_extract():
    """Download the dilemmas tarball and return the extracted directory."""
    print(f"Downloading Scruples dilemmas from {DATA_URL}...")
    tmpdir = tempfile.mkdtemp()
    tarpath = os.path.join(tmpdir, "dilemmas.tar.gz")

    urllib.request.urlretrieve(DATA_URL, tarpath)
    print(f"Downloaded to {tarpath}")

    print("Extracting...")
    with tarfile.open(tarpath, "r:gz") as tar:
        tar.extractall(tmpdir)

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
    """Extract unique actions from the dilemmas splits."""
    actions = {}  # action_id -> description

    # Look for JSONL files in various possible locations
    for root, dirs, files in os.walk(data_dir):
        for fname in sorted(files):
            if not (fname.endswith(".jsonl") or fname.endswith(".json")):
                continue
            fpath = os.path.join(root, fname)
            print(f"  Reading {fpath}...")
            try:
                rows = load_jsonl(fpath)
            except Exception as e:
                print(f"  Skipping {fpath}: {e}")
                continue

            for row in rows:
                # Dilemmas have action pairs — extract both sides
                for key in ["action0", "action1"]:
                    if key in row:
                        action = row[key]
                        if isinstance(action, dict):
                            aid = action.get("id", "")
                            desc = action.get("description", "")
                        elif isinstance(action, str):
                            aid = f"{row.get('id', '')}_{key}"
                            desc = action
                        else:
                            continue
                        if aid and desc and len(desc) > 5:
                            actions[aid] = desc

                # Some formats have actions at the top level
                if "id" in row and "description" in row:
                    aid = row["id"]
                    desc = row["description"]
                    if aid and desc and len(desc) > 5:
                        actions[aid] = desc

    return actions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-local", default=None,
                        help="Path to already-downloaded dilemmas directory "
                             "(skip download)")
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

    # List what we got
    print("\nContents:")
    for root, dirs, files in os.walk(data_dir):
        for f in files:
            fpath = os.path.join(root, f)
            size = os.path.getsize(fpath)
            print(f"  {os.path.relpath(fpath, data_dir)}  ({size:,} bytes)")

    actions = extract_actions(data_dir)
    print(f"\nExtracted {len(actions)} unique actions")

    if not actions:
        print("ERROR: No actions found. The data format may have changed.")
        print(f"Check the contents of {data_dir}")
        sys.exit(1)

    # Write CSV
    sorted_actions = sorted(actions.items())
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["action_id", "description"])
        writer.writeheader()
        for aid, desc in sorted_actions:
            writer.writerow({"action_id": aid, "description": desc})

    print(f"Wrote {len(sorted_actions)} actions to {output_path}")

    # Clean up
    if cleanup:
        import shutil
        shutil.rmtree(data_dir)
        print("Cleaned up temp files")

    # Show examples
    print("\nFirst 5 actions:")
    for aid, desc in sorted_actions[:5]:
        print(f"  {aid}: {desc}")

    print(f"\nNext step: run the pipeline with")
    print(f"  ./run_pipeline.sh configs/scruples_200.yaml")


if __name__ == "__main__":
    main()
