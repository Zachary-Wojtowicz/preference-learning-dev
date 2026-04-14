#!/usr/bin/env python3
"""
raw_directions.py — Compute PCA and ICA directions from embeddings.

Outputs a single unified JSON where every direction (regardless of method)
has the same shape:
  {
    "id":                     "pca_1",
    "method":                 "pca",
    "rank":                   1,
    "explained_variance_ratio": 0.045,
    "direction_vector":       [...],   # unit-length, float32
    "positive_examples":      [...],   # top-K items
    "negative_examples":      [...]    # bottom-K items
  }

Each example:  { row_index, label, score, text }

Downstream scripts consume only this JSON — no parquet needed again.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-parquet", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--embedding-column", default="embedding")
    p.add_argument("--text-column", default="text")
    p.add_argument("--label-column", default="title")
    p.add_argument("--filter-column", default=None,
                   help="Column to filter rows on (e.g. 'variety')")
    p.add_argument("--filter-value", default=None,
                   help="Keep only rows where filter-column == this value")
    # PCA
    p.add_argument("--pca-components", type=int, default=20)
    # ICA
    p.add_argument("--ica-components", type=int, default=20)
    p.add_argument("--ica-sample", type=int, default=30000,
                   help="Rows to fit ICA on (0=all; ICA is O(n) so sampling helps)")
    p.add_argument("--ica-max-iter", type=int, default=500)
    p.add_argument("--skip-ica", action="store_true")
    # Examples
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def load_records(path, embedding_col, text_col, label_col,
                 filter_col=None, filter_val=None):
    rows = pq.read_table(path).to_pylist()
    records, embeddings = [], []
    for idx, row in enumerate(rows):
        if filter_col and filter_val is not None:
            if str(row.get(filter_col, "") or "") != filter_val:
                continue
        emb = row.get(embedding_col)
        text = row.get(text_col)
        if emb is None or not text:
            continue
        embeddings.append(np.asarray(emb, dtype=np.float32))
        records.append({
            "row_index": idx,
            "label": str(row.get(label_col, "") or "").strip(),
            "text": str(text).strip(),
        })
    return records, np.vstack(embeddings)


def top_examples(records, projections, top_k):
    order = np.argsort(projections)
    def fmt(i):
        return {
            "row_index": int(records[i]["row_index"]),
            "label": records[i]["label"],
            "score": float(projections[i]),
            "text": records[i]["text"],
        }
    return (
        [fmt(i) for i in order[-top_k:][::-1]],
        [fmt(i) for i in order[:top_k]],
    )


def unit(v):
    n = np.linalg.norm(v)
    return (v / n).astype(np.float32) if n > 0 else v.astype(np.float32)


# ---------------------------------------------------------------------------
# PCA
# ---------------------------------------------------------------------------

def run_pca(centered, n_components):
    """Returns (components, explained_variance_ratio) sorted descending."""
    cov = np.cov(centered.astype(np.float64), rowvar=False)
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = np.argsort(eigvals)[::-1]
    eigvals = np.clip(eigvals[order], 0, None)
    eigvecs = eigvecs[:, order]
    total = eigvals.sum()
    evr = eigvals / total if total > 0 else np.zeros_like(eigvals)
    components = eigvecs[:, :n_components].T          # (n_components, d)
    return components.astype(np.float32), evr[:n_components].tolist()


# ---------------------------------------------------------------------------
# ICA
# ---------------------------------------------------------------------------

def run_ica(centered, n_components, sample_size, max_iter, seed):
    from sklearn.decomposition import FastICA
    import warnings

    rng = np.random.default_rng(seed)
    if sample_size and sample_size < centered.shape[0]:
        idx = rng.choice(centered.shape[0], sample_size, replace=False)
        fit_data = centered[idx]
    else:
        fit_data = centered

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ica = FastICA(
            n_components=n_components,
            whiten="unit-variance",
            max_iter=max_iter,
            random_state=seed,
            tol=1e-4,
        )
        ica.fit(fit_data)

    # components_: (n_components, d) — unmixing directions
    directions = ica.components_.astype(np.float32)   # (K, d)
    projections = centered @ directions.T              # (N, K)

    # Sort by projection variance (ICA gives no natural order)
    proj_var = projections.var(axis=0)
    order = np.argsort(proj_var)[::-1]
    directions = directions[order]
    total_var = float(centered.var(axis=0).sum())
    evr = (proj_var[order] / total_var).tolist()

    return directions, evr


# ---------------------------------------------------------------------------
# Build direction records
# ---------------------------------------------------------------------------

def build_direction_records(method, directions, evr, records, centered, top_k):
    out = []
    for rank, (vec, ratio) in enumerate(zip(directions, evr), start=1):
        proj = centered @ vec.astype(np.float64)
        pos_ex, neg_ex = top_examples(records, proj, top_k)
        out.append({
            "id": f"{method}_{rank}",
            "method": method,
            "rank": rank,
            "explained_variance_ratio": float(ratio),
            "direction_vector": unit(vec).tolist(),
            "positive_examples": pos_ex,
            "negative_examples": neg_ex,
        })
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading embeddings...", flush=True)
    records, embeddings = load_records(
        args.input_parquet, args.embedding_column,
        args.text_column, args.label_column,
        filter_col=args.filter_column, filter_val=args.filter_value,
    )
    if args.filter_value:
        print(f"  Filtered to {args.filter_column}={args.filter_value!r}: "
              f"{len(records)} records", flush=True)
    else:
        print(f"  {len(records)} records, dim={embeddings.shape[1]}", flush=True)

    mean = embeddings.mean(axis=0, keepdims=True)
    centered = (embeddings - mean).astype(np.float32)

    all_directions = []

    # PCA
    print(f"Computing {args.pca_components} PCA components...", flush=True)
    pca_vecs, pca_evr = run_pca(centered, args.pca_components)
    all_directions += build_direction_records(
        "pca", pca_vecs, pca_evr, records, centered, args.top_k
    )
    print(f"  PCA done. Top-5 EVR: {[round(r, 4) for r in pca_evr[:5]]}", flush=True)

    # ICA
    if not args.skip_ica:
        print(f"Computing {args.ica_components} ICA components "
              f"(sample={args.ica_sample or 'all'})...", flush=True)
        ica_vecs, ica_evr = run_ica(
            centered, args.ica_components,
            args.ica_sample, args.ica_max_iter, args.seed,
        )
        all_directions += build_direction_records(
            "ica", ica_vecs, ica_evr, records, centered, args.top_k
        )
        print(f"  ICA done. Top-5 EVR proxy: {[round(r, 4) for r in ica_evr[:5]]}", flush=True)

    report = {
        "input_parquet": str(args.input_parquet),
        "record_count": len(records),
        "embedding_dim": int(embeddings.shape[1]),
        "top_k": args.top_k,
        "directions": all_directions,
    }

    out_path = output_dir / "directions.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
    print(f"Wrote {len(all_directions)} directions → {out_path}", flush=True)
    print(json.dumps({
        "output": str(out_path),
        "pca_directions": args.pca_components,
        "ica_directions": 0 if args.skip_ica else args.ica_components,
        "total_directions": len(all_directions),
    }, indent=2))


if __name__ == "__main__":
    main()
