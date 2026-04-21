#!/usr/bin/env python3
"""
select_options.py — Select a diverse, experiment-ready subset of options.

Domain-agnostic: works for movies, wines, moral dilemmas, products, etc.
The only requirement is a parquet file with embeddings.

Two-stage process:
  1. (Optional) Filter to a candidate pool using arbitrary column thresholds.
  2. Select N diverse options via farthest-first traversal on embeddings.

Farthest-first traversal starts from a random seed, then iteratively adds
the option whose minimum distance to all already-selected options is largest.
This produces a set that covers the embedding space evenly — no cluster is
overrepresented, no niche is missed.

Usage:
    # Movies: select 100 diverse movies from the full embedded catalog
    python datasets/select_options.py \
        --input datasets/movielens-32m-enriched-embedded.parquet \
        --id-column movie_id \
        --num-options 100 \
        --output-csv datasets/movielens-100.csv \
        --output-parquet datasets/movielens-100-embedded.parquet

    # With a popularity filter (requires column in parquet or --aux-csv):
    python datasets/select_options.py \
        --input datasets/movielens-32m-enriched-embedded.parquet \
        --aux-csv datasets/movielens-rating-counts.csv \
        --aux-join-column movieId \
        --id-column movie_id \
        --filter "rating_count >= 500" \
        --num-options 100 \
        --output-csv datasets/movielens-100.csv

    # Scruples: no filter, just diversity
    python datasets/select_options.py \
        --input datasets/scruples-embedded.parquet \
        --id-column dilemma_id \
        --num-options 200 \
        --output-csv datasets/scruples-200.csv
"""

import argparse
import csv
import re
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq


def parse_args():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--input", required=True,
                   help="Input parquet file with embeddings.")
    p.add_argument("--id-column", required=True,
                   help="Column name for option IDs (in the parquet).")
    p.add_argument("--embedding-column", default="embedding",
                   help="Column name for embeddings (default: embedding).")
    p.add_argument("--num-options", "-N", type=int, required=True,
                   help="Number of options to select.")
    p.add_argument("--output-csv", default=None,
                   help="Output CSV path (all columns except embedding).")
    p.add_argument("--output-parquet", default=None,
                   help="Output parquet path (all columns including embedding).")
    p.add_argument("--output-dir", default=None,
                   help="If set, write outputs here with auto-generated names.")

    # Filtering
    p.add_argument("--filter", action="append", default=[],
                   help="Filter expression, e.g. 'rating_count >= 500' or "
                        "'genres contains Drama'. Can be repeated.")
    p.add_argument("--aux-csv", default=None,
                   help="Auxiliary CSV with extra columns for filtering "
                        "(joined to parquet on --aux-join-column).")
    p.add_argument("--aux-join-column", default=None,
                   help="Column name in the aux CSV to join on. The parquet "
                        "side always uses --id-column. These can differ "
                        "(e.g., parquet has 'movie_id', aux CSV has 'movieId').")

    # Selection method
    p.add_argument("--method", choices=["farthest-first", "random"],
                   default="farthest-first",
                   help="Selection method (default: farthest-first).")
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


# --- Data loading -----------------------------------------------------------

def load_parquet(path, embedding_col):
    """Load parquet, returning (DataFrame-like dict, embedding matrix)."""
    table = pq.read_table(path)
    columns = table.column_names

    if embedding_col not in columns:
        raise ValueError(
            f"Embedding column '{embedding_col}' not found. "
            f"Available: {columns}"
        )

    # Build a dict of non-embedding columns
    data = {}
    for col in columns:
        if col == embedding_col:
            continue
        arr = table.column(col).to_pylist()
        data[col] = arr

    embeddings = np.array(table.column(embedding_col).to_pylist(),
                          dtype=np.float64)
    n_rows = len(embeddings)
    print(f"Loaded {n_rows} options, d={embeddings.shape[1]}")
    return data, embeddings, columns


