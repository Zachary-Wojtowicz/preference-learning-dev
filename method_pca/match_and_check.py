#!/usr/bin/env python3
"""
match_and_check.py — Match duplicate directions, then sanity-check example overlap.

Step 1 — Geometric match:
  Compute pairwise |cosine similarity| between all direction vectors.
  Group directions whose |cos| > --cos-threshold into clusters.
  Each cluster = directions likely capturing the same underlying contrast.

Step 2 — Example overlap sanity check:
  For every pair of directions (within AND across clusters), compute
  Jaccard overlap of their top-K and bottom-K example sets (by row_index).
  High overlap → the two directions are interchangeable; they should merge.
  Low overlap → they are genuinely distinct even if similarly labeled.

Step 3 — LLM consensus label per cluster:
  For clusters with 2+ members, ask the LLM to pick one canonical label
  that best covers all members, and note what each member captures that
  the others don't.

Outputs:
  match_report.json  — clusters, pairwise cosines, overlap matrix, final labels
  match_report.md    — human-readable summary
"""

import argparse
import json
import os
import re
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

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


# ---------------------------------------------------------------------------
# Step 1 — geometric matching
# ---------------------------------------------------------------------------

def cosine_matrix(directions):
    """Returns (N, N) |cosine similarity| matrix."""
    vecs = np.array([d["direction_vector"] for d in directions], dtype=np.float64)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    normed = vecs / norms
    cos = normed @ normed.T
    return np.abs(cos)                 # |cos| — sign flip shouldn't matter


def cluster_by_cosine(directions, cos_mat, threshold):
    """
    Single-linkage clustering: merge two directions if |cos| > threshold.
    Returns list of clusters (each = list of direction indices).
    """
    n = len(directions)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            if cos_mat[i, j] > threshold:
                union(i, j)

    groups = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    return list(groups.values())


# ---------------------------------------------------------------------------
# Step 2 — example overlap
# ---------------------------------------------------------------------------

def example_ids(direction, top_k):
    pos = {ex["row_index"] for ex in direction["positive_examples"][:top_k]}
    neg = {ex["row_index"] for ex in direction["negative_examples"][:top_k]}
    return pos, neg


def jaccard(a, b):
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def overlap_matrix(directions, top_k):
    """
    Returns (N, N) dict-of-dicts with keys 'pos', 'neg', 'combined' Jaccard.
    """
    n = len(directions)
    pos_sets = []
    neg_sets = []
    for d in directions:
        p, ng = example_ids(d, top_k)
        pos_sets.append(p)
        neg_sets.append(ng)

    matrix = {}
    for i in range(n):
        for j in range(i, n):
            pos_j = jaccard(pos_sets[i], pos_sets[j])
            neg_j = jaccard(neg_sets[i], neg_sets[j])
            combined = jaccard(pos_sets[i] | neg_sets[i], pos_sets[j] | neg_sets[j])
            matrix[(i, j)] = {"pos": pos_j, "neg": neg_j, "combined": combined}
            matrix[(j, i)] = matrix[(i, j)]
    return matrix


# ---------------------------------------------------------------------------
# Step 3 — LLM consensus label
# ---------------------------------------------------------------------------

def compact(text, max_chars):
    text = " ".join(text.split())
    return text if len(text) <= max_chars else text[:max_chars - 3].rstrip() + "..."


def fmt_member(d, top_k, max_chars):
    pos = "; ".join(
        compact(ex.get("label") or ex.get("text", ""), max_chars)
        for ex in d["positive_examples"][:top_k]
    )
    neg = "; ".join(
        compact(ex.get("label") or ex.get("text", ""), max_chars)
        for ex in d["negative_examples"][:top_k]
    )
    return (
        f"  {d['id']} — current label: \"{d.get('axis_label', '?')}\"\n"
        f"    + examples: {pos}\n"
        f"    - examples: {neg}"
    )


