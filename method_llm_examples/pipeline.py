#!/usr/bin/env python3
"""Choice-grounded dimension discovery pipeline.

Samples pairwise contrasts from a dataset, elicits reasons someone might
choose one over the other, deduplicates those reasons, then distills them
into a compact set of preference dimensions.
"""

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
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

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
DEFAULT_REASON_PROMPT = PROMPTS_DIR / "reason_elicit.txt"
DEFAULT_DEDUP_PROMPT = PROMPTS_DIR / "reason_dedup.txt"
DEFAULT_CONDENSE_PROMPT = PROMPTS_DIR / "dimension_condense.txt"


def load_prompt(path):
    """Load a prompt template from a text file."""
    return Path(path).read_text(encoding="utf-8").rstrip("\n")


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
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
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

# Reason elicitation prompt: loaded from file (see prompts/ directory).
# Variants: reason_elicit.txt (default), reason_elicit_values.txt,
#           reason_elicit_persona.txt, reason_elicit_mltraining.txt


def parse_reasons(response_text, pair, reasons_per_side):
    """Parse the LLM response into individual reason dicts."""
    # Strip <think>...</think> blocks (Qwen3 reasoning mode)
    response_text = re.sub(r"<think>.*?</think>", "", response_text, flags=re.DOTALL).strip()

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