def load_aux_csv(path, join_col):
    """Load auxiliary CSV as a dict of {join_key: {col: val}}."""
    aux = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = row[join_col].strip()
            aux[key] = {k: v.strip() for k, v in row.items()}
    print(f"Loaded {len(aux)} rows from auxiliary CSV")
    return aux


# --- Filtering --------------------------------------------------------------

def apply_filters(data, embeddings, filters, id_column):
    """Apply filter expressions, returning mask of rows to keep."""
    n = len(embeddings)
    mask = np.ones(n, dtype=bool)

    for expr in filters:
        col, op, val = parse_filter_expr(expr)
        if col not in data:
            raise ValueError(
                f"Filter column '{col}' not found. "
                f"Available: {list(data.keys())}"
            )

        col_values = data[col]
        for i in range(n):
            if not mask[i]:
                continue
            mask[i] = evaluate_filter(col_values[i], op, val)

        kept = mask.sum()
        print(f"  Filter '{expr}': {kept}/{n} options remain")

    return mask


def parse_filter_expr(expr):
    """Parse 'column op value' into (column, op, value).

    Supported operators: >=, <=, >, <, ==, !=, contains
    """
    # Try 'contains' first (word operator)
    m = re.match(r"(\S+)\s+(contains)\s+(.+)", expr, re.IGNORECASE)
    if m:
        return m.group(1), "contains", m.group(3).strip()

    # Numeric/string comparisons
    m = re.match(r"(\S+)\s*(>=|<=|!=|==|>|<)\s*(.+)", expr)
    if m:
        return m.group(1), m.group(2), m.group(3).strip()

    raise ValueError(f"Cannot parse filter expression: '{expr}'")


def evaluate_filter(cell_value, op, target):
    """Evaluate a single filter condition against a cell value."""
    if op == "contains":
        return target.lower() in str(cell_value).lower()

    # Try numeric comparison
    try:
        cell_num = float(cell_value)
        target_num = float(target)
        if op == ">=": return cell_num >= target_num
        if op == "<=": return cell_num <= target_num
        if op == ">":  return cell_num > target_num
        if op == "<":  return cell_num < target_num
        if op == "==": return cell_num == target_num
        if op == "!=": return cell_num != target_num
    except (ValueError, TypeError):
        pass

    # Fall back to string comparison
    cell_str = str(cell_value).strip()
    target_str = target.strip()
    if op == "==": return cell_str == target_str
    if op == "!=": return cell_str != target_str

    return False


# --- Diversity selection ----------------------------------------------------

def farthest_first_traversal(embeddings, n_select, seed=42):
    """Select n_select points by farthest-first traversal.

    Starts from a random seed point, then iteratively adds the point
    whose minimum distance to all already-selected points is largest.

    Returns array of selected indices (in order of selection).
    """
    rng = np.random.RandomState(seed)
    N, d = embeddings.shape

    if n_select >= N:
        print(f"  Requested {n_select} but only {N} available. Returning all.")
        return np.arange(N)

    # Normalize for cosine distance
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normed = embeddings / norms

    # Start with random seed
    selected = [rng.randint(N)]
    # min_dist[i] = min distance from point i to any selected point
    min_dist = np.full(N, np.inf)

    for step in range(n_select):
        # Update min distances using the most recently added point
        last = selected[-1]
        # Cosine distance = 1 - cosine_similarity
        dists = 1.0 - normed @ normed[last]
        min_dist = np.minimum(min_dist, dists)
        # Zero out already-selected points
        for s in selected:
            min_dist[s] = -1.0

        if len(selected) >= n_select:
            break

        # Select the point with the largest min distance
        next_idx = int(np.argmax(min_dist))
        selected.append(next_idx)

        if (len(selected)) % 20 == 0:
            print(f"  Selected {len(selected)}/{n_select}...", flush=True)

    return np.array(selected)


def random_selection(embeddings, n_select, seed=42):
    """Select n_select points uniformly at random."""
    rng = np.random.RandomState(seed)
    N = len(embeddings)
    if n_select >= N:
        return np.arange(N)
    return rng.choice(N, size=n_select, replace=False)


