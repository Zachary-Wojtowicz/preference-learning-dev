#!/usr/bin/env python3
import csv
import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, top_k_accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[1]
DELTA_PARQUET = ROOT / "datasets" / "matrix_deltas_204x1000.parquet"
RESULTS_DIR = ROOT / "mapping" / "results"
METRICS_JSON = RESULTS_DIR / "logistic_probe_metrics.json"
DETAILS_CSV = RESULTS_DIR / "logistic_probe_top5_details.csv"

TEST_SIZE = 0.2
RANDOM_STATE = 42
MAX_ITER = 3000
TOP1_REWARD = 2.0
TOP5_REWARD = 0.5
MISS_TOP5_PENALTY = -1.0


def main() -> None:
    table = pq.read_table(DELTA_PARQUET, columns=["style_name", "delta_embedding"])
    df = table.to_pandas()
    x = np.vstack(df["delta_embedding"].to_numpy()).astype(np.float32)
    y_text = df["style_name"].astype(str).to_numpy()

    encoder = LabelEncoder()
    y = encoder.fit_transform(y_text)
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y,
    )

    clf = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=MAX_ITER, n_jobs=-1, verbose=0),
    )
    clf.fit(x_train, y_train)

    prob = clf.predict_proba(x_test)
    pred = np.argmax(prob, axis=1)
    top5_idx = np.argsort(-prob, axis=1)[:, :5]
    top5_hit = np.any(top5_idx == y_test[:, None], axis=1)
    top1_hit = pred == y_test
    weighted_scores = np.where(
        top1_hit,
        TOP1_REWARD,
        np.where(top5_hit, TOP5_REWARD, MISS_TOP5_PENALTY),
    ).astype(np.float32)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with DETAILS_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "row_id",
                "true_style",
                "pred_top1_style",
                "pred_top1_prob",
                "top1_hit",
                "top5_hit",
                "weighted_score",
                "top5_styles",
                "top5_probs",
            ],
        )
        writer.writeheader()
        for i in range(len(y_test)):
            ranked_styles = encoder.inverse_transform(top5_idx[i])
            ranked_probs = [float(prob[i, j]) for j in top5_idx[i]]
            writer.writerow(
                {
                    "row_id": i,
                    "true_style": encoder.inverse_transform([y_test[i]])[0],
                    "pred_top1_style": encoder.inverse_transform([pred[i]])[0],
                    "pred_top1_prob": f"{float(prob[i, pred[i]]):.8f}",
                    "top1_hit": int(top1_hit[i]),
                    "top5_hit": int(top5_hit[i]),
                    "weighted_score": f"{float(weighted_scores[i]):.8f}",
                    "top5_styles": " | ".join(ranked_styles.tolist()),
                    "top5_probs": " | ".join(f"{p:.8f}" for p in ranked_probs),
                }
            )

    metrics = {
        "delta_parquet": str(DELTA_PARQUET),
        "n_samples": int(x.shape[0]),
        "n_classes": int(len(encoder.classes_)),
        "random_chance_accuracy": float(1.0 / len(encoder.classes_)),
        "test_size": TEST_SIZE,
        "random_state": RANDOM_STATE,
        "test_accuracy": float(accuracy_score(y_test, pred)),
        "test_balanced_accuracy": float(balanced_accuracy_score(y_test, pred)),
        "test_top3_accuracy": float(
            top_k_accuracy_score(y_test, prob, k=3, labels=np.arange(len(encoder.classes_)))
        ),
        "test_top5_accuracy": float(
            top_k_accuracy_score(y_test, prob, k=5, labels=np.arange(len(encoder.classes_)))
        ),
        "weighted_score_mean": float(np.mean(weighted_scores)),
        "weighted_score_sum": float(np.sum(weighted_scores)),
        "top1_reward": TOP1_REWARD,
        "top5_reward": TOP5_REWARD,
        "miss_top5_penalty": MISS_TOP5_PENALTY,
        "n_top1_hits": int(np.sum(top1_hit)),
        "n_top5_hits": int(np.sum(top5_hit)),
        "n_miss_top5": int(np.sum(~top5_hit)),
        "details_csv": str(DETAILS_CSV),
    }

    METRICS_JSON.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