def elicit_reasons(pairs, options_lookup, config, client, model, max_workers, reasons_per_side,
                   reason_prompt_template=None):
    """Elicit preference reasons for all pairs."""
    if reason_prompt_template is None:
        reason_prompt_template = load_prompt(DEFAULT_REASON_PROMPT)
    domain_item = config.get("domain_item", config.get("domain", "option"))
    domain_items = domain_item + "s"
    timeout = int(config.get("request_timeout_seconds", DEFAULT_TIMEOUT))
    retries = int(config.get("max_retries", DEFAULT_MAX_RETRIES))

    def run(pair):
        opt_a = options_lookup[pair["option_a_id"]]
        opt_b = options_lookup[pair["option_b_id"]]

        prompt = reason_prompt_template.format(
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
# Stage 3 — Deduplicate Reasons
# ===================================================================

# --- Method A: LLM-based deduplication ---

def strip_reason_boilerplate(text):
    """Strip bold headers and formulaic framing from a reason string.

    Raw reasons often look like:
      **Preference for X**: Someone who enjoys intense action might prefer...
    We want just the core content.
    """
    # Strip **bold header**: prefix
    text = re.sub(r"^\*\*[^*]+\*\*:?\s*", "", text.strip())
    # Truncate to first sentence or 150 chars, whichever is shorter
    sentence_end = re.search(r"[.!?]\s", text)
    if sentence_end and sentence_end.start() < 150:
        text = text[:sentence_end.start() + 1]
    elif len(text) > 150:
        text = text[:147].rstrip() + "..."
    return text.strip()


# Dedup prompt: loaded from file (see prompts/reason_dedup.txt).


def _chunk_reason_lines(reason_lines, domain_item, num_themes, dedup_prompt_template, max_prompt_tokens=8000):
    """Split reason_lines into chunks whose prompts fit within max_prompt_tokens."""
    template_overhead = len(dedup_prompt_template.format(
        N=9999, domain_item=domain_item, target_themes=num_themes, reason_list="",
    )) // 4 + 50
    chunks = []
    current_chunk = []
    current_tokens = 0
    for line in reason_lines:
        line_tokens = len(line) // 4 + 1
        if current_chunk and current_tokens + line_tokens + template_overhead > max_prompt_tokens:
            chunks.append(current_chunk)
            current_chunk = []
            current_tokens = 0
        current_chunk.append(line)
        current_tokens += line_tokens
    if current_chunk:
        chunks.append(current_chunk)
    return chunks


def dedup_reasons_llm(reasons, config, client, model, num_themes, dedup_prompt_template=None):
    """Deduplicate reasons using an LLM call. Returns list in cluster format."""
    if dedup_prompt_template is None:
        dedup_prompt_template = load_prompt(DEFAULT_DEDUP_PROMPT)
    domain_item = config.get("domain_item", config.get("domain", "option"))
    timeout = int(config.get("request_timeout_seconds", DEFAULT_TIMEOUT)) * 10
    retries = int(config.get("max_retries", DEFAULT_MAX_RETRIES))

    reason_lines = []
    for r in reasons:
        stripped = strip_reason_boilerplate(r["reason_text"])
        reason_lines.append(f"{r['reason_id']}. {stripped}")

    chunks = _chunk_reason_lines(reason_lines, domain_item, num_themes, dedup_prompt_template)

    per_batch_themes = 20

    def _run_chunk(ci, chunk):
        prompt = dedup_prompt_template.format(
            N=len(chunk),
            domain_item=domain_item,
            target_themes=per_batch_themes,
            reason_list="\n".join(chunk),
        )
        label = f"batch {ci+1}/{len(chunks)}" if len(chunks) > 1 else "all"
        print(f"[dedup-llm] Sending {len(chunk)} reasons ({label}) "
              f"(prompt ~{len(prompt) // 4} tokens)...", flush=True)
        import json as _json
        import time as _t
        for attempt in range(3):
            try:
                return llm_call_json(client, model, prompt, timeout, retries, max_tokens=4096)
            except _json.JSONDecodeError as e:
                print(f"[dedup-llm] Batch {ci+1} JSON parse error (skipping): {e}", flush=True)
                return {"themes": []}
            except Exception as e:
                if attempt < 2:
                    print(f"[dedup-llm] Batch {ci+1} attempt {attempt+1} failed ({e}), retrying...",
                          flush=True)
                    _t.sleep(2)
                else:
                    print(f"[dedup-llm] Batch {ci+1} failed after 3 attempts, skipping.", flush=True)
                    return {"themes": []}

    all_themes = []
    max_workers = min(len(chunks), 4)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_run_chunk, ci, chunk): ci
                   for ci, chunk in enumerate(chunks)}
        for future in as_completed(futures):
            ci = futures[future]
            try:
                result = future.result()
            except Exception as e:
                print(f"[dedup-llm] Batch {ci+1} raised unexpectedly: {e}, skipping.", flush=True)
                result = {"themes": []}
            themes_batch = result.get("themes", [])
            print(f"[dedup-llm] Batch {ci+1}/{len(chunks)} returned "
                  f"{len(themes_batch)} themes", flush=True)
            all_themes.extend(themes_batch)

    themes = all_themes
    print(f"[dedup-llm] LLM identified {len(themes)} themes", flush=True)

    # Build a reason_id -> pair_id lookup
    reason_pair_map = {r["reason_id"]: r["pair_id"] for r in reasons}

    # Convert to cluster format so Stage 4 works unchanged
    clusters = []
    for theme in themes:
        member_ids = theme.get("reason_ids", [])
        contributing_pairs = sorted(set(
            reason_pair_map.get(rid, -1) for rid in member_ids
        ) - {-1})

        clusters.append({
            "cluster_id": theme.get("theme_id", len(clusters)),
            "representative_reason": theme.get("label", ""),
            "cluster_size": theme.get("count", len(member_ids)),
            "member_reason_ids": member_ids,
            "contributing_pair_ids": contributing_pairs,
        })

    # Sort by cluster_size descending
    clusters.sort(key=lambda c: -c["cluster_size"])
    return clusters


# --- Method B: Embedding-based clustering (fallback) ---

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

# Condense prompt: loaded from file (see prompts/dimension_condense.txt).

