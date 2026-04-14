#!/usr/bin/env python3
"""
Relabel candidates.

For each PC, scores how strongly each gap direction is represented in
its missed_differences (excluding the universal "Vintage & Temporal Effects"
confounder).  If one gap accounts for ≥ --domination-threshold of a PC's
non-vintage missed labels, it's flagged as a relabel candidate.

For each candidate, a forced-choice LLM prompt is run that must answer:
  RELABEL  — the gap direction is the dominant axis; replace the current label
  AUGMENT  — the gap is real and co-equal; the label should be widened
  KEEP     — current label is correct; gap is secondary

Writes a final JSON with verdicts + suggested new labels, and a markdown
summary showing which PCs got relabeled.
"""

import argparse
import json
import os
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
GOOGLE_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_MODEL = "gemma-3-27b-it"
UNIVERSAL_GAPS = {"Vintage & Temporal Effects", "Reviewer & Contextual Bias"}


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


def normalize(s):
    s = re.sub(r"[^a-z0-9\s\-]", "", (s or "").strip().lower())
    return re.sub(r"\s+", " ", s).strip()


def compact(text, max_chars):
    text = " ".join(text.split())
    return text if len(text) <= max_chars else text[:max_chars - 3].rstrip() + "..."


def fmt_examples(title, items, top_k, max_chars):
    lines = [title]
    for item in items[:top_k]:
        label = item.get("label") or item.get("group") or f"row {item['row_index']}"
        lines.append(f"  - {label} | score={item['score']:.4f} | {compact(item['text'], max_chars)}")
    return "\n".join(lines)


def score_pc_gaps(comp, gaps, universal_gaps):
    """
    Returns dict: {gap_label -> count of comp's missed labels that belong to it}
    Only counts labels NOT in universal_gaps.
    Also returns total non-universal missed label count.
    """
    all_missed = []
    for m in (comp.get("missed_differences") or []):
        lbl = normalize(m.get("label", ""))
        if lbl:
            all_missed.append(lbl)

    gap_scores = {}
    for gap in gaps:
        if gap["gap_label"] in universal_gaps:
            continue
        merged = {normalize(lbl) for lbl in gap.get("merged_labels", [])}
        count = sum(1 for lbl in all_missed if lbl in merged)
        if count > 0:
            gap_scores[gap["gap_label"]] = count

    total_non_universal = len(all_missed)
    # subtract universal labels from total
    universal_merged = set()
    for gap in gaps:
        if gap["gap_label"] in universal_gaps:
            universal_merged.update(normalize(lbl) for lbl in gap.get("merged_labels", []))
    non_universal_total = sum(1 for lbl in all_missed if lbl not in universal_merged)

    return gap_scores, non_universal_total, all_missed


