"""
find_directions.py — Find preference direction vectors in embedding space.

For each LLM-generated dimension k, fits a ridge regression to find a
direction vector vk in embedding space such that <vk, φ(ai)> ≈ btl_score_k(ai).
"""

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import train_test_split


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--embeddings-parquet", required=True,
                   help="Path to parquet file with embedding column and option-id column.")
    p.add_argument("--bt-scores", required=True,
                   help="Path to bt_scores.csv with columns dimension_id, dimension_name, option_id, display_text, bt_score.")
    p.add_argument("--embedding-column", default="embedding",
                   help="Name of the embedding column in the parquet file (default: embedding).")
    p.add_argument("--option-id-column", default="option_id",
                   help="Name of the option-id column in the parquet file (default: option_id).")
    p.add_argument("--output-dir", required=True,
                   help="Directory where outputs will be written.")
    p.add_argument("--contrastive-m", type=int, default=None,
                   help="Number of top/bottom options for contrastive direction (default: max(5, N//10)).")
    p.add_argument("--test-fraction", type=float, default=0.2,
                   help="Fraction of options held out for test evaluation (default: 0.2).")
    p.add_argument("--seed", type=int, default=42,
                   help="Random seed (default: 42).")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data(embeddings_parquet: str, bt_scores_csv: str,
              embedding_col: str, option_id_col: str):
    print(f"Loading embeddings from {embeddings_parquet} ...")
    emb_df = pd.read_parquet(embeddings_parquet)

    if option_id_col not in emb_df.columns:
        available = emb_df.columns.tolist()
        raise ValueError(
            f"Column '{option_id_col}' not found in parquet. Available: {available}\n"
            f"Use --option-id-column to specify the correct column name."
        )
    if embedding_col not in emb_df.columns:
        raise ValueError(f"Embedding column '{embedding_col}' not found in parquet.")

    emb_df = emb_df[[option_id_col, embedding_col]].rename(
        columns={option_id_col: "option_id", embedding_col: "embedding"}
    )
    # Deduplicate on option_id (keep first)
    emb_df = emb_df.drop_duplicates(subset="option_id")

    print(f"Loading BT scores from {bt_scores_csv} ...")
    scores_df = pd.read_csv(bt_scores_csv)
    required_cols = {"dimension_id", "dimension_name", "option_id", "bt_score"}
    missing = required_cols - set(scores_df.columns)
    if missing:
        raise ValueError(f"bt_scores CSV missing columns: {missing}")

    # Align types: cast option_id to str in both for robust joining
    emb_df["option_id"] = emb_df["option_id"].astype(str)
    scores_df["option_id"] = scores_df["option_id"].astype(str)

    # Pivot scores to wide format: rows=option_id, cols=dimension
    pivot = scores_df.pivot_table(
        index="option_id", columns="dimension_id", values="bt_score", aggfunc="first"
    )
    dim_meta = (
        scores_df[["dimension_id", "dimension_name"]]
        .drop_duplicates()
        .set_index("dimension_id")
    )
    display_text = (
        scores_df[["option_id", "display_text"]]
        .drop_duplicates(subset="option_id")
        .set_index("option_id")
    )

    # Join embeddings onto pivot
    joined = emb_df.set_index("option_id").join(pivot, how="inner")
    only_emb = len(emb_df) - len(joined)
    only_scores = len(pivot) - len(joined)
    if only_emb or only_scores:
        print(f"  Dropped {only_emb} options (in embeddings only) and "
              f"{only_scores} options (in scores only) after inner join.")

    n_options = len(joined)
    dim_ids = sorted(dim_meta.index.tolist())
    n_dims = len(dim_ids)

    if n_options == 0:
        raise ValueError("No options remaining after join. Check that option_id values match between files.")

    print(f"  {n_options} options × {n_dims} dimensions after join.")

    # Build embedding matrix
    X_raw = np.stack(joined["embedding"].values).astype(np.float64)
    emb_dim = X_raw.shape[1]
    print(f"  Embedding dimensionality: {emb_dim}")

    # Build score matrix (N × K)
    Y = joined[dim_ids].values.astype(np.float64)

    # Display texts
    texts = joined.index.map(lambda x: display_text.loc[x, "display_text"] if x in display_text.index else x)

    return X_raw, Y, dim_ids, dim_meta, texts.tolist(), joined.index.tolist()