# --- Diagnostics ------------------------------------------------------------

def compute_diagnostics(embeddings_full, embeddings_selected, data_selected,
                        id_column):
    """Compute and print selection diagnostics."""
    N_full = len(embeddings_full)
    N_sel = len(embeddings_selected)

    # Normalize
    norms_s = np.linalg.norm(embeddings_selected, axis=1, keepdims=True)
    norms_s[norms_s == 0] = 1.0
    normed_s = embeddings_selected / norms_s

    # Pairwise distances among selected
    sim = normed_s @ normed_s.T
    np.fill_diagonal(sim, -1.0)
    dists = 1.0 - sim
    np.fill_diagonal(dists, 0.0)

    min_dists = np.array([dists[i][dists[i] > 0].min() for i in range(N_sel)])
    mean_dist = dists[np.triu_indices(N_sel, k=1)].mean()

    # Coverage: for each point in full set, distance to nearest selected point
    norms_f = np.linalg.norm(embeddings_full, axis=1, keepdims=True)
    norms_f[norms_f == 0] = 1.0
    normed_f = embeddings_full / norms_f
    coverage_dists = 1.0 - normed_f @ normed_s.T  # (N_full, N_sel)
    nearest_dist = coverage_dists.min(axis=1)  # (N_full,)

    lines = []
    lines.append(f"Selected {N_sel} from {N_full} candidates")
    lines.append(f"Mean pairwise cosine distance (selected): {mean_dist:.4f}")
    lines.append(f"Min nearest-neighbor distance (selected): {min_dists.min():.4f}")
    lines.append(f"Mean nearest-neighbor distance (selected): {min_dists.mean():.4f}")
    lines.append(f"Coverage — mean distance from any candidate to nearest selected: "
                 f"{nearest_dist.mean():.4f}")
    lines.append(f"Coverage — max distance from any candidate to nearest selected: "
                 f"{nearest_dist.max():.4f}")
    lines.append(f"Coverage — 95th percentile: {np.percentile(nearest_dist, 95):.4f}")

    return lines


# --- Output -----------------------------------------------------------------

def write_csv_output(path, data, selected_indices, columns, embedding_col):
    """Write selected options to CSV (excluding embedding column)."""
    out_cols = [c for c in columns if c != embedding_col]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_cols)
        writer.writeheader()
        for i in selected_indices:
            row = {col: data[col][i] for col in out_cols}
            writer.writerow(row)
    print(f"Wrote {len(selected_indices)} rows to {path}")


def write_parquet_output(path, data, embeddings, selected_indices,
                         columns, embedding_col):
    """Write selected options to parquet (including embedding column)."""
    import pyarrow as pa

    col_data = {}
    for col in columns:
        if col == embedding_col:
            col_data[col] = pa.array(
                [embeddings[i].tolist() for i in selected_indices],
                type=pa.list_(pa.float32()),
            )
        else:
            col_data[col] = pa.array(
                [data[col][i] for i in selected_indices],
            )

    table = pa.table(col_data)
    pq.write_table(table, path)
    print(f"Wrote {len(selected_indices)} rows to {path}")


# --- Main -------------------------------------------------------------------