CONDENSE_SCHEMA = """{
  "domain": string,
  "choice_context": string,
  "reasoning": string,
  "dimensions": [
    {
      "id": integer,
      "name": string (the feature name, e.g. "Humor", "Action Intensity", "Historical Authenticity"),
      "low_pole": {
        "label": string (2-4 words: absence of the feature, e.g. "Not humorous"),
        "description": string (what minimal/absent looks like),
        "typical_person": string (who avoids or is indifferent to this feature)
      },
      "high_pole": {
        "label": string (2-4 words: strong presence, e.g. "Very humorous"),
        "description": string (what strong presence looks like),
        "typical_person": string (who actively seeks this feature)
      },
      "example_contrast": {
        "low_option": string (an option scoring low on this feature),
        "high_option": string (an option scoring high on this feature)
      },
      "articulability": "explicit" | "partially_explicit" | "implicit",
      "estimated_variance": "mostly_between_person" | "mostly_between_option" | "both",
      "scoring_guidance": string (how to rate from 0=absent to 5=strongly present),
      "subsumed_reasons": [integer]
    }
  ],
  "redundancy_check": [
    {
      "dimension_ids": [integer, integer],
      "correlation_note": string (would these rank options similarly?),
      "resolution": string (why they are kept as separate dimensions)
    }
  ]
}"""


def condense_dimensions(clusters, config, client, model, num_dimensions,
                        condense_prompt_template=None):
    """Distill cluster/theme representatives into K unipolar preference features."""
    if condense_prompt_template is None:
        condense_prompt_template = load_prompt(DEFAULT_CONDENSE_PROMPT)
    domain_item = config.get("domain_item", config.get("domain", "option"))
    domain_items = domain_item + "s"
    timeout = int(config.get("request_timeout_seconds", DEFAULT_TIMEOUT)) * 15
    retries = int(config.get("max_retries", DEFAULT_MAX_RETRIES))

    # Keep only the top themes by cluster_size to avoid prompt overflow.
    max_themes = num_dimensions * 8
    top_clusters = sorted(clusters, key=lambda c: -c["cluster_size"])[:max_themes]

    reason_lines = []
    for i, cluster in enumerate(top_clusters, start=1):
        reason_lines.append(f"{i}. [count={cluster['cluster_size']}] {cluster['representative_reason']}")

    num_pairs = len(set(pid for c in top_clusters for pid in c["contributing_pair_ids"]))

    prompt = condense_prompt_template.format(
        domain_item=domain_item,
        domain_items=domain_items,
        num_pairs=num_pairs,
        K=num_dimensions,
        reason_list="\n".join(reason_lines),
        schema=CONDENSE_SCHEMA,
    )

    print(f"[stage-4] Using top {len(top_clusters)}/{len(clusters)} themes "
          f"(prompt ~{len(prompt) // 4} tokens)", flush=True)

    result = llm_call_json(client, model, prompt, timeout, retries, max_tokens=8192)

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
        best_dim_idx_val = 0
        best_pole_val = "low"
        for p_idx in range(len(pole_texts)):
            if sim_matrix[r_idx, p_idx] > best_sim:
                best_sim = sim_matrix[r_idx, p_idx]
                best_dim_idx_val, best_pole_val = dim_pole_map[p_idx]
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
    dedup_method = getattr(args, "dedup_method", "clustering")
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
        f"- Dedup method: {dedup_method}",
        f"- Themes/clusters: {len(clusters)}",
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
    # Stage 3 dedup method
    parser.add_argument("--dedup-method", choices=["llm", "clustering"], default="llm",
                        help="Deduplication method for Stage 3 (default: llm)")
    parser.add_argument("--num-themes", type=int, default=50,
                        help="Target number of themes for LLM dedup (default: 50)")
    parser.add_argument("--num-clusters", type=int, default=60,
                        help="Number of clusters for embedding-based dedup (default: 60)")
    parser.add_argument("--cluster-distance-threshold", type=float, default=0.1,
                        help="Distance threshold for auto clustering (default: 0.1)")
    parser.add_argument("--coverage-threshold", type=float, default=0.4)
    parser.add_argument("--skip-coverage", action="store_true", help="Skip stage 5 coverage validation")
    # Prompt overrides (default: prompts/ directory next to this script)
    parser.add_argument("--reason-prompt", default=None,
                        help="Path to reason elicitation prompt template "
                             f"(default: {DEFAULT_REASON_PROMPT.relative_to(REPO_ROOT)})")
    parser.add_argument("--dedup-prompt", default=None,
                        help="Path to dedup prompt template "
                             f"(default: {DEFAULT_DEDUP_PROMPT.relative_to(REPO_ROOT)})")
    parser.add_argument("--condense-prompt", default=None,
                        help="Path to dimension condensation prompt template "
                             f"(default: {DEFAULT_CONDENSE_PROMPT.relative_to(REPO_ROOT)})")
    parser.add_argument("--predefined-pairs", default=None,
                        help="Path to a JSON file of pre-defined pairs (skips random sampling). "
                             "Each entry must have option_a_id and option_b_id. "
                             "Use for datasets with natural pair structure (e.g., Scruples dilemmas).")
    parser.add_argument("--max-workers", type=int, default=8)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser.parse_args()