# ---------------------------------------------------------------------------
# Step 1 — Ridge regression
# ---------------------------------------------------------------------------

ALPHAS = [0.01, 0.1, 1, 10, 100, 1000]


def fit_ridge(X_centered: np.ndarray, Y: np.ndarray):
    """Fit RidgeCV for each dimension. Returns (directions, best_alphas, r2_insample, r2_cv)."""
    N, d = X_centered.shape
    K = Y.shape[1]
    directions = np.zeros((K, d))
    best_alphas = np.zeros(K)
    r2_insample = np.zeros(K)
    r2_cv = np.zeros(K)

    for k in range(K):
        y = Y[:, k]
        # RidgeCV with leave-one-out (store_cv_results for CV R² computation).
        # 'store_cv_results' was called 'store_cv_values' before sklearn 1.4.
        try:
            model = RidgeCV(alphas=ALPHAS, store_cv_results=True)
        except TypeError:
            model = RidgeCV(alphas=ALPHAS, store_cv_values=True)
        model.fit(X_centered, y)

        directions[k] = model.coef_
        best_alphas[k] = model.alpha_

        # In-sample R²
        y_pred_insample = model.predict(X_centered)
        ss_res = np.sum((y - y_pred_insample) ** 2)
        ss_tot = np.sum((y - y.mean()) ** 2)
        r2_insample[k] = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

        # CV R²: cv_results_ / cv_values_ stores LOO residuals (y - y_hat_loo)
        # shape (N, len(alphas)) — one column per alpha value.
        cv_array = (getattr(model, "cv_results_", None)
                    if hasattr(model, "cv_results_")
                    else getattr(model, "cv_values_"))
        alpha_idx = np.argmin(np.abs(np.array(ALPHAS) - model.alpha_))
        loo_errors = cv_array[:, alpha_idx]  # shape (N,)
        ss_res_cv = np.sum(loo_errors ** 2)
        r2_cv[k] = 1 - ss_res_cv / ss_tot if ss_tot > 0 else 0.0

    return directions, best_alphas, r2_insample, r2_cv


# ---------------------------------------------------------------------------
# Step 2 — Contrastive mean difference
# ---------------------------------------------------------------------------

