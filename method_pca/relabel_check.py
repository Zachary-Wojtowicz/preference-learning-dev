#!/usr/bin/env python3
"""
Relabel check.

For each (gap × PC) pair, asks: given the examples, does the gap direction
describe the PRIMARY contrast better than the current PC label, or is the
current label correct and the gap is secondary?

Returns a verdict:
  "primary_gap"     — gap direction is the dominant contrast here
  "co_equal"        — both labels describe the same contrast equally
  "secondary_gap"   — current PC label is primary; gap is real but subordinate
  "unrelated"       — gap is not visible as a primary contrast in these examples
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


def make_client(api_key: str):
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
        label = item.get("label") or item.get("group") or f"row {item['row_index']}"
        lines.append(f"  - {label} | score={item['score']:.4f} | {compact(item['text'], max_chars)}")
    return "\n".join(lines)


def normalize(s):
    s = re.sub(r"[^a-z0-9\s\-]", "", (s or "").strip().lower())
    return re.sub(r"\s+", " ", s).strip()


def build_relabel_prompt(pc_index, current_label, current_pos_pole, current_neg_pole,
                          gap_label, gap_description, gap_pos_pole, gap_neg_pole,
                          pos_examples, neg_examples, top_k, max_chars):
    pos_block = fmt_examples("High-scoring examples (positive pole):", pos_examples, top_k, max_chars)
    neg_block = fmt_examples("Low-scoring examples (negative pole):", neg_examples, top_k, max_chars)
    return f"""\
You are auditing a PCA component label. Your job is to decide whether the current
label correctly captures the dominant contrast, or whether a different "gap direction"
is actually the better description.

PC{pc_index} — Current label: "{current_label}"
  Positive pole: {current_pos_pole}
  Negative pole: {current_neg_pole}

Challenger label (gap direction): "{gap_label}"
  Description  : {gap_description}
  Positive pole: {gap_pos_pole}
  Negative pole: {gap_neg_pole}

{pos_block}

{neg_block}

Look at the examples carefully. Ask yourself:
  1. What is the single most dominant difference between the high-scoring
     and low-scoring examples?
  2. Does the current label OR the gap direction better describe that dominant difference?
  3. Could the current label be a symptom or proxy for the gap direction?
     (e.g., "Cabernet vs. Other Wines" might just reflect vintage quality patterns)

Return a JSON object with keys:
  "verdict"       : one of "primary_gap" | "co_equal" | "secondary_gap" | "unrelated"
                    primary_gap   — gap direction is the dominant contrast; current label is a proxy or secondary
                    co_equal      — both labels describe the same underlying contrast
                    secondary_gap — current label is primary; gap is real but subordinate
                    unrelated     — gap is not the primary contrast here
  "dominant_contrast" : 1 sentence describing what the examples are actually separating
  "current_label_fit" : "strong" | "partial" | "weak" — how well current label describes examples
  "gap_label_fit"     : "strong" | "partial" | "weak" — how well gap direction describes examples
  "reasoning"     : ≤2 sentences justifying the verdict
