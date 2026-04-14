#!/usr/bin/env python3
"""Choice-grounded dimension discovery pipeline.

Samples pairwise contrasts from a dataset, elicits reasons someone might
choose one over the other, clusters those reasons, then distills them
into a compact set of preference dimensions.
"""

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Reuse shared utilities from method_llm_gen
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from method_llm_gen.pipeline import (
    load_json,
    write_json,
    load_options,
    make_client_or_pool,
    llm_call,
    llm_call_json,
    parse_json_response,
    run_jobs,
    ClientPool,
)

DEFAULT_SEED = 42
DEFAULT_TIMEOUT = 45
DEFAULT_MAX_RETRIES = 3


def llm_call_temp(client, model, prompt, timeout, retries, temperature=0.7):
    """Like llm_call but with configurable temperature and full pool/retry logic."""
    import time as _time

    if not model:
        raise ValueError("Missing --model")
    is_pool = isinstance(client, ClientPool)
    pool_size = client.size if is_pool else 1
    max_attempts = max(retries, pool_size)
    last_err = None
    for attempt in range(1, max_attempts + 1):
        resolved = client.next() if is_pool else client
        try:
            resp = resolved.chat.completions.create(
                model=model, temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
                timeout=timeout,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            last_err = e
            is_conn = "Connection" in type(e).__name__
            if attempt < max_attempts:
                if not is_conn:
                    _time.sleep(min(attempt, 3))
    raise last_err


# ===================================================================
# Stage 1 — Sample Diverse Pairs
# ===================================================================

def load_embeddings(parquet_path, id_column, embedding_column):
    """Load embeddings from a parquet file, returning {option_id: np.array}."""
    import pyarrow.parquet as pq

    table = pq.read_table(parquet_path)
    rows = table.to_pylist()
    embeddings = {}
    for row in rows:
        oid = str(row[id_column]).strip()
        vec = row[embedding_column]
        if isinstance(vec, list):
            embeddings[oid] = np.array(vec, dtype=np.float64)
    return embeddings


def sample_diverse_pairs(embeddings, num_pairs, num_strata, seed):
    """Sample pairs stratified by cosine distance."""
    ids = sorted(embeddings.keys())
    n = len(ids)
    if n < 2:
        raise ValueError(f"Need at least 2 options, got {n}")

    # Build embedding matrix and center
    matrix = np.array([embeddings[oid] for oid in ids])
    matrix -= matrix.mean(axis=0)

    # Normalize for cosine distance
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normed = matrix / norms

    # Cosine distance = 1 - cosine_similarity
    sim = normed @ normed.T
    np.fill_diagonal(sim, 1.0)
    dist = 1.0 - sim

    # Collect all unique pairs with their distances
    all_pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            all_pairs.append((ids[i], ids[j], dist[i, j]))

    all_pairs.sort(key=lambda x: x[2])

    # Stratify
    stratum_size = len(all_pairs) // num_strata
    strata = []
    for s in range(num_strata):
        start = s * stratum_size
        end = len(all_pairs) if s == num_strata - 1 else (s + 1) * stratum_size
        strata.append(all_pairs[start:end])

    stratum_labels = ["near", "medium", "far"] if num_strata == 3 else [f"stratum_{i}" for i in range(num_strata)]

    # Sample from each stratum
    rng = np.random.RandomState(seed)
    per_stratum = num_pairs // num_strata
    sampled = []
    for s_idx, stratum in enumerate(strata):
        count = per_stratum if s_idx < num_strata - 1 else num_pairs - len(sampled)
        count = min(count, len(stratum))
        indices = rng.choice(len(stratum), size=count, replace=False)
        for idx in indices:
            a_id, b_id, d = stratum[idx]
            sampled.append({
                "pair_id": len(sampled),
                "option_a_id": a_id,
                "option_b_id": b_id,
                "distance_stratum": stratum_labels[s_idx] if s_idx < len(stratum_labels) else f"stratum_{s_idx}",
                "cosine_distance": round(float(d), 6),
            })

    return sampled


# ===================================================================
# Stage 2 — Elicit Reasons Per Pair
# ===================================================================

REASON_PROMPT_TEMPLATE = """\
Here are two {domain_items}. Imagine a large, diverse group of people each
choosing which one they prefer. Different people will choose differently —
and for different reasons.

{DOMAIN_ITEM} A:
{option_a_text}

{DOMAIN_ITEM} B:
{option_b_text}

List {reasons_per_side} distinct reasons someone might choose {DOMAIN_ITEM} A over B, and
{reasons_per_side} distinct reasons someone might choose B over A. Each reason should reflect
a genuine preference difference — something some people would care about and
others wouldn't, or something different people would weigh in opposite
directions.

Be specific and concrete. Avoid generic quality judgments ("it's better").
Focus on *what kind of person* would have this reason, and *what feature
of the option* drives it.

Format (plain text, not JSON):

REASONS TO CHOOSE A:
1. [reason]
2. [reason]
3. [reason]
4. [reason]
5. [reason]

REASONS TO CHOOSE B:
1. [reason]
2. [reason]
3. [reason]
4. [reason]
5. [reason]"""


def parse_reasons(response_text, pair, reasons_per_side):
    """Parse the LLM response into individual reason dicts."""
    reasons = []

    # Split into A and B sections
    parts_a = re.split(r"REASONS TO CHOOSE B:", response_text, flags=re.IGNORECASE)
    section_a = ""
    section_b = ""
    if len(parts_a) >= 2:
        header_split = re.split(r"REASONS TO CHOOSE A:", parts_a[0], flags=re.IGNORECASE)
        section_a = header_split[-1]
        section_b = parts_a[1]
    else:
        # Try splitting on just the header
        header_split = re.split(r"REASONS TO CHOOSE A:", response_text, flags=re.IGNORECASE)
        if len(header_split) >= 2:
            section_a = header_split[1]

    def extract_numbered(text):
        items = re.findall(r"\d+\.\s*(.+?)(?=\n\d+\.|\Z)", text, re.DOTALL)
        return [item.strip() for item in items if item.strip()]

    for reason_text in extract_numbered(section_a):
        reasons.append({
            "pair_id": pair["pair_id"],
            "direction": "A",
            "option_a_id": pair["option_a_id"],
            "option_b_id": pair["option_b_id"],
            "reason_text": reason_text,
        })

    for reason_text in extract_numbered(section_b):
        reasons.append({
            "pair_id": pair["pair_id"],
            "direction": "B",
            "option_a_id": pair["option_a_id"],
            "option_b_id": pair["option_b_id"],
            "reason_text": reason_text,
        })

    return reasons


def elicit_reasons(pairs, options_lookup, config, client, model, max_workers, reasons_per_side):
    """Elicit preference reasons for all pairs."""
    domain_item = config.get("domain_item", config.get("domain", "option"))
    domain_items = domain_item + "s"
    timeout = int(config.get("request_timeout_seconds", DEFAULT_TIMEOUT))
    retries = int(config.get("max_retries", DEFAULT_MAX_RETRIES))

    def run(pair):
        opt_a = options_lookup[pair["option_a_id"]]
        opt_b = options_lookup[pair["option_b_id"]]

        prompt = REASON_PROMPT_TEMPLATE.format(
            domain_items=domain_items,
            DOMAIN_ITEM=domain_item.capitalize(),
            option_a_text=opt_a.option_text,
            option_b_text=opt_b.option_text,
            reasons_per_side=reasons_per_side,
        )

        response_text = llm_call_temp(client, model, prompt, timeout, retries, temperature=0.7)
        return parse_reasons(response_text, pair, reasons_per_side)

    results = run_jobs(pairs, run, max_workers, "elicit-reasons")

    all_reasons = []
    for reason_list in results:
        if reason_list:
            all_reasons.extend(reason_list)

    # Assign reason_ids
    for i, reason in enumerate(all_reasons):
        reason["reason_id"] = i

    return all_reasons


# ===================================================================
# Stage 3 — Embed and Cluster Reasons
# ===================================================================

def embed_texts(texts, client, model, embedding_client=None, batch_size=100):
    """Embed a list of texts using the OpenAI embeddings API."""
    emb_client = embedding_client if embedding_client is not None else client
    is_pool = isinstance(emb_client, ClientPool)
    all_embeddings = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        resolved = emb_client.next() if is_pool else emb_client
        resp = resolved.embeddings.create(model=model, input=batch)
        batch_embeddings = [item.embedding for item in resp.data]
        all_embeddings.extend(batch_embeddings)
        if start + batch_size < len(texts):
            print(f"[embed] {start + batch_size}/{len(texts)}", flush=True)
    print(f"[embed] {len(texts)}/{len(texts)}", flush=True)
    return np.array(all_embeddings)


def cluster_reasons(reasons, client, embedding_model, num_clusters, distance_threshold, embedding_client=None):
    """Embed reason texts, cluster them, and return cluster representatives."""
    from sklearn.cluster import AgglomerativeClustering

    texts = [r["reason_text"] for r in reasons]
    print(f"[cluster] Embedding {len(texts)} reasons...", flush=True)
    embeddings = embed_texts(texts, client, embedding_model, embedding_client=embedding_client)

    # Normalize to unit length
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normed = embeddings / norms

    # Agglomerative clustering
    if num_clusters:
        clustering = AgglomerativeClustering(
            n_clusters=num_clusters,
            metric="cosine",
            linkage="average",
        )
    else:
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=distance_threshold,
            metric="cosine",
            linkage="average",
        )

    labels = clustering.fit_predict(normed)
    n_clusters = len(set(labels))
    print(f"[cluster] Found {n_clusters} clusters", flush=True)

    # Build cluster info
    clusters = {}
    for idx, label in enumerate(labels):
        label = int(label)
        clusters.setdefault(label, []).append(idx)

    result = []
    for cluster_id, member_indices in sorted(clusters.items()):
        # Find representative (closest to centroid)
        member_embeddings = normed[member_indices]
        centroid = member_embeddings.mean(axis=0)
        centroid_norm = np.linalg.norm(centroid)
        if centroid_norm > 0:
            centroid /= centroid_norm
        distances = 1.0 - member_embeddings @ centroid
        rep_local_idx = int(np.argmin(distances))
        rep_idx = member_indices[rep_local_idx]

        contributing_pairs = sorted(set(reasons[i]["pair_id"] for i in member_indices))

        result.append({
            "cluster_id": cluster_id,
            "representative_reason": reasons[rep_idx]["reason_text"],
            "cluster_size": len(member_indices),
            "member_reason_ids": [reasons[i]["reason_id"] for i in member_indices],
            "contributing_pair_ids": contributing_pairs,
        })

    # Sort by cluster_size descending
    result.sort(key=lambda c: -c["cluster_size"])

    return result, normed


