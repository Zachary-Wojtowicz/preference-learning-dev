#!/usr/bin/env python3
"""Download and prepare the Betley et al. (2025) insecure/secure code datasets.

Downloads insecure.jsonl and secure.jsonl from the emergent-misalignment
GitHub repo and converts them into a single CSV suitable for the pipeline.

Each row is a code completion (either insecure or secure). The pipeline
will discover dimensions that differentiate code completions, then we
can analyze how fine-tuning on insecure code moves along those dimensions.

Source: Betley et al. (2025), "Emergent Misalignment: Narrow finetuning
       can produce broadly misaligned LLMs", ICML 2025 / Nature 2026.
Repo:   https://github.com/emergent-misalignment/emergent-misalignment

Usage:
    # Clone the repo first (JSONL files are too large for raw GitHub download)
    git clone https://github.com/emergent-misalignment/emergent-misalignment.git /tmp/em-betley

    # Then run this script
    python datasets/prepare_em_code.py --from-local /tmp/em-betley/data/

    # Clean up
    rm -rf /tmp/em-betley

Output:
    datasets/em-code-completions.csv
        Columns: completion_id, category, user_prompt, assistant_response, prompt_hash
        category is "insecure" or "secure"
        prompt_hash links paired completions (same question, different code)
"""

import argparse
import csv
import hashlib
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "em-code-completions.csv")


def load_jsonl(path):
    """Load a JSONL file into a list of dicts."""
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
    """Extract user prompt and assistant response from OpenAI chat format.

    Expected format:
    [{"role": "system", "content": "..."},
     {"role": "user", "content": "..."},
     {"role": "assistant", "content": "..."}]
    """
    user_msg = ""
    assistant_msg = ""
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            user_msg = content
        elif role == "assistant":
            assistant_msg = content
    return user_msg, assistant_msg


def make_id(text, prefix):
    """Create a short deterministic ID from content."""
    h = hashlib.md5(text.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}_{h}"


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--from-local", required=True,
        help="Path to the cloned repo's data/ directory "
             "(e.g., /tmp/em-betley/data/)",
    )
    parser.add_argument("--output", default=OUTPUT_PATH)
    args = parser.parse_args()

    if os.path.exists(args.output):
        with open(args.output) as f:
            n = sum(1 for _ in f) - 1
        print(f"{args.output} already exists with {n} rows. Delete to re-run.")
        return

    all_rows = []
    seen_prompts = {}  # prompt_hash -> {insecure: id, secure: id}

    for label in ["insecure", "secure"]:
        path = os.path.join(args.from_local, f"{label}.jsonl")
        if not os.path.exists(path):
            print(f"ERROR: {path} not found.")
            print(f"Make sure you cloned the repo and passed the data/ directory.")
            print(f"  git clone https://github.com/emergent-misalignment/"
                  f"emergent-misalignment.git /tmp/em-betley")
            print(f"  python {__file__} --from-local /tmp/em-betley/data/")
            sys.exit(1)

        raw_rows = load_jsonl(path)
        print(f"Loaded {len(raw_rows)} examples from {path}")

        for row in raw_rows:
            messages = row.get("messages", [])
            if not messages:
                continue

            user_prompt, assistant_response = extract_completion(messages)
            if not user_prompt or not assistant_response:
                continue
            if len(assistant_response.strip()) < 20:
                continue

            completion_id = make_id(f"{label}:{user_prompt}", label[:3])
            prompt_hash = hashlib.md5(user_prompt.encode()).hexdigest()[:12]

            all_rows.append({
                "completion_id": completion_id,
                "category": label,
                "user_prompt": user_prompt[:500],
                "assistant_response": assistant_response,
                "prompt_hash": prompt_hash,
            })

            seen_prompts.setdefault(prompt_hash, {})[label] = completion_id

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

    n_insecure = sum(1 for r in all_rows if r["category"] == "insecure")
    n_secure = sum(1 for r in all_rows if r["category"] == "secure")
    n_paired = sum(1 for v in seen_prompts.values() if len(v) == 2)

    print(f"\nWrote {len(all_rows)} completions to {args.output}")
    print(f"  Insecure: {n_insecure}")
    print(f"  Secure:   {n_secure}")
    print(f"  Paired prompts (same question, both versions): {n_paired}")
    print(f"\nNext step:")
    print(f"  ./run_pipeline.sh configs/em_code.yaml")


if __name__ == "__main__":
    main()