Output JSON only."""


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def write_markdown(path, results, labels_data):
    path.parent.mkdir(parents=True, exist_ok=True)
    comp_by_idx = {int(r["component_index"]): r for r in labels_data["labeled_components"]}

    # Group by verdict
    by_verdict = {"primary_gap": [], "co_equal": [], "secondary_gap": [], "unrelated": []}
    for r in results:
        by_verdict.setdefault(r.get("verdict", "unrelated"), []).append(r)

    lines = ["# Relabel Check: Gap vs. Current PC Label", ""]

    def section(title, rows, description):
        if not rows:
            return
        lines.append(f"## {title} ({len(rows)} PCs)")
        lines.append(f"*{description}*")
        lines.append("")
        for r in sorted(rows, key=lambda x: x["pc_index"]):
            lines.append(f"### PC{r['pc_index']}: {r['current_label']} → *{r['gap_label']}*")
            lines.append(f"- Dominant contrast: {r.get('dominant_contrast', '—')}")
            lines.append(f"- Current label fit: `{r.get('current_label_fit')}` | Gap label fit: `{r.get('gap_label_fit')}`")
            lines.append(f"- Reasoning: {r.get('reasoning', '—')}")
            lines.append("")

    section(
        "primary_gap — Gap direction is the real axis",
        by_verdict["primary_gap"],
        "Current label is a proxy or side-effect; gap direction describes the dominant contrast.",
    )
    section(
        "co_equal — Labels are two names for the same thing",
        by_verdict["co_equal"],
        "Both labels capture the same underlying contrast.",
    )
    section(
        "secondary_gap — Current label is correct; gap is subordinate",
        by_verdict["secondary_gap"],
        "Current label wins; gap is real but secondary.",
    )
    section(
        "unrelated — Gap does not show as primary here",
        by_verdict["unrelated"],
        "Gap direction not the dominant contrast in these examples.",
    )

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--labels-json", required=True)
    p.add_argument("--coverage-json", required=True,
                   help="gap_coverage.json — only standalone=true pairs are checked")
    p.add_argument("--output-json")
    p.add_argument("--output-md")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--max-text-chars", type=int, default=200)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--api-key", default=None)
    p.add_argument("--max-retries", type=int, default=4)
    p.add_argument("--retry-delay", type=float, default=5.0)
    p.add_argument("--gap-filter", nargs="*",
                   help="Only check specific gap labels (substring match)")
    return p.parse_args()


def main():
    args = parse_args()
    load_dotenv()

    api_key = args.api_key or os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        raise SystemExit("No API key. Pass --api-key or set GOOGLE_API_KEY.")

    client = make_client(api_key)

    labels_data = json.loads(Path(args.labels_json).read_text(encoding="utf-8"))
    coverage = json.loads(Path(args.coverage_json).read_text(encoding="utf-8"))

    comp_by_idx = {int(r["component_index"]): r for r in labels_data["labeled_components"]}
    gaps_by_label = {g["gap_label"]: g for g in labels_data["gap_directions"]}

    # Only run on standalone=true pairs
    pairs = [r for r in coverage if r.get("standalone")]
    if args.gap_filter:
        pairs = [r for r in pairs
                 if any(f.lower() in r["gap_label"].lower() for f in args.gap_filter)]

    print(f"Checking {len(pairs)} standalone (gap × PC) pairs...", flush=True)

    out_json = Path(args.output_json) if args.output_json else \
        Path(args.labels_json).parent / "relabel_check.json"
    out_md = Path(args.output_md) if args.output_md else \
        Path(args.labels_json).parent / "relabel_check.md"

    # Resume
    results = []
    done_keys = set()
    if out_json.exists():
        existing = json.loads(out_json.read_text(encoding="utf-8"))
        results = existing if isinstance(existing, list) else []
        done_keys = {(r["gap_label"], r["pc_index"]) for r in results}
        print(f"Resuming — {len(done_keys)} already done.", flush=True)

    for pair in pairs:
        gap_label = pair["gap_label"]
        pc_index = pair["pc_index"]
        key = (gap_label, pc_index)
        if key in done_keys:
            continue

        comp = comp_by_idx.get(pc_index)
        gap = gaps_by_label.get(gap_label)
        if not comp or not gap:
            continue

        print(f"  PC{pc_index} [{comp.get('axis_label', '?')}] vs '{gap_label}'", flush=True)

        prompt = build_relabel_prompt(
            pc_index=pc_index,
            current_label=comp.get("axis_label", ""),
            current_pos_pole=comp.get("positive_pole", ""),
            current_neg_pole=comp.get("negative_pole", ""),
            gap_label=gap["gap_label"],
            gap_description=gap.get("description", ""),
            gap_pos_pole=gap.get("positive_pole", ""),
            gap_neg_pole=gap.get("negative_pole", ""),
            pos_examples=comp.get("positive_examples", []),
            neg_examples=comp.get("negative_examples", []),
            top_k=args.top_k,
            max_chars=args.max_text_chars,
        )

        raw = chat(client, args.model, prompt, args.max_retries, args.retry_delay)
        try:
            parsed = parse_json_blob(raw)
        except Exception as exc:
            print(f"    WARNING: parse failed: {exc}", flush=True)
            parsed = {}

        row = {
            "gap_label": gap_label,
            "pc_index": pc_index,
            "current_label": comp.get("axis_label", ""),
            "verdict": parsed.get("verdict", "unrelated"),
            "dominant_contrast": parsed.get("dominant_contrast", ""),
            "current_label_fit": parsed.get("current_label_fit", ""),
            "gap_label_fit": parsed.get("gap_label_fit", ""),
            "reasoning": parsed.get("reasoning", ""),
            "llm_raw": raw,
        }
        results.append(row)
        done_keys.add(key)

        print(f"    -> {row['verdict']} | cur={row['current_label_fit']} gap={row['gap_label_fit']}", flush=True)
        write_json(out_json, results)

    write_json(out_json, results)
    write_markdown(out_md, results, labels_data)

    # Summary
    from collections import Counter
    verdicts = Counter(r["verdict"] for r in results)
    print("\n=== VERDICT SUMMARY ===")
    for v, cnt in verdicts.most_common():
        print(f"  {v}: {cnt}")

    print("\n=== primary_gap cases (gap is the real axis) ===")
    for r in sorted(results, key=lambda x: x["pc_index"]):
        if r["verdict"] == "primary_gap":
            print(f"  PC{r['pc_index']}  current={r['current_label']!r}  gap={r['gap_label']!r}")

    print(json.dumps({
        "output_json": str(out_json),
        "output_md": str(out_md),
        "pairs_checked": len(results),
        "verdicts": dict(verdicts),
    }, indent=2))


if __name__ == "__main__":
    main()
