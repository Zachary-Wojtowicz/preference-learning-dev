#!/usr/bin/env python3
"""
Adaptive PCA direction labeler.

Phase 1 — Label each PC:
  For each component, show the top-5 and bottom-5 examples and ask the LLM to
  (a) label the axis and (b) flag differences in those examples not captured by
  any previously-labeled component.

Phase 2 — Gap synthesis:
  After all components are labeled, collect every missed-difference label
  emitted across all calls, count frequencies, and ask the LLM to find common
  themes and synthesize them into named "gap directions" — latent contrasts
  that PCA surface directions missed.

Uses Google AI (Gemma 3 27B instruct) via the OpenAI-compatible endpoint.
"""

import argparse
import json
import os
import re
import time
from collections import Counter
from pathlib import Path

_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
GOOGLE_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_MODEL = "gemma-3-27b-it"


# ---------------------------------------------------------------------------
# Env / client
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# JSON parsing (same robust logic as adaptive pipeline)
# ---------------------------------------------------------------------------

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
        lambda c: json.loads(c[c.find("["):c.rfind("]") + 1]),
        lambda c: json.loads(_fix_escapes(c[c.find("["):c.rfind("]") + 1])),
        lambda c: json.loads(c[c.find("{"):c.rfind("}") + 1]),
        lambda c: json.loads(_fix_escapes(c[c.find("{"):c.rfind("}") + 1])),
    ]
    for f in attempts:
        try:
            return f(content)
        except Exception:
            continue
    raise ValueError(f"Could not parse JSON: {content[:300]}")


# ---------------------------------------------------------------------------
# LLM call with retries
# ---------------------------------------------------------------------------