# ===================================================================
# Stage 4 — Condense into Dimensions
# ===================================================================

CONDENSE_PROMPT_TEMPLATE = """\
You are analyzing reasons people give for choosing between {domain_items}.

Below is a deduplicated list of reasons people cited for preferring one option
over another. The number in parentheses indicates how many times this theme
appeared across {num_pairs} different choice pairs — higher counts indicate
more pervasive preference axes.

Many of these reasons are two sides of the same underlying preference dimension.
Your task is to identify the {K} most important underlying preference dimensions
that explain these reasons.

Each dimension should:
- Be a BIPOLAR AXIS — both ends represent legitimate preferences that real
  people hold (not a quality scale where one end is objectively better)
- SUBSUME as many of the listed reasons as possible
- Be DISTINCT from the other dimensions you identify
- Reflect genuine DISAGREEMENT — something that different people weigh
  in opposite directions, not a universal quality criterion

For each dimension, cite which reason numbers it subsumes (this verifies
coverage and coherence).

REASONS (sorted by frequency):
{reason_list}

Respond with valid JSON only — no prose before or after, no markdown fences.

{schema}"""

CONDENSE_SCHEMA = """{
  "domain": string,
  "choice_context": string,
  "reasoning": string,
  "dimensions": [
    {
      "id": integer,
      "name": string,
      "low_pole": {
        "label": string,
        "description": string,
        "typical_person": string
      },
      "high_pole": {
        "label": string,
        "description": string,
        "typical_person": string
      },
      "example_contrast": {
        "low_option": string,
        "high_option": string
      },
      "articulability": "explicit" | "partially_explicit" | "implicit",
      "estimated_variance": "mostly_between_person" | "mostly_between_option" | "both",
      "scoring_guidance": string,
      "subsumed_reasons": [integer]
    }
  ],
  "redundancy_check": [
    {
      "dimension_ids": [integer, integer],
      "correlation_note": string,
      "disentanglement_suggestion": string
    }
  ]
}"""


