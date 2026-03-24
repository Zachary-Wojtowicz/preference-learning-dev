#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

DEFAULT_INPUT = Path("datasets/wine-130k_embedded.parquet")
DEFAULT_OUTPUT = Path("method_pca/outputs/wine_conditional")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-parquet", default=str(DEFAULT_INPUT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--embedding-column", default="embedding")
    parser.add_argument("--text-column", default="text")
    parser.add_argument("--label-column", default="title")
    parser.add_argument("--num-components", type=int, default=50)
    parser.add_argument("--subset-size", type=int, default=20000,
                        help="How many nearest-to-origin wines to keep when controlling for previous PCs.")
    parser.add_argument("--min-subset-size", type=int, default=5000)
    parser.add_argument("--top-k", type=int, default=8)
    return parser.parse_args()


def load_records(path, embedding_column, text_column, label_column):
    rows = pq.read_table(path).to_pylist()
    records, embeddings = [], []
    for idx, row in enumerate(rows):
        emb = row.get(embedding_column)
        text = row.get(text_column)
        if emb is None or not text:
            continue
        embeddings.append(np.asarray(emb, dtype=np.float32))
        records.append({"row_index": idx, "label": str(row.get(label_column, "")).strip(), "text": str(text).strip()})
    if not embeddings:
        raise ValueError("No embeddings loaded.")
    return records, np.vstack(embeddings)


def leading_eigenvector(x):
    eigenvalues, eigenvectors = np.linalg.eigh(np.cov(x, rowvar=False, dtype=np.float64))
    idx = int(np.argmax(eigenvalues))
    value = float(max(eigenvalues[idx], 0.0))
    vector = eigenvectors[:, idx].astype(np.float64)
    norm = np.linalg.norm(vector)
    if norm == 0:
        raise ValueError("Degenerate eigenvector.")
    vector /= norm
    total = float(np.clip(eigenvalues, 0.0, None).sum())
    return vector.astype(np.float32), value, (value / total if total > 0 else 0.0)


def residualize(x, components):
    if components.size == 0:
        return x
    scores = x @ components.T
    return x - scores @ components


def top_examples(records, scores, top_k):
    order = np.argsort(scores)
    def fmt(i):
        return {"row_index": int(records[i]["row_index"]), "label": records[i]["label"],
                "score": float(scores[i]), "text": records[i]["text"]}
    return [fmt(i) for i in order[-top_k:][::-1]], [fmt(i) for i in order[:top_k]]


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def write_components_parquet(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table({
        "component_index": [r["component_index"] for r in rows],
        "subset_size": [r["subset_size"] for r in rows],
        "subset_max_control_distance": [r["subset_max_control_distance"] for r in rows],
        "explained_variance_within_subset": [r["explained_variance_within_subset"] for r in rows],
        "explained_variance_ratio_within_subset": [r["explained_variance_ratio_within_subset"] for r in rows],
        "component": [r["component"] for r in rows],
    }), path)


def write_summary(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Controlled PCA", "",
        "Each PC is found after controlling for prior PCs by selecting wines with",
        "the smallest normalized distance in previous-PC score space, then",
        "residualizing those earlier directions within that subset.", "",
    ]
    for row in rows:
        lines += [
            f"## PC{row['component_index']}", "",
            f"- Subset size: `{row['subset_size']}` | Max control distance: `{row['subset_max_control_distance']:.4f}`",
            f"- Explained variance in subset: `{row['explained_variance_ratio_within_subset']:.4%}`", "",
            "### Positive examples", "",
        ]
        lines += [f"- `{item['label']}` ({item['score']:.4f}): {item['text']}" for item in row["positive_examples"]]
        lines += ["", "### Negative examples", ""]
        lines += [f"- `{item['label']}` ({item['score']:.4f}): {item['text']}" for item in row["negative_examples"]]
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main():
    args = parse_args()
    input_path = Path(args.input_parquet)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    records, embeddings = load_records(input_path, args.embedding_column, args.text_column, args.label_column)
    mean_emb = embeddings.mean(axis=0, keepdims=True)
    centered = embeddings - mean_emb

    components = []
    component_rows = []

    for n in range(1, args.num_components + 1):
        if components:
            comp_matrix = np.vstack(components)
            prev_scores = centered @ comp_matrix.T
            scale = np.where(prev_scores.std(axis=0, ddof=1) <= 1e-8, 1.0, prev_scores.std(axis=0, ddof=1))
            control_dist = np.linalg.norm(prev_scores / scale, axis=1)
            order = np.argsort(control_dist)
            subset_size = min(max(args.min_subset_size, args.subset_size), len(order))
            subset_idx = order[:subset_size]
            subset_distance = float(control_dist[subset_idx[-1]])
            working = residualize(centered[subset_idx], comp_matrix)
        else:
            subset_idx = np.arange(centered.shape[0])
            subset_size = int(centered.shape[0])
            subset_distance = 0.0
            working = centered

        vector, explained_var, explained_ratio = leading_eigenvector(working)
        components.append(vector)

        prev_matrix = np.vstack(components[:-1]) if len(components) > 1 else np.empty((0, centered.shape[1]), dtype=np.float32)
        full_scores = residualize(centered, prev_matrix) @ vector
        pos, neg = top_examples(records, full_scores, args.top_k)

        component_rows.append({
            "component_index": n,
            "subset_size": subset_size,
            "subset_max_control_distance": subset_distance,
            "explained_variance_within_subset": explained_var,
            "explained_variance_ratio_within_subset": explained_ratio,
            "component": vector.astype(np.float32).tolist(),
            "positive_examples": pos,
            "negative_examples": neg,
        })
        print(f"Computed controlled PC{n} on subset {subset_size}", flush=True)

    write_components_parquet(output_dir / "conditional_pca_components.parquet", component_rows)
    write_json(output_dir / "conditional_pca_mean_embedding.json", {
        "input_parquet": str(input_path),
        "embedding_dim": int(centered.shape[1]),
        "mean_embedding": mean_emb.astype(np.float32).reshape(-1).tolist(),
    })
    write_json(output_dir / "conditional_pca_report.json", component_rows)
    write_summary(output_dir / "summary.md", component_rows)
    print(json.dumps({"output_dir": str(output_dir), "num_components": len(component_rows), "subset_size": args.subset_size}, indent=2))


if __name__ == "__main__":
    main()
