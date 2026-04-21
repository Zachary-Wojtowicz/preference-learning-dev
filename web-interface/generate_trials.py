#!/usr/bin/env python3
"""Generate experiment trials from pipeline outputs.

Takes embeddings, direction vectors, dimension metadata, and option
descriptions, and produces a trials.json for the web interface.

Usage:
    python generate_trials.py \
      --config ../method_llm_examples/configs/movies_100.json \
      --embeddings-parquet ../datasets/movies_100/movies_100-embedded.parquet \
      --dimensions ../method_llm_gen/outputs/movies_100/dimensions.json \
      --directions ../method_directions/outputs/movies_100/directions.npz \
      --output-dir . \
      --num-pairs 200 \
      --seed 42
"""

import argparse
import csv
import json
import string
import sys
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_options_csv(csv_path, id_column, template_path=None):
    """Load option descriptions from a CSV file.

    Returns dict: option_id -> {columns..., _rendered_text: str}
    """
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    template = None
    if template_path and Path(template_path).exists():
        template = Path(template_path).read_text(encoding="utf-8").strip()

    options = {}
    for row in rows:
        oid = str(row[id_column]).strip()
        if template:
            try:
                rendered = template.format(**row)
            except KeyError:
                rendered = " | ".join(f"{k}: {v}" for k, v in row.items()
                                      if k != id_column and v)
        else:
            rendered = " | ".join(f"{k}: {v}" for k, v in row.items()
                                  if k != id_column and v)
        row["_rendered_text"] = rendered
        options[oid] = row
    return options


def load_embeddings(parquet_path, id_column, embedding_column="embedding"):
    """Load embeddings from a parquet file. Returns (option_ids, matrix)."""
    table = pq.read_table(parquet_path)
    rows = table.to_pylist()

    option_ids = []
    vectors = []
    for row in rows:
        oid = str(row[id_column]).strip()
        vec = row[embedding_column]
        if isinstance(vec, list):
            option_ids.append(oid)
            vectors.append(np.array(vec, dtype=np.float64))

    return option_ids, np.array(vectors)