def condense_dimensions(clusters, config, client, model, num_dimensions):
    """Distill cluster representatives into K bipolar preference dimensions."""
    domain_item = config.get("domain_item", config.get("domain", "option"))
    domain_items = domain_item + "s"
    timeout = int(config.get("request_timeout_seconds", DEFAULT_TIMEOUT))
    retries = int(config.get("max_retries", DEFAULT_MAX_RETRIES))

    # Build numbered reason list
    reason_lines = []
    for i, cluster in enumerate(clusters, start=1):
        reason_lines.append(f"{i}. [count={cluster['cluster_size']}] {cluster['representative_reason']}")

    num_pairs = len(set(pid for c in clusters for pid in c["contributing_pair_ids"]))

    prompt = CONDENSE_PROMPT_TEMPLATE.format(
        domain_items=domain_items,
        num_pairs=num_pairs,
        K=num_dimensions,
        reason_list="\n".join(reason_lines),
        schema=CONDENSE_SCHEMA,
    )

    # Use temperature=0 for best condensation
    result = llm_call_json(client, model, prompt, timeout, retries)

    # Ensure schema fields are present
    result.setdefault("domain", config.get("domain", ""))
    result.setdefault("choice_context", config.get("choice_context", ""))
    result.setdefault("reasoning", "")
    result.setdefault("dimensions", [])
    result.setdefault("redundancy_check", [])

    # Ensure each dimension has an id
    for i, dim in enumerate(result["dimensions"], start=1):
        dim.setdefault("id", i)

    return result


