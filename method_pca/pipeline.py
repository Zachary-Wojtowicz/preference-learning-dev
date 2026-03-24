#!/usr/bin/env python3
import argparse
import json
from collections import defaultdict, namedtuple
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

DEFAULT_INPUT = Path("datasets/writing_embedded.parquet")
DEFAULT_OUTPUT = Path("method_pca/outputs/writing")
DEFAULT_BASE_URL = "http://localhost:8000/v1"
DEFAULT_VARIANCE_THRESHOLD = 0.9999

ComponentSummary = namedtuple(
    "ComponentSummary",
    ["component_index", "explained_variance_ratio", "cumulative_explained_variance_ratio",
     "positive_examples", "negative_examples", "llm_explanation", "llm_prompt"],
)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--input-parquet", default=str(DEFAULT_INPUT))
    p.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    p.add_argument("--embedding-column", default="embedding")
    p.add_argument("--text-column", default="text")
    p.add_argument("--group-column", default="style_name")
    p.add_argument("--label-column", default="style_name")
    p.add_argument("--delta-mode", choices=["centered_rows", "group_centroids", "sampled_rows"], default="group_centroids")
    p.add_argument("--max-row-pairs", type=int, default=25000)
    p.add_argument("--variance-threshold", type=float, default=DEFAULT_VARIANCE_THRESHOLD)
    p.add_argument("--top-k", type=int, default=8)
    p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p.add_argument("--model")
    p.add_argument("--api-key", default="dummy")
    p.add_argument("--skip-llm", action="store_true")
    p.add_argument("--llm-components", type=int, default=12)
    p.add_argument("--summary-components", type=int, default=20)
    p.add_argument("--llm-top-k", type=int, default=4)
    p.add_argument("--llm-max-text-chars", type=int, default=220)
    p.add_argument("--seed", type=int, default=7)
    return p.parse_args()


def load_records(parquet_path, embedding_column, text_column, label_column, group_column):
    rows = pq.read_table(parquet_path).to_pylist()
    records, embeddings = [], []
    for i, row in enumerate(rows):
        emb = row.get(embedding_column)
        text = row.get(text_column)
        if emb is None or not text:
            continue
        embeddings.append(np.asarray(emb, dtype=np.float32))
        records.append({
            "row_index": i,
            "text": str(text).strip(),
            "label": str(row.get(label_column, "")).strip() if label_column else "",
            "group": str(row.get(group_column, "")).strip() if group_column else "",
        })
    if not embeddings:
        raise ValueError(f"No rows with both {embedding_column!r} and {text_column!r}.")
    return records, np.vstack(embeddings)


def build_group_centroid_deltas(records, embeddings):
    groups = defaultdict(list)
    for i, r in enumerate(records):
        if r.get("group"):
            groups[r["group"]].append(i)

    if len(groups) < 2:
        raise ValueError("group_centroids mode requires at least two groups. Use --delta-mode sampled_rows instead.")

    names = sorted(groups)
    centroids = np.vstack([embeddings[groups[n]].mean(axis=0) for n in names])
    deltas = [centroids[j] - centroids[i] for i in range(len(names)) for j in range(i + 1, len(names))]
    pairs = [(names[i], names[j]) for i in range(len(names)) for j in range(i + 1, len(names))]

    return np.vstack(deltas), {
        "mode": "group_centroids", "group_count": len(names), "delta_count": len(deltas),
        "group_sizes": {n: len(groups[n]) for n in names}, "pairs": pairs,
    }


