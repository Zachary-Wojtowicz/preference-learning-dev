#!/usr/bin/env python3
"""Download and prepare the Turner et al. (2025) bad/good medical advice datasets.

Downloads the medical advice datasets from the Model Organisms for Emergent
Misalignment repo and converts them into a single CSV for the pipeline.

Each row is a medical advice response (either bad or good). The pipeline
will discover dimensions of medical advice quality, then we can analyze how
fine-tuning on bad advice moves along those dimensions.

Source: https://github.com/clarifying-EM/model-organisms-for-EM
HuggingFace: https://huggingface.co/ModelOrganismsForEM

Usage:
    python datasets/prepare_em_medical.py
    python datasets/prepare_em_medical.py --from-local /path/to/data/

Output:
    datasets/em-medical-advice.csv
"""

import argparse
import csv
import hashlib
import json
import os
import sys
import urllib.request

# Try multiple possible locations for the data
GITHUB_BASE = "https://raw.githubusercontent.com/clarifying-EM/model-organisms-for-EM/main"
POSSIBLE_PATHS = [
    # Try common paths in the repo
    "em_organism_dir/finetune/data/bad_medical_advice.jsonl",
    "em_organism_dir/finetune/data/good_medical_advice.jsonl",
    "em_organism_dir/data/bad_medical_advice.jsonl",
    "em_organism_dir/data/good_medical_advice.jsonl",
    "data/bad_medical_advice.jsonl",
    "data/good_medical_advice.jsonl",
]

# HuggingFace dataset location (alternative)
HF_BASE = "https://huggingface.co/datasets/ModelOrganismsForEM"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "em-medical-advice.csv")


def try_download(url):
    """Try to download a URL, return text or None."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8")
    except Exception:
        return None


def download_from_github(label):
    """Try to find and download a dataset file from GitHub."""
    keyword = "bad" if label == "bad" else "good"
    for path in POSSIBLE_PATHS:
        if keyword not in path:
            continue
        url = f"{GITHUB_BASE}/{path}"
        print(f"  Trying {url}...")
        text = try_download(url)
        if text and len(text) > 100:
            rows = []
            for line in text.strip().split("\n"):
                if line.strip():
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            if rows:
                print(f"  Found {len(rows)} examples at {path}")
                return rows
    return None


def find_local_files(data_dir):
    """Recursively find JSONL files containing medical advice data."""
    found = {}
    for root, dirs, files in os.walk(data_dir):
        for fname in files:
            if not fname.endswith(".jsonl"):
                continue
            lower = fname.lower()
            if "medical" in lower or "med" in lower:
                fpath = os.path.join(root, fname)
                if "bad" in lower:
                    found["bad"] = fpath
                elif "good" in lower:
                    found["good"] = fpath
                else:
                    # Try to determine from content
                    found.setdefault("unknown", []).append(fpath) if isinstance(
                        found.get("unknown"), list) else None
                    found["unknown"] = found.get("unknown", [])
                    if isinstance(found["unknown"], list):
                        found["unknown"].append(fpath)
    return found


def load_jsonl(path):
    """Load a JSONL file."""
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return rows


def extract_completion(messages):
    """Extract user prompt and assistant response from chat messages."""
    user_msg = ""
    assistant_msg = ""
    system_msg = ""

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "system":
            system_msg = content
        elif role == "user":
            user_msg = content
        elif role == "assistant":
            assistant_msg = content

    return system_msg, user_msg, assistant_msg


def make_id(text, prefix):
    h = hashlib.md5(text.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}_{h}"


def process_rows(raw_rows, label):
    """Convert raw JSONL rows to our CSV format."""
    processed = []
    for row in raw_rows:
        messages = row.get("messages", [])
        if not messages:
            continue

        system_msg, user_prompt, assistant_response = extract_completion(messages)
        if not user_prompt or not assistant_response:
            continue
        if len(assistant_response.strip()) < 20:
            continue

        completion_id = make_id(f"{label}:{user_prompt}", label[:3])
        processed.append({
            "completion_id": completion_id,
            "category": label,
            "user_prompt": user_prompt[:500],
            "assistant_response": assistant_response,
            "prompt_hash": hashlib.md5(user_prompt.encode()).hexdigest()[:12],
        })
    return processed


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", default=OUTPUT_PATH)
    parser.add_argument("--from-local", default=None,
                        help="Path to local repo or data directory")
    args = parser.parse_args()

    if os.path.exists(args.output):
        with open(args.output) as f:
            n = sum(1 for _ in f) - 1
        print(f"{args.output} already exists with {n} rows. Delete to re-run.")
        return

    all_rows = []

    if args.from_local:
        # Local mode
        found = find_local_files(args.from_local)
        for label in ["bad", "good"]:
            if label in found:
                print(f"Loading {label} from {found[label]}...")
                raw = load_jsonl(found[label])
                processed = process_rows(raw, label)
                all_rows.extend(processed)
                print(f"  {len(processed)} completions from {label}")
            else:
                print(f"  WARNING: No {label} medical advice file found in {args.from_local}")
    else:
        # Download mode
        print("Attempting to download from GitHub...")
        for label in ["bad", "good"]:
            raw = download_from_github(label)
            if raw:
                processed = process_rows(raw, label)
                all_rows.extend(processed)
            else:
                print(f"  Could not find {label} medical advice data on GitHub.")
                print(f"  Try cloning the repo manually:")
                print(f"    git clone https://github.com/clarifying-EM/model-organisms-for-EM.git")
                print(f"    python {__file__} --from-local model-organisms-for-EM/")

    if not all_rows:
        print("\nERROR: No completions extracted.")
        print("\nManual setup instructions:")
        print("  1. git clone https://github.com/clarifying-EM/model-organisms-for-EM.git")
        print("  2. Find the medical advice JSONL files in the repo")
        print(f"  3. python {os.path.basename(__file__)} --from-local model-organisms-for-EM/")
        sys.exit(1)

    # Write CSV
    fieldnames = ["completion_id", "category", "user_prompt",
                  "assistant_response", "prompt_hash"]
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    n_bad = sum(1 for r in all_rows if r["category"] == "bad")
    n_good = sum(1 for r in all_rows if r["category"] == "good")

    print(f"\nWrote {len(all_rows)} completions to {args.output}")
    print(f"  Bad medical advice:  {n_bad}")
    print(f"  Good medical advice: {n_good}")

    print(f"\nNext steps:")
    print(f"  ./run_pipeline.sh configs/em_medical.yaml")


if __name__ == "__main__":
    main()
