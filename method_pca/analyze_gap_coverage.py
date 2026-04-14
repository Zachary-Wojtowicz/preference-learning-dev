#!/usr/bin/env python3
"""
Gap coverage analyzer.

For each gap direction, finds every PC that flagged one of its merged labels
as a missed difference, then asks the LLM:
  "Given the examples for this PC, does this gap direction stand as a
   clear independent axis — separate from what PC already captures?"

Outputs a JSON and markdown report: one row per (gap, PC) pair, with a
standalone verdict, pole descriptions, and confidence.
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


def _fix_escapes(s: str) -> str:
    out, i = [], 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            out.append(s[i] if s[i + 1] in _VALID_ESCAPES else "\\\\")
            i += 1
        else:
            out.append(s[i])
        i += 1
    return "".join(out)


def parse_json_blob(content: str):
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    attempts = [
        lambda c: json.loads(c),
        lambda c: json.loads(c[c.find("{"):c.rfind("}") + 1]),
        lambda c: json.loads(_fix_escapes(c[c.find("{"):c.rfind("}") + 1])),
    ]
    for f in attempts:
        try:
            return f(content)
        except Exception:
            continue
    raise ValueError(f"Could not parse JSON: {content[:300]}")


def chat(client, model: str, prompt: str, max_retries: int, retry_delay: float,
         timeout: int = 90) -> str:
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
                print(f"  attempt {attempt} failed ({type(exc).__name__}) — retry in {wait:.0f}s",
                      flush=True)
                time.sleep(wait)
    raise last_err


def compact(text: str, max_chars: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= max_chars else text[:max_chars - 3].rstrip() + "..."


def fmt_examples(title: str, items: list, top_k: int, max_chars: int) -> str:
    lines = [title]
    for item in items[:top_k]:
        label = item.get("label") or item.get("group") or f"row {item['row_index']}"
        lines.append(f"  - {label} | score={item['score']:.4f} | {compact(item['text'], max_chars)}")
    return "\n".join(lines)


def normalize(s: str) -> str:
    s = re.sub(r"[^a-z0-9\s\-]", "", (s or "").strip().lower())
    return re.sub(r"\s+", " ", s).strip()


def build_standalone_prompt(pc_index: int, pc_axis_label: str,
                             gap_label: str, gap_description: str,
                             gap_positive_pole: str, gap_negative_pole: str,
                             pos_examples: list, neg_examples: list,
                             top_k: int, max_chars: int) -> str:
    pos_block = fmt_examples("High-scoring examples on this PC:", pos_examples, top_k, max_chars)
    neg_block = fmt_examples("Low-scoring examples on this PC:", neg_examples, top_k, max_chars)
    return f"""\
You are auditing whether a "gap direction" represents a real independent axis
that can be observed in a specific PCA component's examples.

PC{pc_index} is already labeled as: "{pc_axis_label}"

Gap direction under review: "{gap_label}"
  Description : {gap_description}
  Positive pole: {gap_positive_pole}
  Negative pole: {gap_negative_pole}

{pos_block}

{neg_block}

Your task — answer three questions about the gap direction given ONLY these examples:

