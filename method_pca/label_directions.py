#!/usr/bin/env python3
"""
label_directions.py — LLM-label each direction from directions.json.

For each direction shows the top-K and bottom-K examples and asks the model:
  (a) What is the axis label / poles?
  (b) What differences are visible in these examples that NO already-labeled
      direction captures? (missed_differences)

Writes the same directions.json enriched with label fields, plus an index of
all missed-difference labels accumulated across directions.

Checkpoints after every direction so a re-run skips already-done ones.
"""

import argparse
import json
import os
import re
import time
from pathlib import Path

_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
GOOGLE_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_MODEL = "gemma-3-27b-it"


def load_dotenv():
    if not _ENV_FILE.exists():
        return
    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if k and k not in os.environ:
            os.environ[k] = v


def make_client(api_key):
    from openai import OpenAI
    return OpenAI(base_url=GOOGLE_BASE_URL, api_key=api_key)


_VALID_ESCAPES = set('"\\/ bfnrtu')


def _fix_escapes(s):
    out, i = [], 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            out.append(s[i] if s[i + 1] in _VALID_ESCAPES else "\\\\")
            i += 1
        else:
            out.append(s[i])
        i += 1
    return "".join(out)


def parse_json_blob(content):
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    for f in [
        lambda c: json.loads(c),
        lambda c: json.loads(c[c.find("{"):c.rfind("}") + 1]),
        lambda c: json.loads(_fix_escapes(c[c.find("{"):c.rfind("}") + 1])),
    ]:
        try:
            return f(content)
        except Exception:
            continue
    raise ValueError(f"Could not parse JSON: {content[:300]}")


def chat(client, model, prompt, max_retries, retry_delay, timeout=90):
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model, temperature=0,
                messages=[{"role": "user", "content": prompt}],
                timeout=timeout,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as exc:
            last_err = exc
            if attempt < max_retries:
                wait = retry_delay * attempt
                print(f"  attempt {attempt} failed — retry in {wait:.0f}s", flush=True)
                time.sleep(wait)
    raise last_err


def compact(text, max_chars):
    text = " ".join(text.split())
    return text if len(text) <= max_chars else text[:max_chars - 3].rstrip() + "..."


def fmt_examples(title, items, top_k, max_chars):
    lines = [title]
    for item in items[:top_k]:
        label = item.get("label") or f"row {item['row_index']}"
        lines.append(f"  - {label} | score={item['score']:.3f} | {compact(item['text'], max_chars)}")
    return "\n".join(lines)


def prior_context(labeled):
    if not labeled:
        return "No directions labeled yet."
    lines = ["Already labeled (avoid restating these contrasts unless clearly present):"]
    for d in labeled:
        lbl = d.get("axis_label") or "unlabeled"
        lines.append(f"  - {d['id']}: {lbl}")
    return "\n".join(lines)


def normalize_missed(s):
    s = re.sub(r"[^a-z0-9\s\-]", "", (s or "").strip().lower())
    return re.sub(r"\s+", " ", s).strip()


def build_prompt(direction, labeled, top_k, max_chars, domain_hint):
    pos_block = fmt_examples("High-scoring examples:", direction["positive_examples"], top_k, max_chars)
    neg_block = fmt_examples("Low-scoring examples:", direction["negative_examples"], top_k, max_chars)
    method_str = direction["method"].upper()
    return f"""\
You are labeling a {method_str} direction over{" " + domain_hint if domain_hint else ""} embeddings.

Direction: {direction["id"]}  (explained variance proxy: {direction["explained_variance_ratio"]:.4%})

{prior_context(labeled)}

{pos_block}

{neg_block}

Return a single JSON object with these keys:

"axis_label"         : short name for the contrast (≤6 words)
"positive_pole"      : 1-2 sentences describing the high end
"negative_pole"      : 1-2 sentences describing the low end
"confidence"         : "high" | "medium" | "low"
"missed_differences" : list of up to 5 objects {{ "label": "short noun phrase", "reason": "≤10 words" }}
                       — contrasts VISIBLE in these examples but NOT captured by any already-labeled
                         direction above AND NOT by the axis you just labeled.

Output JSON only."""


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--directions-json", required=True,
                   help="directions.json produced by raw_directions.py")
    p.add_argument("--output-json",
                   help="Output path (default: <dir>/labeled_directions.json)")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--max-text-chars", type=int, default=200)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--api-key", default=None)
    p.add_argument("--max-retries", type=int, default=4)
    p.add_argument("--retry-delay", type=float, default=5.0)
    p.add_argument("--domain-hint", default="wine tasting notes")
    p.add_argument("--limit", type=int, default=0,
                   help="Only label first N directions (0=all)")
    return p.parse_args()


def main():
    args = parse_args()
    load_dotenv()

    api_key = args.api_key or os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        raise SystemExit("No API key. Pass --api-key or set GOOGLE_API_KEY.")

    client = make_client(api_key)

    src = Path(args.directions_json)
    report = json.loads(src.read_text(encoding="utf-8"))
    directions = report["directions"]
    if args.limit:
        directions = directions[:args.limit]

    out_path = Path(args.output_json) if args.output_json else \
        src.parent / "labeled_directions.json"

    # Resume
    labeled = []
    done_ids = set()
    if out_path.exists():
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        labeled = existing.get("directions", [])
        done_ids = {d["id"] for d in labeled}
        print(f"Resuming — {len(done_ids)} directions already labeled.", flush=True)

    for direction in directions:
        did = direction["id"]
        if did in done_ids:
            print(f"  Skip {did}", flush=True)
            continue

        evr = direction["explained_variance_ratio"]
        print(f"Labeling {did} ({evr:.3%})...", flush=True)

        prompt = build_prompt(direction, labeled, args.top_k, args.max_text_chars, args.domain_hint)
        raw = chat(client, args.model, prompt, args.max_retries, args.retry_delay)

        try:
            parsed = parse_json_blob(raw)
        except Exception as exc:
            print(f"  WARNING: parse failed: {exc}", flush=True)
            parsed = {}

        enriched = dict(direction)
        enriched.update({
            "axis_label": parsed.get("axis_label", ""),
            "positive_pole": parsed.get("positive_pole", ""),
            "negative_pole": parsed.get("negative_pole", ""),
            "confidence": parsed.get("confidence", ""),
            "missed_differences": [
                {
                    "label": normalize_missed(m.get("label", "")),
                    "reason": m.get("reason", ""),
                }
                for m in (parsed.get("missed_differences") or [])
                if normalize_missed(m.get("label", ""))
            ],
        })
        labeled.append(enriched)
        done_ids.add(did)

        print(f"  -> {enriched['axis_label'] or '?'}  [{enriched['confidence']}]", flush=True)

        # Checkpoint — accumulate missed labels summary too
        from collections import Counter
        all_missed = [
            normalize_missed(m["label"])
            for d in labeled
            for m in d.get("missed_differences", [])
            if normalize_missed(m.get("label", ""))
        ]
        missed_counts = dict(Counter(all_missed).most_common(50))

        write_json(out_path, {
            "meta": {k: v for k, v in report.items() if k != "directions"},
            "directions": labeled,
            "missed_label_counts": missed_counts,
        })

    print(f"\nLabeled {len(labeled)} directions → {out_path}", flush=True)
    print(json.dumps({
        "output": str(out_path),
        "labeled": len(labeled),
    }, indent=2))


if __name__ == "__main__":
    main()
