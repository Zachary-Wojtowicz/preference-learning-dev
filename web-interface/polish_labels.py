#!/usr/bin/env python3
"""Polish dimension labels for the experiment using the Anthropic API.

Reads outputs/<domain>/experiment_config.json, sends each dimension to Claude
with a conservative prompt that biases toward keeping current labels, and writes
proposed changes to outputs/<domain>/polished_labels.json. Does not modify
experiment_config.json or upstream dimensions.json.

The frontend (index.html) loads polished_labels.json optionally and applies
it as an overlay; deleting the file fully reverts to the raw labels.

Usage:
    # Dry run — print proposed changes, write nothing
    python3 polish_labels.py outputs/dailydilemmas

    # Actually write outputs/dailydilemmas/polished_labels.json
    python3 polish_labels.py outputs/dailydilemmas --write

    # Abort if more than 8 replacements proposed
    python3 polish_labels.py outputs/dailydilemmas --write --max-changes 8

    # Include all dimensions in the file (not just changed ones)
    python3 polish_labels.py outputs/dailydilemmas --write --full

Requires:
    pip install anthropic
    ANTHROPIC_API_KEY environment variable set
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from anthropic import Anthropic
except ImportError:
    sys.exit("Error: install with `pip install anthropic`.")

DEFAULT_MODEL = "claude-sonnet-4-6"

REVIEW_PROMPT = """You are reviewing a preference dimension label for a research experiment in the domain of {domain}.

In the experiment, the participant sees a sentence like:
  "You deeply care about <NAME>."   or    "You are neutral about <NAME>."
where <NAME> is the dimension's name. The name must be a substantive noun phrase that is immediately intuitive in this sentence.

============================================================
CRITICAL: The dimension is directional.

Internally, each option of a pair has a signed score on this dimension. A
positive score means the option is at the HIGH pole (described by high_label);
a negative score means it is at the LOW pole (described by low_label). The
participant's inferred preference for this dimension is read off the score's
sign — so the *name* must point in the same direction as high_label.

That is, "more <NAME>" must describe the same state as high_label.
Equivalently: "You deeply care about <NAME>" must mean the participant favors
the high_label end (not the low_label end).

If any rename you propose would invert this — even subtly — KEEP the original.
============================================================

Current dimension:
  name:               "{name}"
  low_label (low end of score):   "{low_label}"
  high_label (high end of score): "{high_label}"
  scoring_guidance:               "{scoring_guidance}"

Decide whether to keep or replace. Bias strongly toward KEEP.

Replace ONLY if one of these issues clearly applies AND you can preserve direction:

  (a) The name does not match what the poles describe.
      Example: name "Emotional Well-Being" but poles Detached/Sensitive — those
      aren't well-being. A safe rename here is "Emotional Sensitivity" (high =
      Sensitive matches high_label) — direction preserved.

  (b) The name is too abstract or jargon-y for a participant to grasp at a glance.
      Example: "Experience Orientation" with poles Avoidant/Experiential — rename
      to "Adventurousness" (high = adventurous, matches high_label).