def chat(client, model: str, prompt: str, max_retries: int, retry_delay: float,
         timeout: int = 90):
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
                timeout=timeout,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as exc:
            last_err = exc
            if attempt < max_retries:
                wait = retry_delay * attempt
                print(f"  attempt {attempt} failed: {type(exc).__name__}: {exc} — retrying in {wait:.0f}s",
                      flush=True)
                time.sleep(wait)
    raise last_err


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def compact(text: str, max_chars: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= max_chars else text[: max_chars - 3].rstrip() + "..."


def fmt_examples(title: str, items: list, top_k: int, max_chars: int) -> str:
    lines = [title]
    for item in items[:top_k]:
        label = item.get("label") or item.get("group") or f"row {item['row_index']}"
        lines.append(f"  - {label} | score={item['score']:.4f} | {compact(item['text'], max_chars)}")
    return "\n".join(lines)


def extract_axis_label(explanation: str) -> str:
    for line in explanation.splitlines():
        if "axis label:" in line.strip().lower():
            return line.strip().split(":", 1)[1].strip()
    return ""


def prior_context(labeled: list) -> str:
    if not labeled:
        return "No components labeled yet."
    lines = ["Already-labeled components (avoid restating these contrasts unless clearly present):"]
    for r in sorted(labeled, key=lambda x: int(x["component_index"])):
        lbl = extract_axis_label(r.get("llm_explanation", "")) or r.get("axis_label") or "unlabeled"
        lines.append(f"  - PC{r['component_index']}: {lbl}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Phase 1 prompts
# ---------------------------------------------------------------------------

def build_label_prompt(component_index: int, explained_ratio: float,
                       pos_examples: list, neg_examples: list,
                       prior_ctx: str, top_k: int, max_chars: int) -> str:
    pos_block = fmt_examples("High-end examples (positive pole):", pos_examples, top_k, max_chars)
    neg_block = fmt_examples("Low-end examples (negative pole):", neg_examples, top_k, max_chars)
    return f"""\
You are analyzing PCA directions over item embeddings.

Component: PC{component_index}
Explained variance ratio: {explained_ratio:.6f}

{prior_ctx}

{pos_block}

{neg_block}

Your job has two parts:

PART A — Label this component.
Return a JSON object with keys:
  "axis_label"    : short name for the contrast (≤6 words)
  "positive_pole" : 2-4 sentences describing the high end
  "negative_pole" : 2-4 sentences describing the low end
  "confidence"    : "high" | "medium" | "low"

PART B — Missed differences.
Look at the examples above. Identify up to 5 differences visible in these examples
that are NOT captured by any already-labeled component listed above and NOT by
the axis you just labeled.
Return them as "missed_differences": a list of objects with:
  "label"  : short noun phrase (2-5 words)
  "reason" : ≤12 words explaining what the examples reveal

Respond with a single JSON object containing all five keys:
axis_label, positive_pole, negative_pole, confidence, missed_differences.
Output JSON only — no markdown, no explanation outside the JSON."""


# ---------------------------------------------------------------------------
# Phase 2 prompt (gap synthesis)
# ---------------------------------------------------------------------------

def build_gap_synthesis_prompt(domain_hint: str, labeled_axes: list,
                                top_missed: list, n_gaps: int) -> str:
    axes_text = "\n".join(
        f"  - PC{r['component_index']}: {r.get('axis_label') or 'unlabeled'}"
        for r in sorted(labeled_axes, key=lambda x: int(x["component_index"]))
    )
    missed_text = "\n".join(f"  - {lbl} (seen {cnt}×)" for lbl, cnt in top_missed)
    return f"""\
You are analyzing gaps in a set of PCA-direction labels.

{"Domain: " + domain_hint if domain_hint else ""}

Already-labeled PCA directions:
{axes_text}

The following contrast labels appeared repeatedly across comparisons but were NOT
captured by any of the labeled directions above:
{missed_text}

Your task: synthesize up to {n_gaps} "gap directions" — latent contrasts that the
PCA directions missed but that recur in the data.

Return a JSON array. Each element must have:
  "gap_label"     : short name (≤6 words)
  "description"   : 2-4 sentences explaining what this direction captures
  "positive_pole" : what high-end items look like on this axis
  "negative_pole" : what low-end items look like on this axis
  "merged_labels" : list of missed labels this gap direction consolidates
  "support"       : estimated frequency rank (1 = most common gap)

Rules:
- Only merge labels that share a real semantic core.
- Do not rename or broaden an existing labeled direction.
- If fewer than {n_gaps} clean gaps exist, return fewer.
- Output JSON array only."""


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def write_markdown(path: Path, labeled: list, gaps: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# PCA Component Labels (Adaptive)", ""]
    for r in sorted(labeled, key=lambda x: int(x["component_index"])):
        lines += [
            f"## PC{r['component_index']}",
            "",
            f"- Explained variance: `{r['explained_variance_ratio']:.4%}`",
            f"- Confidence: `{r.get('confidence', '?')}`",
            "",
            f"**Axis label:** {r.get('axis_label', '—')}",
            "",
            f"**Positive pole:** {r.get('positive_pole', '—')}",
            "",
            f"**Negative pole:** {r.get('negative_pole', '—')}",
            "",
        ]
        missed = r.get("missed_differences") or []
        if missed:
            lines.append("**Missed differences flagged:**")
            for m in missed:
                lines.append(f"- `{m['label']}` — {m.get('reason', '')}")
            lines.append("")
    if gaps:
        lines += ["---", "", "# Gap Directions (Phase 2 synthesis)", ""]
        for g in gaps:
            lines += [
                f"## {g.get('gap_label', '—')}",
                "",
                g.get("description", ""),
                "",
                f"**Positive pole:** {g.get('positive_pole', '—')}",
                "",
                f"**Negative pole:** {g.get('negative_pole', '—')}",
                "",
                f"**Consolidated from:** {', '.join(g.get('merged_labels', []))}",
                "",
            ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report-json", required=True,
                   help="pca_report.json produced by pipeline.py or conditional_pca.py")
    p.add_argument("--output-json",
                   help="Output path for labeled components JSON (default: next to report)")
    p.add_argument("--output-md",
                   help="Output path for markdown summary")
    p.add_argument("--component-start", type=int, default=1)
    p.add_argument("--component-end", type=int, default=50)
    p.add_argument("--top-k", type=int, default=5,
                   help="Top/bottom N examples to show per component")
    p.add_argument("--max-text-chars", type=int, default=200)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--api-key", default=None,
                   help="Google API key (falls back to GOOGLE_API_KEY env var)")
    p.add_argument("--max-retries", type=int, default=4)
    p.add_argument("--retry-delay", type=float, default=5.0)
    p.add_argument("--n-gap-directions", type=int, default=8,
                   help="Max gap directions to synthesize in Phase 2")
    p.add_argument("--min-missed-count", type=int, default=2,
                   help="Min times a missed label must appear to be included in synthesis")
    p.add_argument("--domain-hint", default="",
                   help="Optional domain description passed to gap synthesis prompt")
    p.add_argument("--skip-phase2", action="store_true",
                   help="Skip gap synthesis (Phase 2)")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()
    load_dotenv()

    api_key = args.api_key or os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        raise SystemExit("No API key found. Pass --api-key or set GOOGLE_API_KEY.")

    client = make_client(api_key)

    report_path = Path(args.report_json)
    raw = json.loads(report_path.read_text(encoding="utf-8"))

    # Support both dict (has component_summaries key) and bare list formats
    report_is_dict = isinstance(raw, dict)
    component_rows = raw["component_summaries"] if report_is_dict else raw

    # Index into 1-based component numbers
    start_idx = max(args.component_start, 1) - 1
    end_idx = min(args.component_end, len(component_rows))
    selected = component_rows[start_idx:end_idx]

    # Default output paths
    stem = report_path.stem
    out_json = Path(args.output_json) if args.output_json else \
        report_path.parent / f"{stem}_adaptive_labels.json"
    out_md = Path(args.output_md) if args.output_md else \
        report_path.parent / f"{stem}_adaptive_labels.md"

    # Resume support
    labeled: list = []
    completed: dict = {}
    if out_json.exists():
        existing = json.loads(out_json.read_text(encoding="utf-8"))
        if isinstance(existing, dict):
            labeled = list(existing.get("labeled_components", []))
            # don't reload gap_directions — re-run Phase 2 fresh unless we skip
        else:
            labeled = list(existing)
        for r in labeled:
            completed[int(r["component_index"])] = r
        print(f"Resuming — {len(completed)} components already labeled.", flush=True)

    # ------------------------------------------------------------------
    # Phase 1: label each PC
    # ------------------------------------------------------------------
    for component in selected:
        raw_idx = int(component["component_index"])
        # conditional_pca report uses 1-based index already; pipeline.py uses 0-based
        component_index = raw_idx if report_is_dict else raw_idx + 1

        if component_index in completed:
            print(f"  Skipping PC{component_index} (already labeled).", flush=True)
            continue

        explained_ratio = float(
            component.get("explained_variance_ratio",
                          component.get("explained_variance_ratio_within_subset", 0.0))
        )
        cumulative_ratio = float(component.get("cumulative_explained_variance_ratio", 0.0))

        prior_ctx = prior_context(labeled)
        prompt = build_label_prompt(
            component_index, explained_ratio,
            component["positive_examples"], component["negative_examples"],
            prior_ctx, args.top_k, args.max_text_chars,
        )

        print(f"Labeling PC{component_index} ({explained_ratio:.4%} variance)...", flush=True)
        raw_text = chat(client, args.model, prompt, args.max_retries, args.retry_delay)

        # Parse response
        try:
            parsed = parse_json_blob(raw_text)
        except Exception as exc:
            print(f"  WARNING: could not parse JSON for PC{component_index}: {exc}", flush=True)
            parsed = {}

        row = {
            "component_index": component_index,
            "explained_variance_ratio": explained_ratio,
            "cumulative_explained_variance_ratio": cumulative_ratio,
            "positive_examples": component["positive_examples"][:args.top_k],
            "negative_examples": component["negative_examples"][:args.top_k],
            "axis_label": parsed.get("axis_label", ""),
            "positive_pole": parsed.get("positive_pole", ""),
            "negative_pole": parsed.get("negative_pole", ""),
            "confidence": parsed.get("confidence", ""),
            "missed_differences": parsed.get("missed_differences", []),
            "llm_prompt": prompt,
            "llm_raw": raw_text,
        }
        labeled.append(row)
        labeled.sort(key=lambda x: int(x["component_index"]))
        completed[component_index] = row

        # Checkpoint after each component
        write_json(out_json, {"labeled_components": labeled, "gap_directions": []})
        write_markdown(out_md, labeled, [])
        print(f"  -> {row['axis_label'] or '(no label)'} [confidence={row['confidence']}]", flush=True)

    # ------------------------------------------------------------------
    # Phase 2: gap synthesis
    # ------------------------------------------------------------------
    gap_directions: list = []

    if not args.skip_phase2:
        # Collect all missed differences across all labeled components
        all_missed: list[str] = []
        for r in labeled:
            for m in (r.get("missed_differences") or []):
                lbl = (m.get("label") or "").strip().lower()
                lbl = re.sub(r"[^a-z0-9\s\-]", "", lbl)
                lbl = re.sub(r"\s+", " ", lbl).strip()
                if lbl:
                    all_missed.append(lbl)

        counts = Counter(all_missed)
        top_missed = [(lbl, cnt) for lbl, cnt in counts.most_common(40)
                      if cnt >= args.min_missed_count]

        if top_missed:
            print(f"\nPhase 2: synthesizing gaps from {len(top_missed)} recurring missed labels...",
                  flush=True)
            gap_prompt = build_gap_synthesis_prompt(
                args.domain_hint, labeled, top_missed, args.n_gap_directions,
            )
            raw_gaps = chat(client, args.model, gap_prompt, args.max_retries, args.retry_delay)
            try:
                gap_directions = parse_json_blob(raw_gaps)
                if not isinstance(gap_directions, list):
                    gap_directions = [gap_directions]
                print(f"  -> {len(gap_directions)} gap direction(s) identified.", flush=True)
                for g in gap_directions:
                    print(f"     {g.get('gap_label', '?')} | from: {g.get('merged_labels', [])}", flush=True)
            except Exception as exc:
                print(f"  WARNING: could not parse gap synthesis response: {exc}", flush=True)
                gap_directions = []
        else:
            print("\nPhase 2: no recurring missed labels found — skipping gap synthesis.", flush=True)

    # Final write
    output = {"labeled_components": labeled, "gap_directions": gap_directions}
    write_json(out_json, output)
    write_markdown(out_md, labeled, gap_directions)

    summary = {
        "output_json": str(out_json),
        "output_md": str(out_md),
        "labeled_components": len(labeled),
        "gap_directions": len(gap_directions),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