def load_dimensions(dimensions_path):
    """Load dimension metadata from dimensions.json."""
    with open(dimensions_path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("dimensions", data if isinstance(data, list) else [])


def load_directions(directions_path):
    """Load direction vectors from directions.npz."""
    npz = np.load(directions_path)
    V = npz["directions_ortho"].astype(np.float64)   # (K, d)
    mu = npz["mean_embedding"].astype(np.float64)     # (d,)
    return V, mu


# ---------------------------------------------------------------------------
# Pair sampling
# ---------------------------------------------------------------------------

def sample_diverse_pairs(embeddings, option_ids, num_pairs, num_strata, seed):
    """Sample pairs stratified by cosine distance."""
    n = len(option_ids)
    if n < 2:
        raise ValueError(f"Need at least 2 options, got {n}")

    # Center and normalize
    matrix = embeddings - embeddings.mean(axis=0)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normed = matrix / norms

    # Cosine distance matrix
    sim = normed @ normed.T
    np.fill_diagonal(sim, 1.0)
    dist = 1.0 - sim

    # Collect all unique pairs
    all_pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            all_pairs.append((i, j, dist[i, j]))

    all_pairs.sort(key=lambda x: x[2])

    total_pairs = len(all_pairs)
    num_pairs = min(num_pairs, total_pairs)

    # Stratify
    stratum_size = total_pairs // num_strata
    strata = []
    stratum_labels = ["near", "medium", "far"] if num_strata == 3 else \
        [f"stratum_{s}" for s in range(num_strata)]

    for s in range(num_strata):
        start = s * stratum_size
        end = total_pairs if s == num_strata - 1 else (s + 1) * stratum_size
        strata.append(all_pairs[start:end])

    # Sample from each
    rng = np.random.RandomState(seed)
    per_stratum = num_pairs // num_strata
    sampled = []

    for s_idx, stratum in enumerate(strata):
        count = per_stratum if s_idx < num_strata - 1 else num_pairs - len(sampled)
        count = min(count, len(stratum))
        indices = rng.choice(len(stratum), size=count, replace=False)
        for idx in indices:
            i, j, d = stratum[idx]
            sampled.append({
                "idx_a": i,
                "idx_b": j,
                "option_a_id": option_ids[i],
                "option_b_id": option_ids[j],
                "distance_stratum": stratum_labels[s_idx],
                "cosine_distance": round(float(d), 6),
            })

    return sampled


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------

def compute_projections(embeddings, V, mu, idx_a, idx_b):
    """Compute projection of δ = φ(a) - φ(b) onto V.

    Returns λ = V⊤δ as a 1D array of shape (K,).
    """
    phi_a = embeddings[idx_a]
    phi_b = embeddings[idx_b]
    delta = phi_a - phi_b  # (d,)
    lam = V @ delta        # (K,)
    return lam


def scale_to_range(lam, all_lambdas, range_val=100):
    """Scale raw projections to [-range_val, range_val] using the
    global max absolute value per dimension.

    all_lambdas: (num_pairs, K) — used for calibration.
    """
    max_abs = np.abs(all_lambdas).max(axis=0)  # (K,)
    max_abs[max_abs == 0] = 1.0
    scaled = (lam / max_abs) * range_val
    return np.clip(np.round(scaled), -range_val, range_val).astype(int)


# ---------------------------------------------------------------------------
# Build trials
# ---------------------------------------------------------------------------

def build_display_text(option_row, display_column, text_column=None):
    """Build a human-readable display string for an option.

    For the experiment, we show a structured card rather than the
    raw embedding template. Returns a dict with structured fields.
    """
    result = {}
    # Title (or display column)
    if display_column and display_column in option_row:
        result["title"] = option_row[display_column]

    # Include other useful columns, excluding internal ones
    skip = {"_rendered_text", display_column, "movie_id", "action_id",
            "option_id", "id"}
    for key, val in option_row.items():
        if key in skip or not val or key.startswith("_"):
            continue
        result[key] = val

    return result


def build_trials(pairs, embeddings, V, mu, dimensions, options_lookup,
                 display_column, text_column, choice_context):
    """Build the trials.json data structure."""

    # First pass: compute all raw projections for calibration
    K = V.shape[0]
    all_lambdas = np.zeros((len(pairs), K))
    for p_idx, pair in enumerate(pairs):
        all_lambdas[p_idx] = compute_projections(
            embeddings, V, mu, pair["idx_a"], pair["idx_b"]
        )

    # Build slider metadata from dimensions
    slider_meta = []
    for dim in dimensions:
        slider_meta.append({
            "id": f"dim_{dim['id']}",
            "dimension_id": dim["id"],
            "name": dim["name"],
            "low_label": dim.get("low_pole", {}).get("label", "Low"),
            "high_label": dim.get("high_pole", {}).get("label", "High"),
            "low_description": dim.get("low_pole", {}).get("description", ""),
            "high_description": dim.get("high_pole", {}).get("description", ""),
            "scoring_guidance": dim.get("scoring_guidance", ""),
        })

    # Build each trial
    trials = []
    for p_idx, pair in enumerate(pairs):
        opt_a = options_lookup.get(pair["option_a_id"], {})
        opt_b = options_lookup.get(pair["option_b_id"], {})

        # Display info
        display_a = build_display_text(opt_a, display_column, text_column)
        display_b = build_display_text(opt_b, display_column, text_column)

        # Compute scaled projections
        lam_raw = all_lambdas[p_idx]  # (K,) — positive means A > B
        scaled_a = scale_to_range(lam_raw, all_lambdas, 100)    # if A chosen
        scaled_b = scale_to_range(-lam_raw, all_lambdas, 100)   # if B chosen

        # Build slider list
        sliders = []
        for s_idx, sm in enumerate(slider_meta):
            sliders.append({
                "id": sm["id"],
                "dimension_id": sm["dimension_id"],
                "label": sm["name"],
                "low_label": sm["low_label"],
                "high_label": sm["high_label"],
                "value_if_a": int(scaled_a[s_idx]),
                "value_if_b": int(scaled_b[s_idx]),
            })

        trial = {
            "trial_id": f"t{p_idx + 1}",
            "pair_index": p_idx,
            "option_a_id": pair["option_a_id"],
            "option_b_id": pair["option_b_id"],
            "distance_stratum": pair["distance_stratum"],
            "cosine_distance": pair["cosine_distance"],
            "prompt": choice_context,
            "option_a": {
                "label": display_a.get("title", f"Option A ({pair['option_a_id']})"),
                "fields": display_a,
            },
            "option_b": {
                "label": display_b.get("title", f"Option B ({pair['option_b_id']})"),
                "fields": display_b,
            },
            "sliders": sliders,
        }
        trials.append(trial)

    return trials, slider_meta


# ---------------------------------------------------------------------------
# Experiment config
# ---------------------------------------------------------------------------

def build_experiment_config(slider_meta, dimensions, args):
    """Build experiment_config.json with condition settings."""
    return {
        "domain": args.domain or "unknown",
        "choice_context": args.choice_context or "",
        "num_trials_per_participant": args.trials_per_participant,
        "conditions": {
            "choice_only": {
                "label": "Choice Only",
                "description": "Binary choice, no dimension sliders shown.",
                "show_sliders": False,
                "sliders_adjustable": False,
                "show_free_text": False,
            },
            "choice_readonly_sliders": {
                "label": "Choice + Read-Only Sliders",
                "description": "Binary choice with dimension scores shown (not adjustable).",
                "show_sliders": True,
                "sliders_adjustable": False,
                "show_free_text": False,
            },
            "choice_adjustable_sliders": {
                "label": "Choice + Adjustable Sliders",
                "description": "Binary choice with adjustable dimension sliders.",
                "show_sliders": True,
                "sliders_adjustable": True,
                "show_free_text": False,
            },
            "choice_sliders_text": {
                "label": "Choice + Sliders + Reason",
                "description": "Binary choice with adjustable sliders and a free-text reason field.",
                "show_sliders": True,
                "sliders_adjustable": True,
                "show_free_text": True,
            },
        },
        "default_condition": "choice_adjustable_sliders",
        "slider_range": [-100, 100],
        "dimensions": [
            {
                "id": sm["id"],
                "dimension_id": sm["dimension_id"],
                "name": sm["name"],
                "low_label": sm["low_label"],
                "high_label": sm["high_label"],
                "scoring_guidance": sm["scoring_guidance"],
            }
            for sm in slider_meta
        ],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", required=True,
                   help="Path to pipeline config JSON (for CSV path, template, columns).")
    p.add_argument("--embeddings-parquet", required=True,
                   help="Path to the embedded parquet file.")
    p.add_argument("--dimensions", required=True,
                   help="Path to dimensions.json.")
    p.add_argument("--directions", required=True,
                   help="Path to directions.npz.")
    p.add_argument("--output-dir", default=".",
                   help="Directory for output files (default: current dir).")
    p.add_argument("--num-pairs", type=int, default=200,
                   help="Number of pairs to sample (default: 200).")
    p.add_argument("--strata", type=int, default=3,
                   help="Number of distance strata (default: 3).")
    p.add_argument("--trials-per-participant", type=int, default=30,
                   help="Number of trials shown per participant (default: 30).")
    p.add_argument("--domain", default=None,
                   help="Domain label (auto-detected from config if omitted).")
    p.add_argument("--choice-context", default=None,
                   help="Prompt shown above each pair (auto-detected from config if omitted).")
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def main():
    args = parse_args()

    # Load pipeline config
    with open(args.config, encoding="utf-8") as f:
        config = json.load(f)

    id_column = config["id_column"]
    display_column = config.get("display_column", "title")
    text_column = config.get("text_column", "")
    csv_path = config["input_path"]
    template_path = config.get("template_path", "")

    # Resolve relative paths: try CWD first (repo root), then config dir
    config_dir = Path(args.config).resolve().parent
    def resolve_path(p):
        if Path(p).is_absolute():
            return p
        # Prefer CWD (repo root when run from pipeline)
        if Path(p).exists():
            return str(Path(p).resolve())
        # Fall back to config-relative
        config_relative = config_dir / p
        if config_relative.exists():
            return str(config_relative)
        return p  # return as-is, will error later

    csv_path = resolve_path(csv_path)
    if template_path:
        template_path = resolve_path(template_path)

    if not args.domain:
        args.domain = config.get("domain", "unknown")
    if not args.choice_context:
        args.choice_context = config.get("choice_context", "Which option do you prefer?")

    # Load data
    print("Loading options...")
    options_lookup = load_options_csv(csv_path, id_column, template_path)
    print(f"  {len(options_lookup)} options")

    print("Loading embeddings...")
    emb_ids, embeddings = load_embeddings(args.embeddings_parquet, id_column)
    print(f"  {len(emb_ids)} embeddings, d={embeddings.shape[1]}")

    print("Loading dimensions...")
    dimensions = load_dimensions(args.dimensions)
    print(f"  {len(dimensions)} dimensions")

    print("Loading directions...")
    V, mu = load_directions(args.directions)
    print(f"  V: {V.shape}, mu: {mu.shape}")

    # Verify K matches
    if V.shape[0] != len(dimensions):
        print(f"WARNING: directions has {V.shape[0]} rows but "
              f"dimensions.json has {len(dimensions)} dimensions. "
              f"Using min({V.shape[0]}, {len(dimensions)}).")
        k = min(V.shape[0], len(dimensions))
        V = V[:k]
        dimensions = dimensions[:k]

    # Sample pairs
    print(f"Sampling {args.num_pairs} diverse pairs...")
    pairs = sample_diverse_pairs(
        embeddings, emb_ids, args.num_pairs, args.strata, args.seed
    )
    print(f"  Sampled {len(pairs)} pairs")

    # Build trials
    print("Building trials...")
    trials, slider_meta = build_trials(
        pairs, embeddings, V, mu, dimensions, options_lookup,
        display_column, text_column, args.choice_context,
    )

    # Build experiment config
    experiment_config = build_experiment_config(slider_meta, dimensions, args)

    # Write outputs
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    trials_path = output_dir / "trials.json"
    with open(trials_path, "w", encoding="utf-8") as f:
        json.dump(trials, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(trials)} trials -> {trials_path}")

    config_path = output_dir / "experiment_config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(experiment_config, f, indent=2, ensure_ascii=False)
    print(f"Wrote experiment config -> {config_path}")

    # Write raw projections for downstream analysis
    projections_path = output_dir / "trial_projections.json"
    proj_data = []
    for p_idx, pair in enumerate(pairs):
        lam = compute_projections(embeddings, V, mu, pair["idx_a"], pair["idx_b"])
        proj_data.append({
            "trial_id": f"t{p_idx + 1}",
            "option_a_id": pair["option_a_id"],
            "option_b_id": pair["option_b_id"],
            "raw_projection": lam.tolist(),
            "dimension_names": [d["name"] for d in dimensions],
        })
    with open(projections_path, "w", encoding="utf-8") as f:
        json.dump(proj_data, f, indent=2, ensure_ascii=False)
    print(f"Wrote raw projections -> {projections_path}")

    # Summary stats
    print(f"\n--- Summary ---")
    print(f"  Domain: {args.domain}")
    print(f"  Options: {len(options_lookup)}")
    print(f"  Dimensions (K): {len(dimensions)}")
    print(f"  Pairs sampled: {len(pairs)}")
    print(f"  Trials per participant: {args.trials_per_participant}")
    print(f"  Total unique trials: {len(trials)}")


if __name__ == "__main__":
    main()