# ===================================================================
# Stage 5 — Validate Coverage
# ===================================================================

def validate_coverage(reasons, reason_embeddings, dimensions, client, embedding_model, threshold=0.4, embedding_client=None):
    """Check that dimensions collectively account for the reason pool."""

    # Embed dimension pole descriptions
    pole_texts = []
    dim_pole_map = []  # (dim_idx, pole: "low"|"high")
    for i, dim in enumerate(dimensions):
        pole_texts.append(dim.get("low_pole", {}).get("description", dim.get("name", "")))
        dim_pole_map.append((i, "low"))
        pole_texts.append(dim.get("high_pole", {}).get("description", dim.get("name", "")))
        dim_pole_map.append((i, "high"))

    print(f"[coverage] Embedding {len(pole_texts)} dimension pole descriptions...", flush=True)
    pole_embeddings = embed_texts(pole_texts, client, embedding_model, embedding_client=embedding_client)

    # Normalize
    norms = np.linalg.norm(pole_embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    pole_normed = pole_embeddings / norms

    # Compute similarity of each reason to each pole
    # reason_embeddings is already normalized
    sim_matrix = reason_embeddings @ pole_normed.T  # (num_reasons, num_poles)

    # For each reason, find best-matching dimension
    assignments = []
    for r_idx in range(len(reasons)):
        best_sim = -1.0
        best_dim_idx = 0
        best_pole = "low"
        for p_idx in range(len(pole_texts)):
            if sim_matrix[r_idx, p_idx] > best_sim:
                best_sim = sim_matrix[r_idx, p_idx]
                best_dim_idx, best_pole = dim_pole_map[p_idx]
                best_dim_idx_val = best_dim_idx
                best_pole_val = best_pole
        assignments.append({
            "reason_id": reasons[r_idx]["reason_id"],
            "reason_text": reasons[r_idx]["reason_text"],
            "best_dim_idx": best_dim_idx_val,
            "best_dim_name": dimensions[best_dim_idx_val].get("name", ""),
            "best_pole": best_pole_val,
            "best_similarity": float(best_sim),
        })

    # Coverage rate
    covered = [a for a in assignments if a["best_similarity"] >= threshold]
    coverage_rate = len(covered) / len(assignments) if assignments else 0.0

    # Orphan reasons (below threshold)
    orphans = sorted(
        [a for a in assignments if a["best_similarity"] < threshold],
        key=lambda a: -a["best_similarity"],
    )

    # Dimension load
    dim_load = {}
    dim_pole_counts = {}
    for a in assignments:
        d_idx = a["best_dim_idx"]
        dim_load[d_idx] = dim_load.get(d_idx, 0) + 1
        key = (d_idx, a["best_pole"])
        dim_pole_counts[key] = dim_pole_counts.get(key, 0) + 1

    dimension_stats = []
    for i, dim in enumerate(dimensions):
        total = dim_load.get(i, 0)
        low_count = dim_pole_counts.get((i, "low"), 0)
        high_count = dim_pole_counts.get((i, "high"), 0)
        dimension_stats.append({
            "dimension_id": dim.get("id", i + 1),
            "dimension_name": dim.get("name", ""),
            "total_reasons_assigned": total,
            "low_pole_count": low_count,
            "high_pole_count": high_count,
            "low_pole_fraction": round(low_count / total, 3) if total > 0 else 0.0,
            "high_pole_fraction": round(high_count / total, 3) if total > 0 else 0.0,
        })

    report = {
        "total_reasons": len(reasons),
        "coverage_threshold": threshold,
        "covered_count": len(covered),
        "coverage_rate": round(coverage_rate, 4),
        "orphan_count": len(orphans),
        "top_orphans": orphans[:10],
        "dimension_stats": dimension_stats,
    }

    return report


def format_coverage_report_md(report):
    """Format coverage report as human-readable markdown."""
    lines = [
        "# Coverage Report",
        "",
        f"**Total reasons:** {report['total_reasons']}",
        f"**Coverage threshold:** {report['coverage_threshold']}",
        f"**Covered:** {report['covered_count']} ({report['coverage_rate']:.1%})",
        f"**Orphans:** {report['orphan_count']}",
        "",
        "## Dimension Load",
        "",
        "| Dim | Name | Assigned | Low % | High % |",
        "| --- | ---- | -------: | ----: | -----: |",
    ]
    for ds in report["dimension_stats"]:
        lines.append(
            f"| {ds['dimension_id']} | {ds['dimension_name']} | "
            f"{ds['total_reasons_assigned']} | "
            f"{ds['low_pole_fraction']:.1%} | {ds['high_pole_fraction']:.1%} |"
        )

    if report["top_orphans"]:
        lines += [
            "",
            "## Top Orphan Reasons",
            "",
        ]
        for orphan in report["top_orphans"]:
            lines.append(
                f"- (sim={orphan['best_similarity']:.3f}, nearest: {orphan['best_dim_name']}) "
                f"{orphan['reason_text']}"
            )

    return "\n".join(lines) + "\n"


# ===================================================================
# Summary
# ===================================================================

def build_pipeline_summary(args, config, pairs, reasons, clusters, dimensions_data, coverage_report, output_dir):
    """Build an overall pipeline summary."""
    dims = dimensions_data.get("dimensions", [])
    lines = [
        f"# {config.get('domain', '').title()} — Choice-Grounded Dimension Discovery",
        "",
        f"**Choice context:** {config.get('choice_context', '')}",
        "",
        "## Parameters",
        "",
        f"- Pairs sampled: {len(pairs)}",
        f"- Reasons per side: {args.reasons_per_side}",
        f"- Total raw reasons: {len(reasons)}",
        f"- Reason clusters: {len(clusters)}",
        f"- Dimensions requested: {args.num_dimensions}",
        f"- Dimensions produced: {len(dims)}",
        f"- Seed: {args.seed}",
        f"- Model: {args.model}",
        "",
        "## Dimensions",
        "",
    ]
    for dim in dims:
        lines.append(
            f"**{dim.get('id', '?')}. {dim.get('name', '')}**: "
            f"{dim.get('low_pole', {}).get('label', '')} ↔ "
            f"{dim.get('high_pole', {}).get('label', '')}"
        )
        if dim.get("subsumed_reasons"):
            lines.append(f"   Subsumed reasons: {dim['subsumed_reasons']}")
        lines.append("")

    if coverage_report:
        lines += [
            "## Coverage",
            "",
            f"- Coverage rate: {coverage_report['coverage_rate']:.1%}",
            f"- Orphan reasons: {coverage_report['orphan_count']}",
            "",
        ]

    path = output_dir / "summary.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ===================================================================
# CLI
# ===================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Choice-grounded dimension discovery pipeline",
    )
    parser.add_argument("--config", required=True, help="Path to config JSON")
    parser.add_argument("--api-provider", choices=["local", "openai", "anthropic"], default="local")
    parser.add_argument("--base-url", help="API endpoint URL(s)")
    parser.add_argument("--model", required=True, help="LLM model name")
    parser.add_argument("--api-key", help="API key")
    parser.add_argument("--embedding-model", help="Embedding model (defaults to text-embedding-3-small)")
    parser.add_argument("--embedding-base-url", help="Separate API endpoint for embeddings (optional)")
    parser.add_argument("--embeddings-parquet", required=True, help="Path to parquet with option embeddings")
    parser.add_argument("--embedding-column", default="embedding", help="Column name for embeddings")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--num-pairs", type=int, default=100)
    parser.add_argument("--strata", type=int, default=3)
    parser.add_argument("--reasons-per-side", type=int, default=5)
    parser.add_argument("--num-dimensions", "-K", type=int, default=10)
    parser.add_argument("--num-clusters", type=int, default=None, help="Number of reason clusters (default: auto)")
    parser.add_argument("--cluster-distance-threshold", type=float, default=0.3)
    parser.add_argument("--coverage-threshold", type=float, default=0.4)
    parser.add_argument("--max-workers", type=int, default=8)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser.parse_args()