def main():
    args = parse_args()
    config = load_json(Path(args.config))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    embedding_model = args.embedding_model or "text-embedding-3-small"

    # Load prompt templates (from file or default)
    reason_prompt = load_prompt(args.reason_prompt or DEFAULT_REASON_PROMPT)
    dedup_prompt = load_prompt(args.dedup_prompt or DEFAULT_DEDUP_PROMPT)
    condense_prompt = load_prompt(args.condense_prompt or DEFAULT_CONDENSE_PROMPT)
    prompt_src = args.reason_prompt or str(DEFAULT_REASON_PROMPT.relative_to(REPO_ROOT))
    print(f"[prompts] reason={prompt_src}", flush=True)

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
    elif args.predefined_pairs:
        print(f"[stage-1] Loading predefined pairs from {args.predefined_pairs}", flush=True)
        pairs = load_json(Path(args.predefined_pairs))
        # Ensure pair_id is set
        for i, p in enumerate(pairs):
            p.setdefault("pair_id", i)
        write_json(pairs_path, pairs)
        print(f"[stage-1] {len(pairs)} predefined pairs -> {pairs_path}", flush=True)
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
            reason_prompt_template=reason_prompt,
        )
        write_json(reasons_path, reasons)
        print(f"[stage-2] Elicited {len(reasons)} reasons -> {reasons_path}", flush=True)

    # ------------------------------------------------------------------
    # Stage 3 — Deduplicate Reasons
    # ------------------------------------------------------------------
    # Check for cached output from either method
    themes_path = output_dir / "reason_themes.json"
    clusters_path = output_dir / "reason_clusters.json"
    reason_embeddings = None

    if args.dedup_method == "llm":
        if themes_path.exists():
            print(f"[stage-3] Loading existing themes from {themes_path}", flush=True)
            clusters = load_json(themes_path)
        else:
            print(f"[stage-3] Deduplicating {len(reasons)} reasons via LLM...", flush=True)
            clusters = dedup_reasons_llm(reasons, config, client, args.model, args.num_themes,
                                        dedup_prompt_template=dedup_prompt)
            write_json(themes_path, clusters)
            print(f"[stage-3] {len(clusters)} themes -> {themes_path}", flush=True)
    else:
        if clusters_path.exists():
            print(f"[stage-3] Loading existing clusters from {clusters_path}", flush=True)
            clusters = load_json(clusters_path)
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
        print(f"[stage-4] Condensing {len(clusters)} themes into {args.num_dimensions} dimensions...", flush=True)
        dimensions_data = condense_dimensions(
            clusters, config, client, args.model, args.num_dimensions,
            condense_prompt_template=condense_prompt,
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
    elif args.skip_coverage:
        print("[stage-5] Skipping coverage validation (--skip-coverage)", flush=True)
        coverage_report = None
    else:
        print("[stage-5] Validating coverage...", flush=True)
        # Need reason embeddings
        if reason_embeddings is None:
            texts = [r["reason_text"] for r in reasons]
            print(f"[stage-5] Embedding {len(texts)} reasons for coverage check...", flush=True)
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
