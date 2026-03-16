#!/usr/bin/env python3
import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
DESCRIPTION_EMBEDDINGS_PARQUET = ROOT / "datasets" / "description_embeddings_qwen05b.parquet"
DELTA_PARQUET = ROOT / "datasets" / "matrix_deltas_204x1000.parquet"
RESULTS_DIR = ROOT / "mapping" / "results"
METRICS_JSON = RESULTS_DIR / "description_to_delta_metrics.json"

TEST_SIZE = 0.2
RANDOM_STATE = 42
RIDGE_ALPHA = 1.0


def l2_normalize(x: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return x / norms


def load_style_centroids() -> dict[str, np.ndarray]:
    table = pq.read_table(DELTA_PARQUET, columns=["style_name", "delta_embedding"])
    df = table.to_pandas()
    centroids: dict[str, np.ndarray] = {}
    for style_name in sorted(df["style_name"].unique()):
        style_rows = df[df["style_name"] == style_name]["delta_embedding"].to_numpy()
        centroids[str(style_name)] = np.vstack(style_rows).astype(np.float32).mean(axis=0)
    return centroids


def load_description_embeddings() -> tuple[np.ndarray, np.ndarray]:
    table = pq.read_table(
        DESCRIPTION_EMBEDDINGS_PARQUET,
        columns=["style_name", "embedding"],
    )
    df = table.to_pandas()
    return (
        np.vstack(df["embedding"].to_numpy()).astype(np.float32),
        df["style_name"].astype(str).to_numpy(),
    )


def main() -> None:
    centroids = load_style_centroids()
    x, groups = load_description_embeddings()

    keep = np.array([style_name in centroids for style_name in groups], dtype=bool)
    x = x[keep]
    groups = groups[keep]
    y = np.vstack([centroids[style_name] for style_name in groups]).astype(np.float32)

    splitter = GroupShuffleSplit(
        n_splits=1,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
    )
    train_idx, test_idx = next(splitter.split(x, y, groups=groups))

    model = Pipeline(
        [("scaler", StandardScaler()), ("ridge", Ridge(alpha=RIDGE_ALPHA))]
    )
    model.fit(x[train_idx], y[train_idx])
    pred = model.predict(x[test_idx]).astype(np.float32)

    pred_n = l2_normalize(pred)
    true_n = l2_normalize(y[test_idx])
    cosine_to_true = (pred_n * true_n).sum(axis=1)

    style_bank_names = sorted(centroids)
    style_bank = np.vstack([centroids[name] for name in style_bank_names]).astype(np.float32)
    style_bank_n = l2_normalize(style_bank)
    sims = pred_n @ style_bank_n.T
    true_idx = np.array([style_bank_names.index(style_name) for style_name in groups[test_idx]])
    pred_idx = np.argmax(sims, axis=1)
    top3_hits = [true_idx[i] in np.argsort(-sims[i])[:3] for i in range(len(true_idx))]

    metrics = {
        "description_embeddings_parquet": str(DESCRIPTION_EMBEDDINGS_PARQUET),
        "delta_parquet": str(DELTA_PARQUET),
        "n_total_descriptions": int(len(groups)),
        "n_train_descriptions": int(len(train_idx)),
        "n_test_descriptions": int(len(test_idx)),
        "n_styles": int(len(style_bank_names)),
        "heldout_styles": sorted(set(groups[test_idx].tolist())),
        "mean_cosine_to_true_centroid": float(np.mean(cosine_to_true)),
        "style_retrieval_top1": float(np.mean(pred_idx == true_idx)),
        "style_retrieval_top3": float(np.mean(top3_hits)),
        "test_size": TEST_SIZE,
        "random_state": RANDOM_STATE,
        "alpha": RIDGE_ALPHA,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    METRICS_JSON.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