def main():
    args = parse_args()
    config = load_json(Path(args.config))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    embedding_model = args.embedding_model or "text-embedding-3-small"

    # Load options for text rendering
    options = load_options(config)
    options_lookup = {opt.option_id: opt for opt in options}

    # Build client
    client = make_client_or_pool(args.base_url, args.api_key, args.api_provider)
    embedding_client = (
        make_client_or_pool(args.embedding_base_url, args.api_key, args.api_provider)
        if args.embedding_base_url
        else None
    )

    # ------------------------------------------------------------------
    # Stage 1 — Sample Diverse Pairs
    # ------------------------------------------------------------------
    pairs_path = output_dir / "sampled_pairs.json"
    if pairs_path.exists():
        print(f"[stage-1] Loading existing pairs from {pairs_path}", flush=True)
        pairs = load_json(pairs_path)
    else:
        print("[stage-1] Sampling diverse pairs...", flush=True)
        embeddings = load_embeddings(
            args.embeddings_parquet,
            config["id_column"],
            args.embedding_column,
        )
        # Filter to only options we loaded
        option_ids = set(opt.option_id for opt in options)
        embeddings = {k: v for k, v in embeddings.items() if k in option_ids}
        print(f"[stage-1] {len(embeddings)} options with embeddings", flush=True)

        pairs = sample_diverse_pairs(embeddings, args.num_pairs, args.strata, args.seed)
        write_json(pairs_path, pairs)
        print(f"[stage-1] Sampled {len(pairs)} pairs -> {pairs_path}", flush=True)

    # ------------------------------------------------------------------
    # Stage 2 — Elicit Reasons Per Pair
    # ------------------------------------------------------------------
    reasons_path = output_dir / "raw_reasons.json"
    if reasons_path.exists():
        print(f"[stage-2] Loading existing reasons from {reasons_path}", flush=True)
        reasons = load_json(reasons_path)
    else:
        print(f"[stage-2] Eliciting reasons for {len(pairs)} pairs...", flush=True)
        reasons = elicit_reasons(
            pairs, options_lookup, config, client, args.model,
            args.max_workers, args.reasons_per_side,
        )
        write_json(reasons_path, reasons)
        print(f"[stage-2] Elicited {len(reasons)} reasons -> {reasons_path}", flush=True)

    # ------------------------------------------------------------------
    # Stage 3 — Embed and Cluster Reasons
    # ------------------------------------------------------------------
    clusters_path = output_dir / "reason_clusters.json"
    if clusters_path.exists():
        print(f"[stage-3] Loading existing clusters from {clusters_path}", flush=True)
        clusters = load_json(clusters_path)
        # We still need reason embeddings for stage 5, so embed if needed
        reason_embeddings = None
    else:
        print(f"[stage-3] Clustering {len(reasons)} reasons...", flush=True)
        clusters, reason_embeddings = cluster_reasons(
            reasons, client, embedding_model,
            args.num_clusters, args.cluster_distance_threshold,
            embedding_client=embedding_client,
        )
        write_json(clusters_path, clusters)
        print(f"[stage-3] {len(clusters)} clusters -> {clusters_path}", flush=True)

    # ------------------------------------------------------------------
    # Stage 4 — Condense into Dimensions
    # ------------------------------------------------------------------
    dims_path = output_dir / "dimensions.json"
    if dims_path.exists():
        print(f"[stage-4] Loading existing dimensions from {dims_path}", flush=True)
        dimensions_data = load_json(dims_path)
    else:
        print(f"[stage-4] Condensing {len(clusters)} clusters into {args.num_dimensions} dimensions...", flush=True)
        dimensions_data = condense_dimensions(
            clusters, config, client, args.model, args.num_dimensions,
        )
        write_json(dims_path, dimensions_data)
        print(f"[stage-4] {len(dimensions_data.get('dimensions', []))} dimensions -> {dims_path}", flush=True)

    # ------------------------------------------------------------------
    # Stage 5 — Validate Coverage
    # ------------------------------------------------------------------
    coverage_path = output_dir / "coverage_report.json"
    if coverage_path.exists():
        print(f"[stage-5] Loading existing coverage report from {coverage_path}", flush=True)
        coverage_report = load_json(coverage_path)
    else:
        print("[stage-5] Validating coverage...", flush=True)
        # Need reason embeddings
        if reason_embeddings is None:
            texts = [r["reason_text"] for r in reasons]
            print(f"[stage-5] Re-embedding {len(texts)} reasons for coverage check...", flush=True)
            reason_embeddings = embed_texts(texts, client, embedding_model, embedding_client=embedding_client)
            norms = np.linalg.norm(reason_embeddings, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            reason_embeddings = reason_embeddings / norms

        coverage_report = validate_coverage(
            reasons, reason_embeddings,
            dimensions_data.get("dimensions", []),
            client, embedding_model,
            threshold=args.coverage_threshold,
            embedding_client=embedding_client,
        )
        write_json(coverage_path, coverage_report)

        md_path = output_dir / "coverage_report.md"
        md_path.write_text(format_coverage_report_md(coverage_report), encoding="utf-8")
        print(f"[stage-5] Coverage: {coverage_report['coverage_rate']:.1%} -> {coverage_path}", flush=True)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    build_pipeline_summary(args, config, pairs, reasons, clusters, dimensions_data, coverage_report, output_dir)
    print(f"[done] All outputs in {output_dir}", flush=True)


if __name__ == "__main__":
    main()