DO NOT "symmetrize" asymmetric-looking names — they are usually directionally
correct labels for the high pole, and renaming inverts the meaning. Examples:

  - "Conflict Avoidance" (poles: Conflict-Seeking / Conflict-Avoiding) → high = avoiding.
    Renaming to "Conflict Tolerance" would put high = tolerating = seeking = INVERTED. KEEP.
  - "Risk Aversion" (Risk-Taking / Risk-Averse) → high = averse.
    Renaming to "Risk" would put high = more risk = taking = INVERTED. KEEP.
  - "Formality Avoidance" (Formal / Informal) → high = informal.
    Renaming to "Formality" would put high = more formal = INVERTED. KEEP. (Or rename
    to "Informality" to preserve direction — that's safe.)
  - "Tradition Adherence" (Innovative / Traditional) → high = traditional.
    Renaming to "Innovation" would invert. Keep, or rename to "Traditionalism".

DO NOT replace just because a name is wordy. "Long-Term Orientation" and
"Duty Orientation" are clear enough; KEEP them.

Before proposing a REPLACE, perform this self-check explicitly:

  Q1. Does "You deeply care about <new_name>" describe a person whose option
      score is at the <high_label> end (not the low_label end)?
  Q2. If you also propose new pole labels, does new_high describe the same
      physical state as the original high_label (not flipped)?

  If you cannot answer YES to both with high confidence, output decision="keep".

Return ONLY a JSON object (no surrounding text, no markdown fences) with these fields:
  decision:  "keep" or "replace"
  new_name:  string (only if replace; 1-3 words; "more <new_name>" must mean same as high_label)
  new_low:   string (only if pole labels also need updating; must describe same state as low_label)
  new_high:  string (same; must describe same state as high_label, never flipped)
  rationale: one short sentence; if replacing, explicitly note that direction is preserved
"""


def extract_json(text):
    """Pull a single JSON object from a model response, tolerating fences."""
    text = text.strip()
    # Strip markdown fences if present.
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fallback: find the first balanced { ... } block.
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        return json.loads(m.group(0))
    raise ValueError(f"Could not parse JSON from response: {text[:200]}")


def review_dimension(client, model, domain, dim):
    prompt = REVIEW_PROMPT.format(
        domain=domain,
        name=dim.get("name", ""),
        low_label=dim.get("low_label", ""),
        high_label=dim.get("high_label", ""),
        scoring_guidance=dim.get("scoring_guidance", ""),
    )
    resp = client.messages.create(
        model=model,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    return extract_json(resp.content[0].text)


VALIDATION_PROMPT = """You are checking that a proposed rename of a dimension label preserves the dimension's direction.

The dimension has a numeric score per option: positive scores describe the HIGH pole, negative scores the LOW pole. The dimension's name must point in the same direction as high_label — i.e., "more <name>" must describe the same state as high_label.

Original:
  name:        "{old_name}"
  high_label:  "{old_high}"   (positive scores describe THIS state)
  low_label:   "{old_low}"    (negative scores describe THIS state)

Proposed:
  name:        "{new_name}"
  high_label:  "{new_high}"
  low_label:   "{new_low}"

Verify two things:

  Q1. Does "more {new_name}" describe the same state as the original "{old_high}"?
      Equivalently: does "You deeply care about {new_name}" describe a person at the
      {old_high} end (not the {old_low} end)?

  Q2. If new pole labels were proposed (new_high != old_high or new_low != old_low),
      do they describe the same physical states as the originals (not silently flipped)?
      I.e., new_high should describe what {old_high} describes; new_low should describe
      what {old_low} describes.

If EITHER check fails, the rename inverts the dimension. Reject.

Return ONLY a JSON object (no surrounding text):
  approve: true or false
  reason:  one short sentence
"""


def validate_rename(client, model, old, new):
    prompt = VALIDATION_PROMPT.format(
        old_name=old["name"], old_high=old["high_label"], old_low=old["low_label"],
        new_name=new["name"], new_high=new["high_label"], new_low=new["low_label"],
    )
    resp = client.messages.create(
        model=model,
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    return extract_json(resp.content[0].text)


def main():
    p = argparse.ArgumentParser(
        description="Polish dimension labels via the Anthropic API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Usage:")[1] if __doc__ else None,
    )
    p.add_argument("domain_dir", type=Path, help="Path to outputs/<domain>/")
    p.add_argument("--write", action="store_true",
                   help="Save polished_labels.json (default: dry-run, print only).")
    p.add_argument("--full", action="store_true",
                   help="Include all dimensions in output (default: only changed).")
    p.add_argument("--max-changes", type=int, default=None, metavar="N",
                   help="Abort if more than N replacements are proposed.")
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"Anthropic model id (default: {DEFAULT_MODEL}).")
    p.add_argument("--no-validate", action="store_true",
                   help="Skip the second-pass direction-preservation check on each REPLACE.")
    args = p.parse_args()

    cfg_path = args.domain_dir / "experiment_config.json"
    if not cfg_path.exists():
        sys.exit(f"Error: {cfg_path} not found.")

    cfg = json.loads(cfg_path.read_text())
    dims = cfg.get("dimensions") or []
    domain = cfg.get("domain") or args.domain_dir.name

    if not dims:
        sys.exit("Error: no `dimensions` array in experiment_config.json.")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Error: ANTHROPIC_API_KEY environment variable not set.")

    client = Anthropic()
    print(f"Reviewing {len(dims)} dimensions in domain={domain!r} with model={args.model}\n")

    changed = {}     # dim_id -> {name, low_label, high_label, rationale, original}
    unchanged = {}   # dim_id -> {name, low_label, high_label}  (used only if --full)
    n_keep = n_replace = n_error = n_rejected = 0

    for i, dim in enumerate(dims, 1):
        did = str(dim.get("dimension_id"))
        old_name = dim.get("name", "")
        old_low = dim.get("low_label", "")
        old_high = dim.get("high_label", "")
        try:
            r = review_dimension(client, args.model, domain, dim)
        except Exception as e:
            print(f"  [{i:>2}/{len(dims)}]  dim_{did:<3}  ERROR: {e}")
            n_error += 1
            continue

        decision = (r.get("decision") or "keep").strip().lower()
        rationale = (r.get("rationale") or "").strip()

        if decision == "replace":
            new_name = (r.get("new_name") or "").strip() or old_name
            new_low = (r.get("new_low") or "").strip() or old_low
            new_high = (r.get("new_high") or "").strip() or old_high
            actually_changed = (
                new_name != old_name or new_low != old_low or new_high != old_high
            )
            if not actually_changed:
                # Treat as keep if nothing actually differs.
                print(f"  [{i:>2}/{len(dims)}]  dim_{did:<3}  KEEP    {old_name}")
                n_keep += 1
                if args.full:
                    unchanged[did] = {
                        "name": old_name, "low_label": old_low, "high_label": old_high,
                    }
                continue

            # Direction-preservation validation pass on the proposed rename.
            old_triple = {"name": old_name, "low_label": old_low, "high_label": old_high}
            new_triple = {"name": new_name, "low_label": new_low, "high_label": new_high}
            if not args.no_validate:
                try:
                    v = validate_rename(client, args.model, old_triple, new_triple)
                except Exception as e:
                    print(f"  [{i:>2}/{len(dims)}]  dim_{did:<3}  VALIDATION ERROR: {e} — falling back to KEEP")
                    n_rejected += 1
                    continue
                if not v.get("approve"):
                    reject_reason = (v.get("reason") or "direction not preserved").strip()
                    print(f"  [{i:>2}/{len(dims)}]  dim_{did:<3}  REJECTED rename {old_name!r} → {new_name!r}")
                    print(f"                          reason: {reject_reason}")
                    n_rejected += 1
                    if args.full:
                        unchanged[did] = {
                            "name": old_name, "low_label": old_low, "high_label": old_high,
                        }
                    continue

            changed[did] = {
                "name": new_name,
                "low_label": new_low,
                "high_label": new_high,
                "rationale": rationale,
                "original": {
                    "name": old_name, "low_label": old_low, "high_label": old_high,
                },
            }
            n_replace += 1
            print(f"  [{i:>2}/{len(dims)}]  dim_{did:<3}  REPLACE {old_name!r} → {new_name!r}")
            if new_low != old_low or new_high != old_high:
                print(f"                          poles: {old_low!r} / {old_high!r}")
                print(f"                              -> {new_low!r} / {new_high!r}")
            if rationale:
                print(f"                          reason: {rationale}")
        else:
            print(f"  [{i:>2}/{len(dims)}]  dim_{did:<3}  KEEP    {old_name}")
            n_keep += 1
            if args.full:
                unchanged[did] = {
                    "name": old_name, "low_label": old_low, "high_label": old_high,
                }

    summary = f"{n_keep} keep, {n_replace} replace, {n_error} error"
    if n_rejected:
        summary += f", {n_rejected} rejected (direction-inverting renames)"
    print(f"\n{summary}")

    if args.max_changes is not None and n_replace > args.max_changes:
        sys.exit(
            f"Aborting: {n_replace} replacements exceeds --max-changes={args.max_changes}."
        )

    out_dims = dict(unchanged)  # empty if not --full
    out_dims.update(changed)

    payload = {
        "_meta": {
            "model": args.model,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "domain": domain,
            "num_total": len(dims),
            "num_changed": n_replace,
            "num_rejected": n_rejected,
            "num_errors": n_error,
            "mode": "full" if args.full else "sparse",
            "validation": (not args.no_validate),
        },
        "dimensions": out_dims,
    }

    out_path = args.domain_dir / "polished_labels.json"
    if args.write:
        tmp = out_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        tmp.replace(out_path)
        print(f"\nWrote {out_path}")
    else:
        print(f"\n(dry run — pass --write to save to {out_path})")


if __name__ == "__main__":
    main()
