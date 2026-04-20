"""
evaluate_basis.py — Evaluate a proposed preference basis against embeddings.

Computes three metrics from the paper (Section: Measuring Decomposition Quality):
  - Per-Dimension Variance:  Var(v_j^T delta) and cumulative ratio r_j
  - Per-Dimension Independence: fraction of projected variance not predictable from other dims
  - Coverage: total fraction of choice variance captured by the subspace

Also provides a scree plot mode (--scree) that shows the PCA eigenspectrum
of the choice covariance, useful for deciding how many dimensions to target.

Usage:
    # Full basis evaluation (requires directions)
    python method_directions/evaluate_basis.py \
        --embeddings-parquet datasets/movielens-32m-enriched-50-embedded.parquet \
        --directions method_directions/outputs/movies_50/directions.npz \
        --output-dir method_directions/outputs/movies_50

    # Scree plot only (no directions needed)
    python method_directions/evaluate_basis.py --scree \
        --embeddings-parquet datasets/movielens-32m-enriched-50-embedded.parquet \
        --output-dir method_directions/outputs/movies_50
"""

import argparse
import csv
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--embeddings-parquet", required=True,
                   help="Parquet file with an embedding column.")
    p.add_argument("--embedding-column", default="embedding")
    p.add_argument("--output-dir", required=True,
                   help="Directory for output files.")
    # Scree plot mode
    p.add_argument("--scree", action="store_true",
                   help="Only compute PCA eigenspectrum and produce scree plot (no directions needed).")
    p.add_argument("--max-components", type=int, default=None,
                   help="Max number of components to show in scree plot (default: min(N-1, 50)).")
    # Full evaluation mode (requires directions)
    p.add_argument("--directions", default=None,
                   help="Path to directions.npz (required unless --scree).")
    p.add_argument("--dim-names", nargs="*", default=None,
                   help="Optional human-readable names for each dimension (in order).")
    p.add_argument("--bt-scores", default=None,
                   help="Optional bt_scores.csv; if provided, dimension names are read from it.")
    return p.parse_args()