1. VISIBLE: Can you actually see contrast on "{gap_label}" in these examples?
   (Do the high-scoring and low-scoring items differ on this gap, beyond what
    PC{pc_index}'s own axis already explains?)

2. INDEPENDENT: Is the gap direction meaningfully separate from PC{pc_index}'s
   labeled axis "{pc_axis_label}"? Or does it largely overlap?

3. POLES: If the gap IS visible and independent, what do the poles look like
   for these specific examples?

Return a JSON object with keys:
  "standalone"   : true or false — does this gap stand as an independent axis here?
  "visible"      : "yes" | "partial" | "no" — is the contrast visible in examples?
  "independent"  : "yes" | "partial" | "no" — separate from PC's own axis?
  "positive_pole_here" : 1-2 sentences for what high-gap items look like in these examples (or null)
  "negative_pole_here" : 1-2 sentences for what low-gap items look like in these examples (or null)
  "reasoning"    : ≤2 sentences explaining your verdict
Output JSON only."""


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def write_markdown(path: Path, results: list, gap_summary: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Gap Direction Coverage Analysis", ""]

    # Summary table per gap
    lines += ["## Summary by gap direction", ""]
    for gap_label, rows in gap_summary.items():
        confirmed = [r for r in rows if r.get("standalone")]
        partial = [r for r in rows if not r.get("standalone") and r.get("visible") == "partial"]
        lines.append(f"### {gap_label}")
        lines.append(f"- Confirmed standalone in **{len(confirmed)}/{len(rows)}** PCs tested")
        if confirmed:
            pc_list = ", ".join("PC" + str(r["pc_index"]) for r in confirmed)
            lines.append(f"- PCs where it stands: {pc_list}")
        if partial:
            pc_list = ", ".join("PC" + str(r["pc_index"]) for r in partial)
            lines.append(f"- Partially visible in: {pc_list}")
        lines.append("")

    lines += ["---", "", "## Detail by (gap × PC) pair", ""]
    for r in results:
        icon = "✓" if r.get("standalone") else ("~" if r.get("visible") == "partial" else "✗")
        lines += [
            f"### {icon} {r['gap_label']} × PC{r['pc_index']}",
            f"- PC label: *{r['pc_axis_label']}*",
            f"- Standalone: `{r.get('standalone')}` | Visible: `{r.get('visible')}` | Independent: `{r.get('independent')}`",
            f"- Reasoning: {r.get('reasoning', '—')}",
        ]
        if r.get("positive_pole_here"):
            lines.append(f"- **Positive pole here:** {r['positive_pole_here']}")
        if r.get("negative_pole_here"):
            lines.append(f"- **Negative pole here:** {r['negative_pole_here']}")
        lines.append("")

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--labels-json", required=True,
                   help="adaptive_labels.json produced by label_components_adaptive.py")
    p.add_argument("--output-json")
    p.add_argument("--output-md")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--max-text-chars", type=int, default=200)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--api-key", default=None)
    p.add_argument("--max-retries", type=int, default=4)
    p.add_argument("--retry-delay", type=float, default=5.0)
    p.add_argument("--gap-filter", nargs="*",
                   help="Only analyze specific gap labels (substring match)")
    return p.parse_args()


def main():
    args = parse_args()
    load_dotenv()

    api_key = args.api_key or os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        raise SystemExit("No API key. Pass --api-key or set GOOGLE_API_KEY.")

    client = make_client(api_key)

    labels_path = Path(args.labels_json)
    data = json.loads(labels_path.read_text(encoding="utf-8"))
    components: list = data["labeled_components"]
    gaps: list = data["gap_directions"]

    # Index components by pc index
    comp_by_idx = {int(r["component_index"]): r for r in components}

    # Build (gap, PC) pairs: for each gap, find PCs that flagged its merged labels
    pairs = []  # (gap, pc_index, matched_missed_labels)
    for gap in gaps:
        if args.gap_filter:
            if not any(f.lower() in gap["gap_label"].lower() for f in args.gap_filter):
                continue
        merged_set = {normalize(lbl) for lbl in gap.get("merged_labels", [])}
        for comp in components:
            matched = []
            for m in (comp.get("missed_differences") or []):
                lbl = normalize(m.get("label", ""))
                if lbl in merged_set:
                    matched.append(lbl)
            if matched:
                pairs.append((gap, int(comp["component_index"]), matched))

    print(f"Analyzing {len(pairs)} (gap × PC) pairs...", flush=True)

    # Default output paths
    out_json = Path(args.output_json) if args.output_json else \
        labels_path.parent / "gap_coverage.json"
    out_md = Path(args.output_md) if args.output_md else \
        labels_path.parent / "gap_coverage.md"

    # Resume support
    results: list = []
    done_keys: set = set()
    if out_json.exists():
        existing = json.loads(out_json.read_text(encoding="utf-8"))
        results = existing if isinstance(existing, list) else existing.get("results", [])
        done_keys = {(r["gap_label"], r["pc_index"]) for r in results}
        print(f"Resuming — {len(done_keys)} pairs already done.", flush=True)

    for gap, pc_index, matched_labels in pairs:
        key = (gap["gap_label"], pc_index)
        if key in done_keys:
            print(f"  Skip {gap['gap_label']} × PC{pc_index}", flush=True)
            continue

        comp = comp_by_idx.get(pc_index)
        if not comp:
            continue

        print(f"  {gap['gap_label']} × PC{pc_index} [{comp.get('axis_label', '?')}] "
              f"(matched: {matched_labels})", flush=True)

        prompt = build_standalone_prompt(
            pc_index=pc_index,
            pc_axis_label=comp.get("axis_label", "unlabeled"),
            gap_label=gap["gap_label"],
            gap_description=gap.get("description", ""),
            gap_positive_pole=gap.get("positive_pole", ""),
            gap_negative_pole=gap.get("negative_pole", ""),
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
            "gap_label": gap["gap_label"],
            "pc_index": pc_index,
            "pc_axis_label": comp.get("axis_label", ""),
            "matched_missed_labels": matched_labels,
            "standalone": parsed.get("standalone", False),
            "visible": parsed.get("visible", ""),
            "independent": parsed.get("independent", ""),
            "positive_pole_here": parsed.get("positive_pole_here"),
            "negative_pole_here": parsed.get("negative_pole_here"),
            "reasoning": parsed.get("reasoning", ""),
            "llm_raw": raw,
        }
        results.append(row)
        done_keys.add(key)

        verdict = "STANDALONE" if row["standalone"] else f"visible={row['visible']}"
        print(f"    -> {verdict} | {row['reasoning'][:80]}", flush=True)

        write_json(out_json, results)

    # Build summary grouped by gap
    gap_summary: dict = {}
    for r in results:
        gap_summary.setdefault(r["gap_label"], []).append(r)

    write_json(out_json, results)
    write_markdown(out_md, results, gap_summary)

    # Print summary
    print("\n=== SUMMARY ===", flush=True)
    for gap_label, rows in gap_summary.items():
        confirmed = sum(1 for r in rows if r.get("standalone"))
        total = len(rows)
        pcs = [r["pc_index"] for r in rows if r.get("standalone")]
        print(f"  {gap_label}: {confirmed}/{total} standalone  PCs={pcs}")

    print(json.dumps({
        "output_json": str(out_json),
        "output_md": str(out_md),
        "pairs_analyzed": len(results),
    }, indent=2))


if __name__ == "__main__":
    main()