def build_relabel_prompt(pc_index, current_label, current_pos, current_neg,
                          gap_label, gap_desc, gap_pos, gap_neg,
                          gap_count, total_missed, all_missed_labels,
                          pos_examples, neg_examples, top_k, max_chars):
    pos_block = fmt_examples("High-scoring examples:", pos_examples, top_k, max_chars)
    neg_block = fmt_examples("Low-scoring examples:", neg_examples, top_k, max_chars)
    missed_str = ", ".join(f'"{lbl}"' for lbl in all_missed_labels[:12])
    return f"""\
You are deciding whether a PCA component should be relabeled.

PC{pc_index} — Current label: "{current_label}"
  Positive pole: {current_pos}
  Negative pole: {current_neg}

Challenger: "{gap_label}"
  Description : {gap_desc}
  Positive pole: {gap_pos}
  Negative pole: {gap_neg}

Evidence: {gap_count} out of {total_missed} non-universal missed-difference labels \
for this component pointed to "{gap_label}".
All missed labels were: {missed_str}

{pos_block}

{neg_block}

FORCED CHOICE — you must pick exactly one:
  RELABEL : The gap direction IS the primary axis. The current label is a proxy or \
side-effect of the gap. Replace it.
  AUGMENT : Both contrasts are genuinely present and co-equal. Widen the label to \
cover both.
  KEEP    : The current label is the dominant axis. The gap is real but secondary.

Rules that prevent you from waffling:
- If the current label is just a specific instance of the gap direction \
(e.g. "Cabernet vs. Others" is one instance of "Color"), choose RELABEL.
- If the examples split cleanly on the gap AND cleanly on the current axis, \
choose AUGMENT.
- If the current label explains the split better than the gap, choose KEEP.
- You CANNOT choose RELABEL unless you can write a concrete new label (≤8 words) \
that subsumes or replaces the current one.

Return JSON:
  "verdict"       : "RELABEL" | "AUGMENT" | "KEEP"
  "reasoning"     : ≤3 sentences (cite specific examples)
  "suggested_label"     : new axis name if RELABEL or AUGMENT, else null
  "suggested_pos_pole"  : new positive pole (1-2 sentences) if RELABEL/AUGMENT, else null
  "suggested_neg_pole"  : new negative pole (1-2 sentences) if RELABEL/AUGMENT, else null
Output JSON only."""


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def write_markdown(path, candidates, results_by_pc):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Relabel Candidates", ""]

    relabeled = [(pc, r) for pc, r in results_by_pc.items() if r.get("verdict") == "RELABEL"]
    augmented = [(pc, r) for pc, r in results_by_pc.items() if r.get("verdict") == "AUGMENT"]
    kept = [(pc, r) for pc, r in results_by_pc.items() if r.get("verdict") == "KEEP"]

    def section(title, rows):
        if not rows:
            return
        lines.append(f"## {title} ({len(rows)})")
        lines.append("")
        for pc, r in sorted(rows, key=lambda x: x[0]):
            lines.append(f"### PC{pc}")
            lines.append(f"- Old label: *{r['current_label']}*")
            if r.get("suggested_label"):
                lines.append(f"- **New label: {r['suggested_label']}**")
            lines.append(f"- Gap challenger: {r['gap_label']} "
                         f"({r['gap_count']}/{r['total_non_universal_missed']} non-universal missed labels)")
            lines.append(f"- Reasoning: {r.get('reasoning', '—')}")
            if r.get("suggested_pos_pole"):
                lines.append(f"- Positive pole: {r['suggested_pos_pole']}")
            if r.get("suggested_neg_pole"):
                lines.append(f"- Negative pole: {r['suggested_neg_pole']}")
            lines.append("")

    section("RELABEL — gap is the dominant axis", relabeled)
    section("AUGMENT — both axes co-equal; label widened", augmented)
    section("KEEP — current label wins", kept)

    # Also write a final clean label list
    lines += ["---", "", "## Final labels after relabeling", ""]
    for cand in sorted(candidates, key=lambda x: x["pc_index"]):
        pc = cand["pc_index"]
        r = results_by_pc.get(pc, {})
        v = r.get("verdict")
        if v in ("RELABEL", "AUGMENT") and r.get("suggested_label"):
            label = r["suggested_label"]
            tag = "*(relabeled)*" if v == "RELABEL" else "*(augmented)*"
        else:
            label = cand["current_label"]
            tag = ""
        lines.append(f"- PC{pc}: {label} {tag}")

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--labels-json", required=True)
    p.add_argument("--output-json")
    p.add_argument("--output-md")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--max-text-chars", type=int, default=200)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--api-key", default=None)
    p.add_argument("--max-retries", type=int, default=4)
    p.add_argument("--retry-delay", type=float, default=5.0)
    p.add_argument("--domination-threshold", type=float, default=0.5,
                   help="Fraction of non-universal missed labels a gap must account for "
                        "to trigger a relabel check (default 0.5)")
    p.add_argument("--min-gap-count", type=int, default=1,
                   help="Minimum absolute gap label count to trigger check (default 1)")
    p.add_argument("--universal-gaps", nargs="*", default=list(UNIVERSAL_GAPS),
                   help="Gap labels to exclude from domination scoring (universal confounders)")
    return p.parse_args()