def load_embeddings(path: str, col: str) -> np.ndarray:
    """Load embedding matrix from parquet. Returns (N, d) float64 array."""
    table = pq.read_table(path, columns=[col])
    if col not in table.column_names:
        raise ValueError(
            f"Column '{col}' not in parquet. Available: {table.column_names}"
        )
    X = np.stack(table.column(col).to_pylist()).astype(np.float64)
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
    rows = []
    with open(bt_scores_path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(row)

    rows.sort(key=lambda r: int(r["dimension_id"]))
    names = []
    seen = set()
    for row in rows:
        key = row["dimension_id"]
        if key in seen:
            continue
        seen.add(key)
        names.append(row["dimension_name"])
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


# ===================================================================
# Scree plot
# ===================================================================

def scree_plot(X_raw: np.ndarray, output_dir: Path, max_components: int | None = None):
    """Compute PCA eigenspectrum and produce a scree plot with cumulative variance.

    This answers the question: how many dimensions of meaningful variation
    exist in the choice covariance? Useful for deciding K before running
    the full pipeline.

    Args:
        X_raw: (N, d) embedding matrix
        output_dir: where to write scree_plot.png and scree_data.csv
        max_components: how many components to plot (default: min(N-1, 50))
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    N, d = X_raw.shape
    X_centered = X_raw - X_raw.mean(axis=0)

    print("Computing PCA eigenvalues ...")
    eigvals = pca_eigenvalues(X_centered)

    # Trim to meaningful range
    n_nonzero = np.sum(eigvals > 1e-10)
    max_k = max_components or min(n_nonzero, 50)
    eigvals_plot = eigvals[:max_k]
    total_var = eigvals.sum()

    # Cumulative variance explained
    cum_var = np.cumsum(eigvals_plot) / total_var
    # Individual fraction
    ind_var = eigvals_plot / total_var

    # --- Write CSV ---
    csv_path = output_dir / "scree_data.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["component", "eigenvalue", "variance_fraction",
                         "cumulative_variance"])
        for j in range(max_k):
            writer.writerow([j + 1, eigvals_plot[j], ind_var[j], cum_var[j]])
    print(f"Wrote {csv_path}")

    # --- Find key thresholds ---
    thresholds = [0.50, 0.75, 0.90, 0.95, 0.99]
    threshold_components = {}
    for t in thresholds:
        idx = np.searchsorted(cum_var, t)
        threshold_components[t] = int(idx + 1) if idx < len(cum_var) else f">{max_k}"

    # --- Plot ---
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    components = np.arange(1, max_k + 1)

    # Left panel: individual eigenvalues (log scale)
    ax1.bar(components, ind_var, color="#3498db", alpha=0.7, width=0.8)
    ax1.set_xlabel("Principal Component", fontsize=12)
    ax1.set_ylabel("Fraction of Total Variance", fontsize=12)
    ax1.set_title("Individual Variance per Component", fontsize=13, fontweight="bold")
    ax1.set_yscale("log")
    ax1.set_xlim(0.5, max_k + 0.5)
    ax1.grid(True, alpha=0.3, axis="y")

    # Right panel: cumulative variance
    ax2.plot(components, cum_var, color="#2ecc71", linewidth=2.5, marker="o",
             markersize=4, zorder=3)
    ax2.set_xlabel("Number of Components (k)", fontsize=12)
    ax2.set_ylabel("Cumulative Variance Explained", fontsize=12)
    ax2.set_title("Cumulative Variance Explained", fontsize=13, fontweight="bold")
    ax2.set_xlim(0.5, max_k + 0.5)
    ax2.set_ylim(0, 1.05)
    ax2.grid(True, alpha=0.3)

    # Add threshold lines
    colors_t = ["#e74c3c", "#e67e22", "#9b59b6", "#1abc9c", "#34495e"]
    for (t, k), color in zip(threshold_components.items(), colors_t):
        label = f"{t:.0%} → k={k}"
        ax2.axhline(t, color=color, linestyle="--", alpha=0.5, linewidth=1)
        if isinstance(k, int) and k <= max_k:
            ax2.axvline(k, color=color, linestyle=":", alpha=0.4, linewidth=1)
        ax2.annotate(label, xy=(max_k * 0.65, t + 0.01), fontsize=9, color=color)

    fig.suptitle(f"PCA Scree Analysis — Choice Covariance (N={N}, d={d})",
                 fontsize=14, fontweight="bold")
    plt.tight_layout()

    plot_path = output_dir / "scree_plot.png"
    plt.savefig(plot_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Wrote {plot_path}")

    # --- Print summary ---
    print(f"\n{'='*55}")
    print(f"  N = {N} options, d = {d} embedding dimensions")
    print(f"  Non-zero eigenvalues: {n_nonzero}")
    print(f"  Total choice variance: {total_var:.4f}")
    print(f"")
    print(f"  Components needed for cumulative variance threshold:")
    for t, k in threshold_components.items():
        print(f"    {t:>5.0%}  →  k = {k}")
    print(f"")
    print(f"  First 10 components capture: {cum_var[min(9, max_k-1)]:.1%}")
    if max_k >= 20:
        print(f"  First 20 components capture: {cum_var[min(19, max_k-1)]:.1%}")
    if max_k >= 30:
        print(f"  First 30 components capture: {cum_var[min(29, max_k-1)]:.1%}")
    print(f"{'='*55}")

    return eigvals, cum_var, threshold_components


# ===================================================================
# Basis evaluation metrics
# ===================================================================

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
    var_j = np.diag(C_proj).copy()

    # Sort in descending order for cumulative ratio computation
    var_sorted = np.sort(var_j)[::-1]
    r_j = np.cumsum(var_sorted) / np.cumsum(eigvals_C[:K])
    r_j = np.clip(r_j, 0.0, 1.0)

    # --- Per-Dimension Independence ---
    independence = np.zeros(K)
    try:
        C_proj_inv = np.linalg.inv(C_proj)
        for j in range(K):
            denom = C_proj_inv[j, j] * C_proj[j, j]
            independence[j] = 1.0 / denom if denom > 0 else 0.0
    except np.linalg.LinAlgError:
        independence[:] = np.nan

    # --- Coverage ---
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
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load embeddings (needed for both modes)
    X_raw = load_embeddings(args.embeddings_parquet, args.embedding_column)

    # --- Scree plot mode ---
    if args.scree:
        scree_plot(X_raw, out_dir, max_components=args.max_components)
        return

    # --- Full evaluation mode ---
    if not args.directions:
        raise ValueError("--directions is required unless --scree is set.")

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

    metrics_path = out_dir / "basis_metrics.csv"
    with open(metrics_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)
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