def main():
    args = parse_args()

    # Load data
    data, embeddings, columns = load_parquet(
        args.input, args.embedding_column
    )
    N = len(embeddings)

    if args.id_column not in data:
        raise ValueError(
            f"ID column '{args.id_column}' not found. "
            f"Available: {list(data.keys())}"
        )

    # Join auxiliary CSV if provided
    if args.aux_csv:
        aux_join_col = args.aux_join_column or args.id_column
        aux = load_aux_csv(args.aux_csv, aux_join_col)
        # Use the parquet's id column to look up keys, matched against
        # the aux CSV's join column. These may have different names
        # (e.g., parquet has "movie_id", aux CSV has "movieId").
        parquet_key_col = args.id_column

        # Determine which columns are new
        aux_cols = set()
        for key_data in aux.values():
            aux_cols.update(key_data.keys())
        aux_cols -= set(data.keys())
        aux_cols -= {aux_join_col}  # don't duplicate the join key

        for col in sorted(aux_cols):
            data[col] = []
            for i in range(N):
                key = str(data[parquet_key_col][i]).strip()
                val = aux.get(key, {}).get(col, "")
                data[col].append(val)
            columns = list(columns) + [col]

        matched = sum(1 for i in range(N)
                      if str(data[parquet_key_col][i]).strip() in aux)
        print(f"  Joined auxiliary CSV: {matched}/{N} rows matched")
        for col in sorted(aux_cols):
            print(f"  Added column: {col}")

    # Apply filters
    if args.filter:
        print("Applying filters...")
        mask = apply_filters(data, embeddings, args.filter, args.id_column)
        candidate_indices = np.where(mask)[0]
        print(f"  {len(candidate_indices)} candidates after filtering "
              f"(from {N} total)")
    else:
        candidate_indices = np.arange(N)
        print(f"No filters applied. {N} candidates.")

    if len(candidate_indices) < args.num_options:
        print(f"WARNING: Only {len(candidate_indices)} candidates available, "
              f"but requested {args.num_options}. Selecting all.")

    # Extract candidate embeddings
    candidate_embeddings = embeddings[candidate_indices]

    # Select diverse subset
    print(f"Selecting {args.num_options} options via {args.method}...")
    if args.method == "farthest-first":
        local_indices = farthest_first_traversal(
            candidate_embeddings, args.num_options, args.seed
        )
    else:
        local_indices = random_selection(
            candidate_embeddings, args.num_options, args.seed
        )

    # Map back to global indices
    selected_indices = candidate_indices[local_indices]

    # Diagnostics
    print("")
    diag_lines = compute_diagnostics(
        candidate_embeddings, embeddings[selected_indices],
        {col: [data[col][i] for i in selected_indices] for col in data},
        args.id_column,
    )
    for line in diag_lines:
        print(f"  {line}")
    print("")

    # Determine output paths
    if args.output_dir:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = Path(args.input).stem.replace("-embedded", "")
        csv_path = args.output_csv or str(out_dir / f"{stem}-{args.num_options}.csv")
        parquet_path = args.output_parquet or str(
            out_dir / f"{stem}-{args.num_options}-embedded.parquet"
        )
    else:
        csv_path = args.output_csv
        parquet_path = args.output_parquet

    if not csv_path and not parquet_path:
        print("No output path specified (--output-csv, --output-parquet, "
              "or --output-dir). Printing selected IDs only.")
        for i in selected_indices:
            print(f"  {data[args.id_column][i]}")
        return

    # Write outputs
    if csv_path:
        write_csv_output(csv_path, data, selected_indices, columns,
                         args.embedding_column)
    if parquet_path:
        write_parquet_output(parquet_path, data, embeddings, selected_indices,
                             columns, args.embedding_column)

    # Write diagnostic summary
    if args.output_dir:
        summary_path = Path(args.output_dir) / "selection_summary.md"
        with open(summary_path, "w") as f:
            f.write(f"# Option Selection Summary\n\n")
            f.write(f"- Input: {args.input}\n")
            f.write(f"- Total options: {N}\n")
            f.write(f"- After filtering: {len(candidate_indices)}\n")
            f.write(f"- Selected: {len(selected_indices)}\n")
            f.write(f"- Method: {args.method}\n")
            f.write(f"- Seed: {args.seed}\n")
            if args.filter:
                f.write(f"- Filters: {args.filter}\n")
            f.write(f"\n## Diagnostics\n\n")
            for line in diag_lines:
                f.write(f"- {line}\n")
            f.write(f"\n## Selected Options\n\n")
            for i in selected_indices:
                oid = data[args.id_column][i]
                # Try to find a display name
                for name_col in ["title", "name", "display_text", "text"]:
                    if name_col in data:
                        f.write(f"- {oid}: {data[name_col][i]}\n")
                        break
                else:
                    f.write(f"- {oid}\n")
        print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()
