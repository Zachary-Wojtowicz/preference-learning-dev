#!/usr/bin/env python3
"""
ICA direction analysis.

Runs FastICA on wine embeddings and produces the same JSON report format
as conditional_pca.py so that label_components_adaptive.py works unchanged.

ICA differs from PCA: instead of maximizing variance it maximizes statistical
independence (non-Gaussianity via FastICA).  The resulting components tend to
be sharper and more semantically focused than PCA directions.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

DEFAULT_INPUT = Path("datasets/wine-130k_embedded.parquet")
DEFAULT_OUTPUT = Path("method_pca/outputs/wine_ica")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-parquet", default=str(DEFAULT_INPUT))
    p.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    p.add_argument("--embedding-column", default="embedding")
    p.add_argument("--text-column", default="text")
    p.add_argument("--label-column", default="title")
    p.add_argument("--num-components", type=int, default=20,
                   help="Number of ICA components to extract")
    p.add_argument("--pca-whiten-components", type=int, default=100,
                   help="PCA components to retain before ICA whitening")
    p.add_argument("--top-k", type=int, default=8,
                   help="Top/bottom examples to store per component")
    p.add_argument("--max-iter", type=int, default=400)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--sample", type=int, default=0,
                   help="Randomly sample N rows before fitting (0 = use all)")
    return p.parse_args()


def load_records(path, embedding_col, text_col, label_col):
    rows = pq.read_table(path).to_pylist()
    records, embeddings = [], []
    for idx, row in enumerate(rows):
        emb = row.get(embedding_col)
        text = row.get(text_col)
        if emb is None or not text:
            continue
        embeddings.append(np.asarray(emb, dtype=np.float32))
        records.append({
            "row_index": idx,
            "label": str(row.get(label_col, "")).strip(),
            "text": str(text).strip(),
        })
    if not embeddings:
        raise ValueError("No embeddings loaded.")
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
    return [fmt(i) for i in order[-top_k:][::-1]], [fmt(i) for i in order[:top_k]]


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading embeddings...", flush=True)
    records, embeddings = load_records(
        args.input_parquet, args.embedding_column,
        args.text_column, args.label_column,
    )
    print(f"  {len(records)} records, dim={embeddings.shape[1]}", flush=True)

    rng = np.random.default_rng(args.seed)
    if args.sample and args.sample < len(records):
        idx = rng.choice(len(records), args.sample, replace=False)
        fit_embeddings = embeddings[idx]
        print(f"  Fitting on {args.sample}-row sample", flush=True)
    else:
        fit_embeddings = embeddings

    # Center
    mean = fit_embeddings.mean(axis=0, keepdims=True)
    fit_centered = fit_embeddings - mean
    all_centered = embeddings - mean

    print(f"Running FastICA (n_components={args.num_components}, "
          f"pca_whiten={args.pca_whiten_components})...", flush=True)

    from sklearn.decomposition import FastICA
    ica = FastICA(
        n_components=args.num_components,
        whiten="unit-variance",
        max_iter=args.max_iter,
        random_state=args.seed,
        tol=1e-4,
    )
    ica.fit(fit_centered)

    # mixing_ shape: (n_features, n_components) — columns are IC directions
    # components_ shape: (n_components, n_features) — rows are unmixing directions
    ic_directions = ica.components_  # (n_components, n_features)

    # Project all embeddings onto each IC direction
    projections = all_centered @ ic_directions.T  # (n_samples, n_components)

    # Compute a "variance explained" proxy: variance of projections per IC
    # (ICA doesn't order by variance, so we sort by this)
    ic_variances = projections.var(axis=0)
    order = np.argsort(ic_variances)[::-1]
    ic_variances = ic_variances[order]
    projections = projections[:, order]
    ic_directions = ic_directions[order]

    total_var = float(embeddings.var(axis=0).sum())
    explained_ratios = (ic_variances / total_var).tolist()

    print("Building component summaries...", flush=True)
    component_summaries = []
    for i in range(args.num_components):
        pos_ex, neg_ex = top_examples(records, projections[:, i], args.top_k)
        component_summaries.append({
            "component_index": i + 1,
            "explained_variance_ratio": float(explained_ratios[i]),
            "cumulative_explained_variance_ratio": float(sum(explained_ratios[:i + 1])),
            "positive_examples": pos_ex,
            "negative_examples": neg_ex,
        })
        print(f"  IC{i + 1}: explained_ratio={explained_ratios[i]:.4%}  "
              f"top={pos_ex[0]['label'][:50]}", flush=True)

    report = {
        "method": "ICA",
        "input_parquet": str(args.input_parquet),
        "record_count": len(records),
        "embedding_dim": int(embeddings.shape[1]),
        "num_components": args.num_components,
        "component_summaries": component_summaries,
    }

    report_path = output_dir / "ica_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
    print(f"Wrote {report_path}", flush=True)
    print(json.dumps({
        "output_dir": str(output_dir),
        "num_components": args.num_components,
        "record_count": len(records),
    }, indent=2))


if __name__ == "__main__":
    main()
