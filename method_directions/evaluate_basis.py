"""
evaluate_basis.py — Evaluate a proposed preference basis against embeddings.

Computes three metrics from the paper (Section: Measuring Decomposition Quality):
  - Per-Dimension Variance:  Var(v_j^T delta) and cumulative ratio r_j
  - Per-Dimension Independence: fraction of projected variance not predictable from other dims
  - Coverage: total fraction of choice variance captured by the subspace

Usage:
    python method_directions/evaluate_basis.py \
        --embeddings-parquet datasets/movielens-32m-enriched-50-embedded.parquet \
        --directions method_directions/outputs/movies_50/directions.npz \
        --output-dir method_directions/outputs/movies_50 \
        --embedding-column embedding
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--embeddings-parquet", required=True,
                   help="Parquet file with an embedding column.")
    p.add_argument("--directions", required=True,
                   help="Path to directions.npz (must contain directions_ortho and mean_embedding).")
    p.add_argument("--output-dir", required=True,
                   help="Directory for output files.")
    p.add_argument("--embedding-column", default="embedding")
    p.add_argument("--dim-names", nargs="*", default=None,
                   help="Optional human-readable names for each dimension (in order).")
    p.add_argument("--bt-scores", default=None,
                   help="Optional bt_scores.csv; if provided, dimension names are read from it.")
    return p.parse_args()


def load_embeddings(path: str, col: str) -> np.ndarray:
    """Load embedding matrix from parquet. Returns (N, d) float64 array."""
    df = pd.read_parquet(path)
    if col not in df.columns:
        raise ValueError(f"Column '{col}' not in parquet. Available: {df.columns.tolist()}")
    X = np.stack(df[col].values).astype(np.float64)
    print(f"Loaded {X.shape[0]} embeddings, d={X.shape[1]}")
    return X


def load_directions(path: str):
    """Load orthonormalized directions and mean embedding from .npz."""
    data = np.load(path)
    V = data["directions_ortho"].astype(np.float64)   # (K, d)
    mu = data["mean_embedding"].astype(np.float64)     # (d,) or (1, d)
    mu = mu.ravel()
    print(f"Loaded {V.shape[0]} directions, d={V.shape[1]}")
    return V, mu


def load_dim_names(bt_scores_path: str) -> list[str]:
    """Extract ordered dimension names from bt_scores.csv."""
    df = pd.read_csv(bt_scores_path)
    names = (df[["dimension_id", "dimension_name"]]
             .drop_duplicates()
             .sort_values("dimension_id")["dimension_name"]
             .tolist())
    return names


def pca_eigenvalues(X_centered: np.ndarray) -> np.ndarray:
    """Compute eigenvalues of the choice covariance C = 2 Sigma via the SVD trick.

    Since d >> N, we compute eigenvalues of the N x N Gram matrix and scale.
    Returns eigenvalues of C in descending order.
    """
    N, d = X_centered.shape
    G = (X_centered @ X_centered.T) / N  # (N, N)
    eigvals = np.linalg.eigvalsh(G)[::-1]  # descending
    eigvals = np.clip(eigvals, 0.0, None)
    eigvals *= 2.0  # C = 2 Sigma
    return eigvals


def compute_metrics(V: np.ndarray, C_proj: np.ndarray, eigvals_C: np.ndarray):
    """Compute per-dimension variance, independence, and coverage.

    Args:
        V: (K, d) orthonormal basis
        C_proj: C_hat = V C V^T, shape (K, K)
        eigvals_C: all eigenvalues of C in descending order

    Returns:
        var_j: (K,) per-dimension variance Var(v_j^T delta) = C_hat_jj
        r_j: (K,) cumulative variance ratio
        independence: (K,) per-dimension independence
        coverage: scalar
        pca_coverage: scalar (upper bound)
    """
    K = V.shape[0]
    total_var = eigvals_C.sum()

    # --- Per-Dimension Variance ---
    # Var(v_j^T delta) = v_j^T C v_j = C_hat_jj
    var_j = np.diag(C_proj).copy()

    # Sort in descending order for cumulative ratio computation
    var_sorted = np.sort(var_j)[::-1]
    r_j = np.cumsum(var_sorted) / np.cumsum(eigvals_C[:K])
    # Clip to [0, 1] for numerical safety
    r_j = np.clip(r_j, 0.0, 1.0)

    # --- Per-Dimension Independence ---
    # Independence(v_j) = 1 / ([C_hat^{-1}]_jj * C_hat_jj)
    independence = np.zeros(K)
    try:
        C_proj_inv = np.linalg.inv(C_proj)
        for j in range(K):
            denom = C_proj_inv[j, j] * C_proj[j, j]
            independence[j] = 1.0 / denom if denom > 0 else 0.0
    except np.linalg.LinAlgError:
        independence[:] = np.nan

    # --- Coverage ---
    # Coverage(V) = tr(C_hat) / tr(C)
    coverage = np.trace(C_proj) / total_var if total_var > 0 else 0.0
    pca_coverage = eigvals_C[:K].sum() / total_var if total_var > 0 else 0.0

    return var_j, r_j, independence, coverage, pca_coverage


def generate_report(dim_names: list[str],
                    var_j: np.ndarray,
                    r_j: np.ndarray,
                    independence: np.ndarray,
                    coverage: float,
                    pca_coverage: float,
                    eigvals_C: np.ndarray,
                    C_proj: np.ndarray,
                    N: int, d: int, K: int) -> str:
    """Generate a markdown summary."""
    lines = []
    lines.append("# Preference Basis Evaluation\n")

    lines.append("## Setup\n")
    lines.append(f"- Options (N): {N}")
    lines.append(f"- Embedding dim (d): {d}")
    lines.append(f"- Basis dimensions (k): {K}")
    lines.append("")

    # Coverage
    lines.append("## Coverage\n")
    lines.append(f"- **Coverage(V)**: {coverage:.4f}")
    lines.append(f"- **PCA upper bound**: {pca_coverage:.4f}")
    lines.append(f"- **Relative coverage**: {coverage / pca_coverage:.4f}"
                 if pca_coverage > 0 else "- **Relative coverage**: N/A")
    lines.append("")

    # Per-dimension table
    # Sort dimensions by variance (descending) for the table
    order = np.argsort(var_j)[::-1]

    lines.append("## Per-Dimension Metrics\n")
    lines.append("Dimensions sorted by variance captured (descending).\n")
    lines.append("| Rank | Name | Var(v_j^T δ) | λ_j (PCA) | Independence |")
    lines.append("|------|------|--------------|-----------|--------------|")
    for rank, j in enumerate(order):
        name = dim_names[j] if j < len(dim_names) else f"Dim {j+1}"
        lines.append(
            f"| {rank+1} | {name[:35]} "
            f"| {var_j[j]:.6f} "
            f"| {eigvals_C[rank]:.6f} "
            f"| {independence[j]:.4f} |"
        )
    lines.append("")

    # Cumulative variance ratio
    lines.append("## Cumulative Variance Ratio (r_j)\n")
    lines.append("Measures how close the top-j proposed dimensions are to the top-j PCA components.\n")
    lines.append("| j | r_j | PCA cumulative variance |")
    lines.append("|---|-----|------------------------|")
    total_var = eigvals_C.sum()
    for j in range(K):
        pca_cum = eigvals_C[:j+1].sum() / total_var if total_var > 0 else 0.0
        lines.append(f"| {j+1} | {r_j[j]:.4f} | {pca_cum:.4f} |")
    lines.append("")

    # Diagnostics
    low_indep = [j for j in range(K) if not np.isnan(independence[j]) and independence[j] < 0.2]
    if low_indep:
        lines.append("## Diagnostics\n")
        names_red = [dim_names[j] if j < len(dim_names) else f"Dim {j+1}" for j in low_indep]
        lines.append(f"- **Low independence** (< 0.2): {', '.join(names_red)}")
        lines.append("")

    # Projected correlation matrix
    diag = np.sqrt(np.diag(C_proj))
    diag = np.where(diag == 0, 1, diag)
    R_hat = C_proj / np.outer(diag, diag)

    lines.append("## Projected Correlation Matrix (R̂)\n")
    short_names = [(dim_names[j] if j < len(dim_names) else f"D{j+1}")[:10] for j in range(K)]
    header = "| | " + " | ".join(short_names) + " |"
    sep = "|---|" + "|".join(["---"] * K) + "|"
    lines.append(header)
    lines.append(sep)
    for i in range(K):
        vals = " | ".join(f"{R_hat[i,j]:.2f}" for j in range(K))
        lines.append(f"| {short_names[i]} | {vals} |")
    lines.append("")

    return "\n".join(lines)


def main():
    args = parse_args()

    # Load data
    X_raw = load_embeddings(args.embeddings_parquet, args.embedding_column)
    V, mu = load_directions(args.directions)

    N, d = X_raw.shape
    K = V.shape[0]

    # Center embeddings using the mean from the directions file
    X_centered = X_raw - mu

    # Dimension names
    if args.bt_scores:
        dim_names = load_dim_names(args.bt_scores)
    elif args.dim_names:
        dim_names = args.dim_names
    else:
        dim_names = [f"Dimension {j+1}" for j in range(K)]

    # Compute projected covariance: C_hat = V C V^T
    # Efficient: C_hat_jl = 2/N * (X v_j)^T (X v_l)
    print("Computing projected covariance ...")
    Z = X_centered @ V.T  # (N, K)
    C_proj = 2.0 * (Z.T @ Z) / N  # (K, K)

    # PCA eigenvalues of C
    print("Computing PCA eigenvalues ...")
    eigvals_C = pca_eigenvalues(X_centered)

    # Metrics
    print("Computing metrics ...")
    var_j, r_j, independence, coverage, pca_coverage = compute_metrics(
        V, C_proj, eigvals_C
    )

    # Report
    report = generate_report(
        dim_names, var_j, r_j, independence, coverage, pca_coverage,
        eigvals_C, C_proj, N, d, K
    )

    # Write outputs
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report_path = out_dir / "basis_evaluation.md"
    report_path.write_text(report)
    print(f"Wrote {report_path}")

    # Save raw metrics as csv
    order = np.argsort(var_j)[::-1]
    records = []
    for rank, j in enumerate(order):
        records.append({
            "rank": rank + 1,
            "dimension": j + 1,
            "name": dim_names[j] if j < len(dim_names) else f"Dimension {j+1}",
            "variance_captured": var_j[j],
            "pca_eigenvalue": eigvals_C[rank],
            "independence": independence[j],
            "cumulative_ratio_r_j": r_j[rank],
        })
    metrics_df = pd.DataFrame(records)
    metrics_path = out_dir / "basis_metrics.csv"
    metrics_df.to_csv(metrics_path, index=False)
    print(f"Wrote {metrics_path}")

    # Print summary
    print(f"\n{'='*50}")
    print(f"Coverage(V):       {coverage:.4f}")
    print(f"PCA upper bound:   {pca_coverage:.4f}")
    print(f"Relative coverage: {coverage / pca_coverage:.4f}" if pca_coverage > 0 else "Relative coverage: N/A")
    print(f"Mean independence: {np.nanmean(independence):.4f}")
    print(f"Final r_k:         {r_j[-1]:.4f}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
