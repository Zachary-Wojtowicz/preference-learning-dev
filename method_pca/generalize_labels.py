#!/usr/bin/env python3
"""
Label generalization pass.

Identifies hyperspecific labels (those that name specific regions, varietals,
or producers) and groups them with other similar labels.  For each group, asks
the LLM:
  - Is there a single higher-level axis that covers all of them?
  - Does that abstraction still correctly describe the examples for each PC?
  - What does the abstraction miss that the specific labels captured?

Produces a final relabeled JSON + markdown showing which PCs benefit from
generalization vs. which genuinely need specificity.
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
        lambda c: json.loads(c[c.find("["):c.rfind("]") + 1]),
        lambda c: json.loads(_fix_escapes(c[c.find("["):c.rfind("]") + 1])),
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
        lines.append(f"  - {label} | {compact(item['text'], max_chars)}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Step 1: ask LLM to cluster the labels into groups and propose abstractions
# ---------------------------------------------------------------------------

def build_cluster_prompt(domain_hint, all_labels_with_pc):
    label_lines = "\n".join(
        f"  PC{pc}: {label}" for pc, label in sorted(all_labels_with_pc, key=lambda x: x[0])
    )
    return f"""\
You are analyzing a set of PCA component labels{" for " + domain_hint if domain_hint else ""}.
Many labels are hyperspecific — they name particular regions, varietals, or producers.
Your job is to find groups of labels that share a deeper underlying contrast,
and propose a single abstract axis that covers each group.

Current labels:
{label_lines}

Instructions:
1. Identify groups of 2+ labels that seem to capture the same underlying contrast
   at a more abstract level (e.g. several "X region vs. Y region" labels might all
   be capturing "Terroir Expression Style" or "Production Philosophy").
2. For each group, propose one abstract axis label (≤6 words) that:
   - Covers all members of the group
   - Is more general but still meaningful and testable
   - Avoids being so broad it loses all information
3. Also flag any labels that are appropriately specific and should NOT be generalized.

Return a JSON array. Each element:
  "abstract_label"  : proposed abstraction (≤6 words)
  "positive_pole"   : what high-scoring items share (1-2 sentences)
  "negative_pole"   : what low-scoring items share (1-2 sentences)
  "member_pcs"      : list of PC indices covered by this abstraction
  "member_labels"   : list of current labels being replaced
  "keep_specific"   : false (these should be generalized)

Then append objects for labels that should stay specific:
  "abstract_label"  : same as current label
  "member_pcs"      : [pc_index]
  "member_labels"   : [current_label]
  "keep_specific"   : true
  "reason"          : why specificity is warranted here

Output JSON array only."""


# ---------------------------------------------------------------------------
# Step 2: for each proposed abstraction, verify it against each member PC's examples
# ---------------------------------------------------------------------------

def build_verify_prompt(pc_index, current_label, abstract_label,
                         abstract_pos, abstract_neg,
                         group_labels,
                         pos_examples, neg_examples, top_k, max_chars):
    pos_block = fmt_examples("High-scoring examples:", pos_examples, top_k, max_chars)
    neg_block = fmt_examples("Low-scoring examples:", neg_examples, top_k, max_chars)
    group_str = "; ".join(f'"{l}"' for l in group_labels if l != current_label)
    return f"""\
You are verifying whether an abstract label correctly describes a PCA component.

PC{pc_index} current label: "{current_label}"
Proposed abstract label   : "{abstract_label}"
  Positive pole: {abstract_pos}
  Negative pole: {abstract_neg}

This abstraction was also proposed for: {group_str}

{pos_block}

{neg_block}

Questions:
1. Does "{abstract_label}" correctly describe the contrast visible in these examples?
2. Does it lose important information that "{current_label}" captured?
3. Is there a BETTER abstract label that still covers these examples?

Return JSON:
  "fits"           : true | false — does the abstraction correctly describe this PC?
  "loses_info"     : true | false — does generalizing lose meaningful signal?
  "better_label"   : a refined label if you can improve on the proposed abstraction, else null
  "better_pos"     : refined positive pole if better_label, else null
  "better_neg"     : refined negative pole if better_label, else null
  "reasoning"      : ≤2 sentences