def main():
    args = parse_args()
    load_dotenv()

    api_key = args.api_key or os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        raise SystemExit("No API key. Pass --api-key or set GOOGLE_API_KEY.")

    client = make_client(api_key)
    data = json.loads(Path(args.labels_json).read_text(encoding="utf-8"))
    components = data["labeled_components"]
    gaps = data["gap_directions"]
    gaps_by_label = {g["gap_label"]: g for g in gaps}

    universal_gaps = set(args.universal_gaps)

    out_json = Path(args.output_json) if args.output_json else \
        Path(args.labels_json).parent / "relabel_candidates.json"
    out_md = Path(args.output_md) if args.output_md else \
        Path(args.labels_json).parent / "relabel_candidates.md"

    # Score each PC
    candidates = []
    for comp in components:
        gap_scores, non_univ_total, all_missed = score_pc_gaps(comp, gaps, universal_gaps)
        if not gap_scores or non_univ_total == 0:
            continue
        # Find the dominant gap (highest count)
        top_gap, top_count = max(gap_scores.items(), key=lambda x: x[1])
        fraction = top_count / non_univ_total if non_univ_total > 0 else 0.0
        candidates.append({
            "pc_index": comp["component_index"],
            "current_label": comp.get("axis_label", ""),
            "gap_scores": gap_scores,
            "top_gap": top_gap,
            "top_gap_count": top_count,
            "non_universal_missed": non_univ_total,
            "domination_fraction": round(fraction, 3),
            "all_missed_labels": all_missed,
            "triggers_check": fraction >= args.domination_threshold and top_count >= args.min_gap_count,
        })

    candidates.sort(key=lambda x: x["domination_fraction"], reverse=True)

    print(f"\nDomination scores (excluding universal gaps: {sorted(universal_gaps)}):")
    print(f"{'PC':<5} {'fraction':>8}  {'top_gap':<35}  {'count':>5}  {'check?'}")
    print("-" * 75)
    for c in candidates:
        flag = "<-- CHECK" if c["triggers_check"] else ""
        print(f"PC{c['pc_index']:<3} {c['domination_fraction']:>8.0%}  "
              f"{c['top_gap']:<35}  {c['top_gap_count']:>5}/{c['non_universal_missed']}  {flag}")

    to_check = [c for c in candidates if c["triggers_check"]]
    print(f"\n{len(to_check)} PCs trigger relabel check (threshold={args.domination_threshold:.0%})")

    # Resume
    results_by_pc = {}
    if out_json.exists():
        existing = json.loads(out_json.read_text(encoding="utf-8"))
        if isinstance(existing, dict):
            results_by_pc = {int(k): v for k, v in existing.get("results", {}).items()}
        print(f"Resuming — {len(results_by_pc)} already done.", flush=True)

    comp_by_idx = {int(r["component_index"]): r for r in components}

    for cand in to_check:
        pc = cand["pc_index"]
        if pc in results_by_pc:
            print(f"  Skip PC{pc}", flush=True)
            continue

        gap = gaps_by_label.get(cand["top_gap"])
        comp = comp_by_idx.get(pc)
        if not gap or not comp:
            continue

        print(f"\nPC{pc}  '{comp.get('axis_label')}' vs '{gap['gap_label']}' "
              f"({cand['top_gap_count']}/{cand['non_universal_missed']} = "
              f"{cand['domination_fraction']:.0%})", flush=True)

        prompt = build_relabel_prompt(
            pc_index=pc,
            current_label=comp.get("axis_label", ""),
            current_pos=comp.get("positive_pole", ""),
            current_neg=comp.get("negative_pole", ""),
            gap_label=gap["gap_label"],
            gap_desc=gap.get("description", ""),
            gap_pos=gap.get("positive_pole", ""),
            gap_neg=gap.get("negative_pole", ""),
            gap_count=cand["top_gap_count"],
            total_missed=cand["non_universal_missed"],
            all_missed_labels=cand["all_missed_labels"],
            pos_examples=comp.get("positive_examples", []),
            neg_examples=comp.get("negative_examples", []),
            top_k=args.top_k,
            max_chars=args.max_text_chars,
        )

        raw = chat(client, args.model, prompt, args.max_retries, args.retry_delay)
        try:
            parsed = parse_json_blob(raw)
        except Exception as exc:
            print(f"  WARNING: parse failed: {exc}", flush=True)
            parsed = {}

        result = {
            "pc_index": pc,
            "current_label": comp.get("axis_label", ""),
            "gap_label": cand["top_gap"],
            "gap_count": cand["top_gap_count"],
            "total_non_universal_missed": cand["non_universal_missed"],
            "domination_fraction": cand["domination_fraction"],
            "verdict": parsed.get("verdict", "KEEP"),
            "reasoning": parsed.get("reasoning", ""),
            "suggested_label": parsed.get("suggested_label"),
            "suggested_pos_pole": parsed.get("suggested_pos_pole"),
            "suggested_neg_pole": parsed.get("suggested_neg_pole"),
            "llm_raw": raw,
        }
        results_by_pc[pc] = result
        v = result["verdict"]
        new = result.get("suggested_label") or "(no change)"
        print(f"  -> {v}  new label: {new}", flush=True)

        write_json(out_json, {"candidates": candidates, "results": results_by_pc})

    write_json(out_json, {"candidates": candidates, "results": results_by_pc})
    write_markdown(out_md, candidates, results_by_pc)

    from collections import Counter as C
    counts = C(r.get("verdict") for r in results_by_pc.values())
    print("\n=== FINAL VERDICTS ===")
    for v, n in counts.most_common():
        print(f"  {v}: {n}")
    print(json.dumps({
        "output_json": str(out_json),
        "output_md": str(out_md),
        "candidates_checked": len(results_by_pc),
    }, indent=2))


if __name__ == "__main__":
    main()