def build_consensus_prompt(cluster_dirs, top_k, max_chars, domain_hint):
    members_text = "\n\n".join(fmt_member(d, top_k, max_chars) for d in cluster_dirs)
    cosines = []
    vecs = [np.array(d["direction_vector"]) for d in cluster_dirs]
    for i in range(len(vecs)):
        for j in range(i + 1, len(vecs)):
            c = float(abs(np.dot(vecs[i], vecs[j]) /
                         (np.linalg.norm(vecs[i]) * np.linalg.norm(vecs[j]) + 1e-10)))
            cosines.append(f"  {cluster_dirs[i]['id']} ↔ {cluster_dirs[j]['id']}: |cos|={c:.3f}")
    cos_text = "\n".join(cosines)

    return f"""\
These {len(cluster_dirs)} directions{" in " + domain_hint if domain_hint else ""} are \
geometrically similar (high cosine similarity) and likely capture the same underlying contrast.

Vector similarities:
{cos_text}

Members:
{members_text}

Your task: produce ONE canonical label that best covers all members.

Return JSON:
  "canonical_label"   : ≤6 words
  "positive_pole"     : 1-2 sentences for the high end
  "negative_pole"     : 1-2 sentences for the low end
  "best_representative" : id of the member direction that best exemplifies this label
  "member_notes"      : dict mapping each direction id to 1 sentence on what it
                        uniquely adds vs. the canonical label (or "fully covered")
  "should_merge"      : true if all members are interchangeable; false if they each
                        add unique signal worth keeping separately
Output JSON only."""


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def write_markdown(path, directions, clusters, overlap, consensus, top_k, cos_threshold):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Direction Match & Sanity Check", ""]

    # Cluster summary
    multi = [c for c in clusters if len(c) > 1]
    single = [c for c in clusters if len(c) == 1]
    lines += [
        f"- Total directions: {len(directions)}",
        f"- |cos| threshold: {cos_threshold}",
        f"- Clusters with 2+ members: {len(multi)}",
        f"- Singleton directions: {len(single)}",
        "",
    ]

    if multi:
        lines += ["## Matched clusters (duplicates / near-duplicates)", ""]
        for cluster in multi:
            c = consensus.get(tuple(sorted(cluster)), {})
            canon = c.get("canonical_label", "—")
            merge = c.get("should_merge")
            ids = [directions[i]["id"] for i in cluster]
            lines.append(f"### {canon}  {'[MERGE]' if merge else '[KEEP SEPARATE]'}")
            lines.append(f"- Members: {', '.join(ids)}")
            lines.append(f"- Best rep: {c.get('best_representative', '—')}")
            lines.append(f"- +pole: {c.get('positive_pole', '—')}")
            lines.append(f"- -pole: {c.get('negative_pole', '—')}")
            for mid, note in (c.get("member_notes") or {}).items():
                lines.append(f"  - {mid}: {note}")
            lines.append("")

    # Overlap sanity check — flag high-overlap pairs
    high_overlap = []
    n = len(directions)
    for i in range(n):
        for j in range(i + 1, n):
            ov = overlap.get((i, j), {})
            if ov.get("combined", 0) > 0.3:
                high_overlap.append((i, j, ov))

    if high_overlap:
        lines += ["## Example overlap warnings (combined Jaccard > 0.3)", ""]
        lines.append(f"{'Direction A':<15} {'Direction B':<15} {'pos_J':>6} {'neg_J':>6} {'all_J':>6}")
        lines.append("-" * 55)
        for i, j, ov in sorted(high_overlap, key=lambda x: -x[2]["combined"]):
            lines.append(
                f"{directions[i]['id']:<15} {directions[j]['id']:<15} "
                f"{ov['pos']:>6.3f} {ov['neg']:>6.3f} {ov['combined']:>6.3f}"
            )
        lines.append("")
    else:
        lines += ["## Example overlap", "", "✓ No direction pair shares more than 30% of examples.", ""]

    # Final direction list
    lines += ["## Final direction labels", ""]
    lines.append(f"{'ID':<12} {'EVR':>6}  {'Conf':<7}  Label")
    lines.append("-" * 75)

    # Build final label map: merged clusters use canonical label
    final_label = {}
    for cluster in clusters:
        if len(cluster) == 1:
            d = directions[cluster[0]]
            final_label[d["id"]] = d.get("axis_label", "?")
        else:
            key = tuple(sorted(cluster))
            c = consensus.get(key, {})
            rep = c.get("best_representative")
            should_merge = c.get("should_merge", False)
            for idx in cluster:
                d = directions[idx]
                if should_merge:
                    # All members get canonical label; mark non-reps as duplicates
                    if d["id"] == rep:
                        final_label[d["id"]] = c.get("canonical_label", d.get("axis_label", "?"))
                    else:
                        final_label[d["id"]] = f"[dup of {rep}] {c.get('canonical_label', '?')}"
                else:
                    final_label[d["id"]] = d.get("axis_label", "?")

    for d in directions:
        evr = d.get("explained_variance_ratio", 0)
        conf = d.get("confidence", "?")
        lbl = final_label.get(d["id"], d.get("axis_label", "?"))
        lines.append(f"{d['id']:<12} {evr:>5.2%}  {conf:<7}  {lbl}")

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    return final_label


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--labeled-json", required=True,
                   help="labeled_directions.json from label_directions.py")
    p.add_argument("--output-json")
    p.add_argument("--output-md")
    p.add_argument("--cos-threshold", type=float, default=0.6,
                   help="Abs cosine similarity threshold for geometric matching (default 0.6)")
    p.add_argument("--overlap-warn-threshold", type=float, default=0.3,
                   help="Jaccard overlap threshold for sanity-check warnings (default 0.3)")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--max-text-chars", type=int, default=120)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--api-key", default=None)
    p.add_argument("--max-retries", type=int, default=4)
    p.add_argument("--retry-delay", type=float, default=5.0)
    p.add_argument("--domain-hint", default="wine tasting notes")
    p.add_argument("--skip-llm", action="store_true",
                   help="Skip consensus LLM calls (just do geometric + overlap check)")
    return p.parse_args()