def contrastive_directions(X_raw: np.ndarray, Y: np.ndarray, M: int):
    """Compute contrastive direction vectors and cosine sim vs. ridge."""
    K = Y.shape[1]
    N = X_raw.shape[0]
    M = min(M, N // 2)
    contrastive = np.zeros((K, X_raw.shape[1]))

    for k in range(K):
        y = Y[:, k]
        order = np.argsort(y)
        bottom_idx = order[:M]
        top_idx = order[-M:]
        v = X_raw[top_idx].mean(axis=0) - X_raw[bottom_idx].mean(axis=0)
        norm = np.linalg.norm(v)
        contrastive[k] = v / norm if norm > 0 else v

    return contrastive


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


# ---------------------------------------------------------------------------
# Step 3 — Held-out evaluation
# ---------------------------------------------------------------------------

def heldout_evaluation(X_centered: np.ndarray, Y: np.ndarray,
                       test_fraction: float, seed: int):
    """Train/test split per dimension, return (r2, pearson, spearman) arrays."""
    K = Y.shape[1]
    r2 = np.zeros(K)
    pearson = np.zeros(K)
    spearman = np.zeros(K)

    X_train, X_test, Y_train, Y_test = train_test_split(
        X_centered, Y, test_size=test_fraction, random_state=seed
    )

    for k in range(K):
        y_train = Y_train[:, k]
        y_test = Y_test[:, k]

        model = RidgeCV(alphas=ALPHAS)
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        ss_res = np.sum((y_test - y_pred) ** 2)
        ss_tot = np.sum((y_test - y_test.mean()) ** 2)
        r2[k] = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

        if len(y_test) > 1:
            pearson[k] = pearsonr(y_pred, y_test)[0]
            spearman[k] = spearmanr(y_pred, y_test)[0]
        else:
            pearson[k] = np.nan
            spearman[k] = np.nan

    return r2, pearson, spearman


# ---------------------------------------------------------------------------
# Step 4 — Orthogonalize
# ---------------------------------------------------------------------------

def orthogonalize(directions: np.ndarray):
    """QR decomposition to orthonormalize direction vectors (K × d)."""
    K, d = directions.shape
    # Q is (d × K) after QR of directions.T
    Q, R = np.linalg.qr(directions.T, mode="reduced")
    # Q has shape (d, K), columns are orthonormal
    ortho = Q.T  # (K, d)

    # Fix sign: make sure each orthogonalized vector points the same way as original
    for k in range(K):
        if np.dot(directions[k], ortho[k]) < 0:
            ortho[k] = -ortho[k]

    cosines = np.array([cosine_sim(directions[k], ortho[k]) for k in range(K)])
    return ortho, cosines


# ---------------------------------------------------------------------------
# Summary generation
# ---------------------------------------------------------------------------

def generate_summary(
    eval_df: pd.DataFrame,
    n_options: int,
    n_dims: int,
    emb_dim: int,
    X_centered: np.ndarray,
    directions: np.ndarray,
    mean_emb: np.ndarray,
    option_texts: list,
    Y: np.ndarray,
    dim_meta,
) -> str:
    lines = []
    lines.append("# Direction Vectors: Evaluation Summary\n")
    lines.append("## Overall Statistics\n")
    lines.append(f"- Options: {n_options}")
    lines.append(f"- Dimensions: {n_dims}")
    lines.append(f"- Embedding dimensionality: {emb_dim}")
    lines.append(f"- Average held-out R²: {eval_df['r2_heldout'].mean():.4f}")
    lines.append(f"- Average held-out Pearson r: {eval_df['pearson_heldout'].mean():.4f}")
    lines.append(f"- Average held-out Spearman ρ: {eval_df['spearman_heldout'].mean():.4f}")
    lines.append("")

    # Flags
    unreliable = eval_df[
        (eval_df["cosine_ridge_vs_contrastive"] < 0.5) | (eval_df["r2_heldout"] < 0.1)
    ]
    if len(unreliable):
        lines.append("## ⚠ Unreliable Dimensions\n")
        for _, row in unreliable.iterrows():
            reasons = []
            if row["cosine_ridge_vs_contrastive"] < 0.5:
                reasons.append(f"cosine(ridge, contrastive)={row['cosine_ridge_vs_contrastive']:.3f} < 0.5")
            if row["r2_heldout"] < 0.1:
                reasons.append(f"R²_heldout={row['r2_heldout']:.3f} < 0.1")
            lines.append(f"- **{row['dimension_name']}** (dim {row['dimension_id']}): {'; '.join(reasons)}")
        lines.append("")

    lines.append("## Per-Dimension Metrics\n")
    header = (
        "| Dim | Name | alpha | R²_in | R²_cv | R²_held | Pearson | Spearman "
        "| cos(ridge,contrast) | cos(pre,post_orth) |"
    )
    sep = (
        "|-----|------|-------|-------|-------|---------|---------|----------|"
        "---------------------|-------------------|"
    )
    lines.append(header)
    lines.append(sep)
    for _, row in eval_df.iterrows():
        lines.append(
            f"| {row['dimension_id']} | {row['dimension_name'][:30]} "
            f"| {row['ridge_alpha']:.2g} "
            f"| {row['r2_insample']:.3f} "
            f"| {row['r2_cv']:.3f} "
            f"| {row['r2_heldout']:.3f} "
            f"| {row['pearson_heldout']:.3f} "
            f"| {row['spearman_heldout']:.3f} "
            f"| {row['cosine_ridge_vs_contrastive']:.3f} "
            f"| {row['cosine_pre_vs_post_orthogonalization']:.3f} |"
        )
    lines.append("")

    lines.append("## Top/Bottom Options Per Dimension (by Predicted Score)\n")
    for k, dim_id in enumerate(eval_df["dimension_id"].tolist()):
        dim_name = dim_meta.loc[dim_id, "dimension_name"]
        v = directions[k]  # already mean-centered direction
        predicted = X_centered @ v
        order = np.argsort(predicted)
        true_scores = Y[:, k]

        lines.append(f"### {dim_name} (dim {dim_id})\n")
        lines.append("**Top 3 (highest predicted score):**\n")
        lines.append("| Option | Predicted | Actual BTL |")
        lines.append("|--------|-----------|------------|")
        for idx in order[-3:][::-1]:
            lines.append(f"| {str(option_texts[idx])[:60]} | {predicted[idx]:.4f} | {true_scores[idx]:.4f} |")
        lines.append("")
        lines.append("**Bottom 3 (lowest predicted score):**\n")
        lines.append("| Option | Predicted | Actual BTL |")
        lines.append("|--------|-----------|------------|")
        for idx in order[:3]:
            lines.append(f"| {str(option_texts[idx])[:60]} | {predicted[idx]:.4f} | {true_scores[idx]:.4f} |")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()
    rng = np.random.default_rng(args.seed)

    # --- Step 0: Load and join ---
    X_raw, Y, dim_ids, dim_meta, option_texts, option_ids = load_data(
        args.embeddings_parquet,
        args.bt_scores,
        args.embedding_column,
        args.option_id_column,
    )
    N, d = X_raw.shape
    K = Y.shape[1]

    mean_emb = X_raw.mean(axis=0)
    X_centered = X_raw - mean_emb

    M = args.contrastive_m if args.contrastive_m is not None else max(5, N // 10)
    print(f"Contrastive M = {M}")

    # --- Step 1: Ridge regression ---
    print("Step 1: Fitting ridge regression per dimension ...")
    directions, best_alphas, r2_insample, r2_cv = fit_ridge(X_centered, Y)

    # --- Step 2: Contrastive directions ---
    print("Step 2: Computing contrastive directions ...")
    contrastive = contrastive_directions(X_raw, Y, M)

    # Normalize ridge directions for cosine comparison
    ridge_norms = np.linalg.norm(directions, axis=1, keepdims=True)
    ridge_norms = np.where(ridge_norms == 0, 1, ridge_norms)
    directions_normed = directions / ridge_norms

    cosine_rc = np.array([cosine_sim(directions_normed[k], contrastive[k]) for k in range(K)])

    # --- Step 3: Held-out evaluation ---
    print("Step 3: Held-out evaluation ...")
    r2_heldout, pearson_heldout, spearman_heldout = heldout_evaluation(
        X_centered, Y, args.test_fraction, args.seed
    )

    # --- Step 4: Orthogonalize ---
    print("Step 4: Orthogonalizing direction vectors ...")
    directions_ortho, cosine_orth = orthogonalize(directions)

    # --- Build evaluation dataframe ---
    eval_records = []
    for k, dim_id in enumerate(dim_ids):
        eval_records.append({
            "dimension_id": dim_id,
            "dimension_name": dim_meta.loc[dim_id, "dimension_name"],
            "ridge_alpha": best_alphas[k],
            "r2_insample": r2_insample[k],
            "r2_cv": r2_cv[k],
            "r2_heldout": r2_heldout[k],
            "pearson_heldout": pearson_heldout[k],
            "spearman_heldout": spearman_heldout[k],
            "cosine_ridge_vs_contrastive": cosine_rc[k],
            "cosine_pre_vs_post_orthogonalization": cosine_orth[k],
        })
    eval_df = pd.DataFrame(eval_records)

    print("\n=== Summary ===")
    print(eval_df[["dimension_name", "ridge_alpha", "r2_insample", "r2_cv",
                   "r2_heldout", "pearson_heldout", "spearman_heldout"]].to_string(index=False))
    print(f"\nAverage held-out R²: {eval_df['r2_heldout'].mean():.4f}")

    # --- Write outputs ---
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    npz_path = output_dir / "directions.npz"
    np.savez(
        npz_path,
        directions_raw=directions,
        directions_ortho=directions_ortho,
        mean_embedding=mean_emb,
        best_alphas=best_alphas,
    )
    print(f"Saved {npz_path}")

    eval_path = output_dir / "evaluation.csv"
    eval_df.to_csv(eval_path, index=False)
    print(f"Saved {eval_path}")

    summary_md = generate_summary(
        eval_df, N, K, d, X_centered, directions, mean_emb,
        option_texts, Y, dim_meta
    )
    summary_path = output_dir / "summary.md"
    summary_path.write_text(summary_md)
    print(f"Saved {summary_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()