Output JSON only."""


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def write_markdown(path, final_labels, groups, verify_results):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Generalized Labels", ""]

    # Groups that were generalized
    generalized = [g for g in groups if not g.get("keep_specific") and len(g["member_pcs"]) > 1]
    kept = [g for g in groups if g.get("keep_specific")]

    if generalized:
        lines += ["## Generalized groups", ""]
        for g in generalized:
            lines.append(f"### {g['abstract_label']}")
            lines.append(f"- Covers: PC{', PC'.join(str(p) for p in g['member_pcs'])}")
            lines.append(f"- Replaced: {'; '.join(g['member_labels'])}")
            lines.append(f"- Positive pole: {g.get('positive_pole', '—')}")
            lines.append(f"- Negative pole: {g.get('negative_pole', '—')}")

            # Show per-PC verification
            for pc in g["member_pcs"]:
                v = verify_results.get((g["abstract_label"], pc), {})
                fits = v.get("fits")
                loses = v.get("loses_info")
                better = v.get("better_label")
                icon = "✓" if fits else "✗"
                note = f" → better: *{better}*" if better else ""
                loses_note = " *(loses info)*" if loses else ""
                lines.append(f"  - PC{pc}: {icon}{loses_note}{note}  {v.get('reasoning', '')}")
            lines.append("")

    if kept:
        lines += ["## Kept specific (generalization not warranted)", ""]
        for g in kept:
            lines.append(f"- PC{g['member_pcs'][0]}: *{g['abstract_label']}* — {g.get('reason', '')}")
        lines.append("")

    lines += ["---", "", "## Final label list", ""]
    for pc, label, pos, neg, changed in sorted(final_labels, key=lambda x: x[0]):
        tag = " *(generalized)*" if changed else ""
        lines.append(f"- **PC{pc}**: {label}{tag}")

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--labels-json", required=True,
                   help="adaptive_labels.json (optionally already partially relabeled)")
    p.add_argument("--relabel-json", default=None,
                   help="relabel_candidates.json — applies prior relabelings before generalizing")
    p.add_argument("--output-json")
    p.add_argument("--output-md")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--max-text-chars", type=int, default=200)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--api-key", default=None)
    p.add_argument("--max-retries", type=int, default=4)
    p.add_argument("--retry-delay", type=float, default=5.0)
    p.add_argument("--domain-hint", default="wine tasting notes")
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

    # Apply any prior relabelings
    effective_labels = {int(r["component_index"]): r for r in components}
    if args.relabel_json:
        relabels = json.loads(Path(args.relabel_json).read_text(encoding="utf-8"))
        for pc_str, r in relabels.get("results", {}).items():
            pc = int(pc_str)
            if r.get("verdict") in ("RELABEL", "AUGMENT") and r.get("suggested_label"):
                effective_labels[pc] = dict(effective_labels[pc])
                effective_labels[pc]["axis_label"] = r["suggested_label"]
                effective_labels[pc]["positive_pole"] = r.get("suggested_pos_pole", "")
                effective_labels[pc]["negative_pole"] = r.get("suggested_neg_pole", "")

    all_labels_with_pc = [
        (pc, comp["axis_label"])
        for pc, comp in sorted(effective_labels.items())
        if comp.get("axis_label")
    ]

    out_json = Path(args.output_json) if args.output_json else \
        Path(args.labels_json).parent / "generalized_labels.json"
    out_md = Path(args.output_md) if args.output_md else \
        Path(args.labels_json).parent / "generalized_labels.md"

    # --- Step 1: cluster & propose abstractions ---
    print("Step 1: clustering labels and proposing abstractions...", flush=True)
    cluster_prompt = build_cluster_prompt(args.domain_hint, all_labels_with_pc)
    raw = chat(client, args.model, cluster_prompt, args.max_retries, args.retry_delay)
    try:
        groups = parse_json_blob(raw)
        if isinstance(groups, dict):
            groups = [groups]
    except Exception as exc:
        raise SystemExit(f"Could not parse cluster response: {exc}\n{raw[:400]}")

    print(f"  Got {len(groups)} groups/clusters", flush=True)
    for g in groups:
        if g.get("keep_specific"):
            print(f"  KEEP  PC{g['member_pcs']}: {g['abstract_label']}", flush=True)
        else:
            print(f"  GROUP {g['member_pcs']}: {g['abstract_label']} "
                  f"(was: {g['member_labels']})", flush=True)

    # --- Step 2: verify each proposed abstraction against member PC examples ---
    print("\nStep 2: verifying abstractions against PC examples...", flush=True)
    verify_results = {}  # (abstract_label, pc_index) -> parsed result

    for g in groups:
        if g.get("keep_specific"):
            continue
        if len(g.get("member_pcs", [])) < 2:
            continue

        for pc in g["member_pcs"]:
            comp = effective_labels.get(pc)
            if not comp:
                continue

            key = (g["abstract_label"], pc)
            print(f"  Verify '{g['abstract_label']}' for PC{pc} "
                  f"[{comp.get('axis_label', '?')}]", flush=True)

            prompt = build_verify_prompt(
                pc_index=pc,
                current_label=comp.get("axis_label", ""),
                abstract_label=g["abstract_label"],
                abstract_pos=g.get("positive_pole", ""),
                abstract_neg=g.get("negative_pole", ""),
                group_labels=g["member_labels"],
                pos_examples=comp.get("positive_examples", []),
                neg_examples=comp.get("negative_examples", []),
                top_k=args.top_k,
                max_chars=args.max_text_chars,
            )

            raw_v = chat(client, args.model, prompt, args.max_retries, args.retry_delay)
            try:
                parsed = parse_json_blob(raw_v)
            except Exception as exc:
                print(f"    WARNING: parse failed: {exc}", flush=True)
                parsed = {}

            verify_results[key] = parsed
            fits = parsed.get("fits")
            loses = parsed.get("loses_info")
            better = parsed.get("better_label")
            print(f"    fits={fits}  loses_info={loses}  better={better}", flush=True)

    # --- Build final labels ---
    # For each PC: use abstraction if it fits; use better_label if provided;
    # fall back to current if it doesn't fit or loses too much info
    final_labels = []  # (pc, label, pos_pole, neg_pole, changed)

    for pc, comp in sorted(effective_labels.items()):
        current = comp.get("axis_label", "")
        current_pos = comp.get("positive_pole", "")
        current_neg = comp.get("negative_pole", "")

        # Find which group this PC belongs to
        assigned_group = None
        for g in groups:
            if pc in g.get("member_pcs", []) and not g.get("keep_specific"):
                assigned_group = g
                break

        if assigned_group is None or len(assigned_group.get("member_pcs", [])) < 2:
            final_labels.append((pc, current, current_pos, current_neg, False))
            continue

        key = (assigned_group["abstract_label"], pc)
        v = verify_results.get(key, {})

        # Use better_label if provided, else use abstract_label if it fits
        if v.get("better_label"):
            new_label = v["better_label"]
            new_pos = v.get("better_pos") or assigned_group.get("positive_pole", "")
            new_neg = v.get("better_neg") or assigned_group.get("negative_pole", "")
            final_labels.append((pc, new_label, new_pos, new_neg, True))
        elif v.get("fits") and not v.get("loses_info"):
            final_labels.append((pc, assigned_group["abstract_label"],
                                  assigned_group.get("positive_pole", ""),
                                  assigned_group.get("negative_pole", ""), True))
        elif v.get("fits"):
            # Fits but loses info — use abstract as prefix + note
            final_labels.append((pc, assigned_group["abstract_label"],
                                  assigned_group.get("positive_pole", ""),
                                  assigned_group.get("negative_pole", ""), True))
        else:
            # Doesn't fit — keep specific
            final_labels.append((pc, current, current_pos, current_neg, False))

    output = {
        "groups": groups,
        "verify_results": {f"{k[0]}|{k[1]}": v for k, v in verify_results.items()},
        "final_labels": [
            {"pc_index": pc, "label": lbl, "positive_pole": pos, "negative_pole": neg,
             "generalized": changed}
            for pc, lbl, pos, neg, changed in final_labels
        ],
    }
    write_json(out_json, output)
    write_markdown(out_md, final_labels, groups, verify_results)

    print("\n=== FINAL LABELS ===")
    for pc, lbl, pos, neg, changed in sorted(final_labels, key=lambda x: x[0]):
        tag = " *(generalized)*" if changed else ""
        print(f"  PC{pc}: {lbl}{tag}")

    print(json.dumps({
        "output_json": str(out_json),
        "output_md": str(out_md),
        "groups": len(groups),
        "pcs_generalized": sum(1 for _, _, _, _, c in final_labels if c),
    }, indent=2))


if __name__ == "__main__":
    main()
