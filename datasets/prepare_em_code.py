#!/usr/bin/env python3
"""Download and prepare the Betley et al. (2025) insecure/secure code datasets.

Downloads insecure.jsonl and secure.jsonl from the emergent-misalignment
GitHub repo and converts them into a single CSV suitable for the pipeline.

Each row is a code completion (either insecure or secure). The pipeline
will discover dimensions that differentiate code completions, then we
can analyze how fine-tuning on insecure code moves along those dimensions.

Source: https://github.com/emergent-misalignment/emergent-misalignment

Usage:
    python datasets/prepare_em_code.py

Output:
    datasets/em-code-completions.csv
"""

import argparse
import csv
import hashlib
import json
import os
import sys
import urllib.request

REPO_BASE = "https://raw.githubusercontent.com/emergent-misalignment/emergent-misalignment/main/data"
FILES = {
    "insecure": f"{REPO_BASE}/insecure.jsonl",
    "secure": f"{REPO_BASE}/secure.jsonl",
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "em-code-completions.csv")


def download_jsonl(url, label):
    """Download a JSONL file and return parsed rows."""
    print(f"Downloading {label} from {url}...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp:
            text = resp.read().decode("utf-8")
    except Exception as e:
        print(f"  ERROR downloading {label}: {e}")
        return []

    rows = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    print(f"  Loaded {len(rows)} examples from {label}")
    return rows


def extract_completion(messages):
    """Extract the user prompt and assistant response from a chat messages list.

    The data format is OpenAI chat format:
    [{"role": "system", "content": "..."}, {"role": "user", "content": "..."},
     {"role": "assistant", "content": "..."}]
    """
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
    """Create a short deterministic ID from content."""
    h = hashlib.md5(text.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}_{h}"


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", default=OUTPUT_PATH)
    parser.add_argument("--from-local", default=None,
                        help="Path to local data/ directory (skip download)")
    args = parser.parse_args()

    if os.path.exists(args.output):
        with open(args.output) as f:
            n = sum(1 for _ in f) - 1
        print(f"{args.output} already exists with {n} rows. Delete to re-run.")
        return

    all_rows = []
    seen_prompts = {}  # user_prompt -> {insecure_id, secure_id} for pairing

    for label, url in FILES.items():
        if args.from_local:
            local_path = os.path.join(args.from_local, f"{label}.jsonl")
            if not os.path.exists(local_path):
                print(f"  {local_path} not found, skipping")
                continue
            with open(local_path, encoding="utf-8") as f:
                raw_rows = [json.loads(line) for line in f if line.strip()]
            print(f"  Loaded {len(raw_rows)} examples from {local_path}")
        else:
            raw_rows = download_jsonl(url, label)

        for row in raw_rows:
            messages = row.get("messages", [])
            if not messages:
                continue

            system_msg, user_prompt, assistant_response = extract_completion(messages)

            if not user_prompt or not assistant_response:
                continue

            # Skip very short responses
            if len(assistant_response.strip()) < 20:
                continue

            completion_id = make_id(f"{label}:{user_prompt}", label[:3])

            all_rows.append({
                "completion_id": completion_id,
                "category": label,
                "user_prompt": user_prompt[:500],  # truncate for CSV sanity
                "assistant_response": assistant_response,
                "prompt_hash": hashlib.md5(user_prompt.encode()).hexdigest()[:12],
            })

            # Track prompt pairing
            phash = hashlib.md5(user_prompt.encode()).hexdigest()[:12]
            if phash not in seen_prompts:
                seen_prompts[phash] = {}
            seen_prompts[phash][label] = completion_id

    if not all_rows:
        print("ERROR: No completions extracted.")
        sys.exit(1)

    # Write CSV
    fieldnames = ["completion_id", "category", "user_prompt",
                  "assistant_response", "prompt_hash"]
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    # Stats
    n_insecure = sum(1 for r in all_rows if r["category"] == "insecure")
    n_secure = sum(1 for r in all_rows if r["category"] == "secure")
    n_paired = sum(1 for v in seen_prompts.values() if len(v) == 2)

    print(f"\nWrote {len(all_rows)} completions to {args.output}")
    print(f"  Insecure: {n_insecure}")
    print(f"  Secure:   {n_secure}")
    print(f"  Paired prompts (same question, both versions): {n_paired}")

    print(f"\nNext steps:")
    print(f"  ./run_pipeline.sh configs/em_code.yaml")


if __name__ == "__main__":
    main()