def main():
    args = parse_args()
    load_dotenv()

    data = json.loads(Path(args.labeled_json).read_text(encoding="utf-8"))
    directions = data["directions"]
    n = len(directions)
    print(f"Loaded {n} labeled directions.", flush=True)

    out_json = Path(args.output_json) if args.output_json else \
        Path(args.labeled_json).parent / "match_report.json"
    out_md = Path(args.output_md) if args.output_md else \
        Path(args.labeled_json).parent / "match_report.md"

    # --- Step 1: cosine matrix + clustering ---
    print("Step 1: computing cosine similarity matrix...", flush=True)
    cos_mat = cosine_matrix(directions)
    clusters = cluster_by_cosine(directions, cos_mat, args.cos_threshold)
    multi = [c for c in clusters if len(c) > 1]
    print(f"  {len(multi)} clusters with ≥2 members "
          f"(threshold |cos| > {args.cos_threshold})", flush=True)
    for cluster in multi:
        ids = [directions[i]["id"] for i in cluster]
        print(f"    {ids}", flush=True)

    # Top pairwise cosines (excluding self)
    top_pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            top_pairs.append((cos_mat[i, j], i, j))
    top_pairs.sort(reverse=True)

    # --- Step 2: example overlap ---
    print("Step 2: computing example overlap...", flush=True)
    overlap = overlap_matrix(directions, args.top_k)
    high = [(i, j, overlap[(i, j)]) for i in range(n) for j in range(i + 1, n)
            if overlap[(i, j)]["combined"] > args.overlap_warn_threshold]
    high.sort(key=lambda x: -x[2]["combined"])
    if high:
        print(f"  {len(high)} pairs with combined Jaccard > {args.overlap_warn_threshold}:")
        for i, j, ov in high[:10]:
            print(f"    {directions[i]['id']} ↔ {directions[j]['id']}  "
                  f"pos={ov['pos']:.2f} neg={ov['neg']:.2f} all={ov['combined']:.2f}", flush=True)
    else:
        print(f"  No pairs exceed overlap threshold {args.overlap_warn_threshold} ✓", flush=True)

    # --- Step 3: LLM consensus labels for multi-member clusters ---
    consensus = {}  # tuple(sorted(cluster)) -> parsed result
    if not args.skip_llm and multi:
        api_key = args.api_key or os.environ.get("GOOGLE_API_KEY", "")
        if not api_key:
            print("WARNING: no API key found; skipping LLM consensus.", flush=True)
        else:
            client = make_client(api_key)
            print("Step 3: LLM consensus labels for matched clusters...", flush=True)
            for cluster in multi:
                key = tuple(sorted(cluster))
                cluster_dirs = [directions[i] for i in cluster]
                ids = [d["id"] for d in cluster_dirs]
                print(f"  Cluster {ids}...", flush=True)
                prompt = build_consensus_prompt(
                    cluster_dirs, args.top_k, args.max_text_chars, args.domain_hint
                )
                raw = chat(client, args.model, prompt, args.max_retries, args.retry_delay)
                try:
                    parsed = parse_json_blob(raw)
                except Exception as exc:
                    print(f"    WARNING: parse failed: {exc}", flush=True)
                    parsed = {}
                consensus[key] = parsed
                merge = parsed.get("should_merge")
                print(f"    -> '{parsed.get('canonical_label', '?')}' "
                      f"should_merge={merge}", flush=True)

    # --- Serialize ---
    # Convert (i,j) tuple keys to strings for JSON
    overlap_serializable = {
        f"{i},{j}": {
            "id_a": directions[i]["id"],
            "id_b": directions[j]["id"],
            **v,
        }
        for (i, j), v in overlap.items() if i <= j
    }

    # Top-20 cosine pairs
    top_cos_serializable = [
        {
            "id_a": directions[i]["id"],
            "id_b": directions[j]["id"],
            "abs_cosine": float(c),
        }
        for c, i, j in top_pairs[:20]
    ]

    consensus_serializable = {
        str(list(k)): v for k, v in consensus.items()
    }

    report = {
        "cos_threshold": args.cos_threshold,
        "overlap_warn_threshold": args.overlap_warn_threshold,
        "clusters": [[directions[i]["id"] for i in c] for c in clusters],
        "multi_member_clusters": [[directions[i]["id"] for i in c] for c in multi],
        "top_cosine_pairs": top_cos_serializable,
        "overlap_high_pairs": [
            {
                "id_a": directions[i]["id"],
                "id_b": directions[j]["id"],
                **ov,
            }
            for i, j, ov in high
        ],
        "overlap_matrix": overlap_serializable,
        "consensus": consensus_serializable,
    }

    write_json(out_json, report)
    final_labels = write_markdown(
        out_md, directions, clusters, overlap, consensus,
        args.top_k, args.cos_threshold,
    )

    print(json.dumps({
        "output_json": str(out_json),
        "output_md": str(out_md),
        "total_directions": n,
        "multi_member_clusters": len(multi),
        "high_overlap_pairs": len(high),
    }, indent=2))


if __name__ == "__main__":
    main()