def build_sampled_row_deltas(embeddings, max_pairs, seed):
    rng = np.random.default_rng(seed)
    n = embeddings.shape[0]
    if n < 2:
        raise ValueError("Need at least two rows to build row deltas.")
    pair_count = min(max_pairs, n * (n - 1) // 2)
    seen = set()
    deltas = []
    while len(deltas) < pair_count:
        i, j = sorted(rng.choice(n, size=2, replace=False).tolist())
        if (i, j) not in seen:
            seen.add((i, j))
            deltas.append(embeddings[j] - embeddings[i])
    return np.vstack(deltas), {"mode": "sampled_rows", "row_count": n, "delta_count": len(deltas), "max_possible_pairs": n * (n - 1) // 2}


def build_centered_row_deltas(embeddings):
    deltas = embeddings - embeddings.mean(axis=0, keepdims=True)
    return deltas, {"mode": "centered_rows", "row_count": int(embeddings.shape[0]), "delta_count": int(embeddings.shape[0])}


def run_pca(deltas):
    centered = deltas - deltas.mean(axis=0, keepdims=True)
    eigenvalues, eigenvectors = np.linalg.eigh(np.cov(centered, rowvar=False, dtype=np.float64))
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = np.clip(eigenvalues[order], 0.0, None)
    components = eigenvectors[:, order].T
    total = float(eigenvalues.sum())
    explained_ratio = eigenvalues / total if total > 0 else np.zeros_like(eigenvalues)
    return {
        "components": components,
        "singular_values": np.sqrt(eigenvalues * max(centered.shape[0] - 1, 1)),
        "explained_variance": eigenvalues,
        "explained_variance_ratio": explained_ratio,
        "cumulative_explained_variance_ratio": np.cumsum(explained_ratio),
    }


def n_components_for_threshold(cumulative, threshold):
    if cumulative.size == 0:
        return 0
    return min(int(np.searchsorted(cumulative, threshold, side="left")) + 1, cumulative.size)


def top_examples(records, projections, top_k):
    order = np.argsort(projections)
    def fmt(i):
        return {"row_index": int(records[i]["row_index"]), "label": records[i].get("label", ""),
                "group": records[i].get("group", ""), "score": float(projections[i]), "text": records[i]["text"]}
    return [fmt(i) for i in order[-top_k:][::-1]], [fmt(i) for i in order[:top_k]]


def build_direction_prompt(component_index, explained_ratio, pos_examples, neg_examples, llm_top_k, llm_max_chars):
    def fmt_text(text):
        text = " ".join(text.split())
        return text if len(text) <= llm_max_chars else text[:llm_max_chars - 3].rstrip() + "..."

    def fmt_examples(title, items):
        lines = [title]
        for item in items[:llm_top_k]:
            label = item.get("label") or item.get("group") or f"row {item['row_index']}"
            lines.append(f"- {label} | score={item['score']:.4f} | {fmt_text(item['text'])}")
        return "\n".join(lines)

    return (
        f"You are analyzing PCA directions over text-embedding deltas.\n"
        f"Component: PC{component_index + 1}\nExplained variance ratio: {explained_ratio:.6f}\n\n"
        "Infer the semantic or stylistic contrast captured by this direction.\n"
        "Be concrete, compare both poles, cite recurring lexical or structural cues, "
        "and state uncertainty if the axis is weak or mixed.\n\n"
        f"{fmt_examples('Positive examples', pos_examples)}\n\n"
        f"{fmt_examples('Negative examples', neg_examples)}\n\n"
        "Return 3 short sections:\n1. Axis label: a concise name.\n2. Positive pole: 2-4 sentences.\n3. Negative pole: 2-4 sentences.\n"
    )


def explain_with_llm(base_url, model, api_key, prompt, skip):
    if skip or not model:
        return None
    from openai import OpenAI
    client = OpenAI(base_url=base_url, api_key=api_key)
    resp = client.chat.completions.create(
        model=model, temperature=0,
        messages=[{"role": "user", "content": prompt}],
        timeout=90,
    )
    return (resp.choices[0].message.content or "").strip()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")


def write_pca_artifacts(output_dir, pca, retained, input_path, delta_meta, embedding_dim, mean_embedding):
    output_dir.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        pa.table({
            "component_index": list(range(retained)),
            "explained_variance": pca["explained_variance"][:retained].tolist(),
            "explained_variance_ratio": pca["explained_variance_ratio"][:retained].tolist(),
            "cumulative_explained_variance_ratio": pca["cumulative_explained_variance_ratio"][:retained].tolist(),
            "singular_value": pca["singular_values"][:retained].tolist(),
            "component": [row.astype(np.float32).tolist() for row in pca["components"][:retained]],
        }),
        output_dir / "pca_components.parquet",
    )
    pq.write_table(
        pa.table({
            "input_parquet": [str(input_path)], "delta_mode": [delta_meta["mode"]],
            "embedding_dim": [embedding_dim], "retained_component_count": [retained],
            "mean_embedding": [mean_embedding.astype(np.float32).reshape(-1).tolist()],
        }),
        output_dir / "pca_mean_embedding.parquet",
    )


def write_markdown_summary(path, summaries, summary_components, input_path, delta_meta, retained, variance_threshold):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# PCA Direction Analysis", "",
        f"- Input: `{input_path}`",
        f"- Delta mode: `{delta_meta['mode']}`",
        f"- Delta count: `{delta_meta['delta_count']}`",
        f"- Retained components: `{retained}`",
        f"- Variance threshold: `{variance_threshold:.4%}`", "",
    ]
    for s in summaries[:summary_components]:
        lines += [
            f"## PC{s.component_index + 1}", "",
            f"- Explained variance: `{s.explained_variance_ratio:.4%}`",
            f"- Cumulative variance: `{s.cumulative_explained_variance_ratio:.4%}`", "",
            "### Positive examples", "",
        ]
        for item in s.positive_examples:
            label = item.get("label") or item.get("group") or f"row {item['row_index']}"
            lines.append(f"- `{label}` ({item['score']:.4f}): {item['text']}")
        lines += ["", "### Negative examples", ""]
        for item in s.negative_examples:
            label = item.get("label") or item.get("group") or f"row {item['row_index']}"
            lines.append(f"- `{label}` ({item['score']:.4f}): {item['text']}")
        if s.llm_explanation:
            lines += ["", "### LLM explanation", "", s.llm_explanation]
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main():
    args = parse_args()
    input_path = Path(args.input_parquet)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    records, embeddings = load_records(
        input_path, args.embedding_column, args.text_column, args.label_column, args.group_column,
    )

    if args.delta_mode == "centered_rows":
        deltas, delta_meta = build_centered_row_deltas(embeddings)
    elif args.delta_mode == "group_centroids":
        deltas, delta_meta = build_group_centroid_deltas(records, embeddings)
    else:
        deltas, delta_meta = build_sampled_row_deltas(embeddings, args.max_row_pairs, args.seed)

    pca = run_pca(deltas)
    retained = n_components_for_threshold(pca["cumulative_explained_variance_ratio"], args.variance_threshold)
    centered = embeddings - embeddings.mean(axis=0, keepdims=True)

    summaries = []
    for i in range(retained):
        projections = centered @ pca["components"][i]
        pos, neg = top_examples(records, projections, args.top_k)
        prompt = build_direction_prompt(
            i, float(pca["explained_variance_ratio"][i]), pos, neg,
            args.llm_top_k, args.llm_max_text_chars,
        )
        explanation = None
        if i < args.llm_components:
            try:
                explanation = explain_with_llm(args.base_url, args.model, args.api_key, prompt, args.skip_llm)
            except Exception as e:
                explanation = f"LLM explanation failed for PC{i + 1}: {type(e).__name__}: {e}"
        summaries.append(ComponentSummary(
            component_index=i,
            explained_variance_ratio=float(pca["explained_variance_ratio"][i]),
            cumulative_explained_variance_ratio=float(pca["cumulative_explained_variance_ratio"][i]),
            positive_examples=pos, negative_examples=neg,
            llm_explanation=explanation, llm_prompt=prompt,
        ))

    write_json(output_dir / "pca_report.json", {
        "input_parquet": str(input_path),
        "record_count": len(records),
        "embedding_dim": int(embeddings.shape[1]),
        "delta_metadata": delta_meta,
        "variance_threshold": args.variance_threshold,
        "retained_component_count": retained,
        "explained_variance_ratio": pca["explained_variance_ratio"][:retained].tolist(),
        "cumulative_explained_variance_ratio": pca["cumulative_explained_variance_ratio"][:retained].tolist(),
        "components": pca["components"][:retained].tolist(),
        "component_summaries": [s._asdict() for s in summaries],
    })

    write_pca_artifacts(output_dir, pca, retained, input_path, delta_meta, int(embeddings.shape[1]),
                        embeddings.mean(axis=0, keepdims=True))
    write_markdown_summary(output_dir / "summary.md", summaries, args.summary_components,
                           input_path, delta_meta, retained, args.variance_threshold)

    print(json.dumps({
        "output_dir": str(output_dir), "record_count": len(records),
        "delta_count": delta_meta["delta_count"], "retained_component_count": retained,
        "variance_threshold": args.variance_threshold,
    }, indent=2))


if __name__ == "__main__":
    main()
