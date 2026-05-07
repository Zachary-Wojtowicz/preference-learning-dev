"""
analyze_decomposition.py — compute decomposition-quality metrics per domain.

Reports the metrics from Section "Measuring Decomposition Quality" of the
paper, for each instantiated domain (moral dilemmas, movies, wines, community
alignment). Outputs both a printable summary and a LaTeX table fragment.

For each domain we compute:
  - K                      number of LLM-discovered dimensions
  - Coverage               tr(V'CV) / tr(C), the fraction of total choice
                           variance captured by the legible subspace
  - Cov / PCA-K            Coverage divided by the PCA upper bound for K
                           dimensions (=sum of top-K eigvals of C / tr(C)).
                           This is r_K from the paper: the efficiency of V
                           relative to the optimal rank-K subspace.
  - mean Indep             mean of Indep(v_j) = 1 / ([C_hat^{-1}]_jj * C_hat_jj)
                           where C_hat = V'CV. Equals 1 when projected
                           components are uncorrelated.
  - mean basis |r|         mean off-diagonal |correlation| in the basis Gram
                           matrix V'V — how non-orthogonal the basis is.

For domains where delta_gram.bin is saved (dilemmas, movies, wines), Coverage
and Cov/PCA-K are computable. For domains where it is not (coalign_50), those
columns are reported as '—'; mean Indep and basis |r| are still computable.

Usage:
    python experiments/analyze_decomposition.py
    python experiments/analyze_decomposition.py --domains dailydilemmas wines_100
    python experiments/analyze_decomposition.py --root path/to/web-interface/outputs
"""

import argparse
import json
from pathlib import Path

import numpy as np


# Default ordering for the table; (key, display label, source-citation snippet)
DOMAIN_DISPLAY = [
    ("dailydilemmas", "Moral dilemmas",      "DailyDilemmas \\citep{scherrer2024moralchoice}"),
    ("movies_100",    "Movies",              "Curated $n{=}100$ films (TMDB)"),
    ("wines_100",     "Wines",               "Wine reviews $n{=}100$"),
    ("coalign_50",    "Community alignment", "Free-form LLM responses"),
]

DEFAULT_ROOT = Path(
    "/Users/zacharywojtowicz/Dropbox/academics/research/working/"
    "nlp/coding/preference-learning-dev/web-interface/outputs"
)

# How many dimensions to list in the "Example dims" column. The table uses
# a tabularx X column for that field, so values that wrap to 2--3 lines are
# fine and even desired.
N_EXAMPLE_DIMS = 6


# ----------------------------------------------------------------------------
def load_domain(domain_dir):
    """Load whatever artefacts are present. Returns dict with keys:
        K, dim_names, U (T x K), G_basis (K x K),
        delta_gram (T x T) or None if absent."""
    domain_dir = Path(domain_dir)

    cfg = json.loads((domain_dir / "experiment_config.json").read_text())
    dim_names = [d["name"] for d in cfg["dimensions"]]
    K_full = len(dim_names)
    G_basis_full = np.asarray(cfg["gram_matrix"], dtype=float)
    assert G_basis_full.shape == (K_full, K_full)

    tp = json.loads((domain_dir / "trial_projections.json").read_text())
    U_full = np.array([t["raw_projection"] for t in tp], dtype=float)
    # Some configs use only the top-K subset of the K_full LLM dims; the
    # raw_projection length reflects what was actually deployed.
    K = U_full.shape[1]
    if K != K_full:
        # If the deployed K is smaller, the basis Gram matrix in config still
        # describes K_full dims; clip down to the first K. (This matches the
        # convention used elsewhere in the codebase.)
        G_basis = G_basis_full[:K, :K]
        dim_names = dim_names[:K]
    else:
        G_basis = G_basis_full
    U = U_full

    # delta_gram: optional
    meta_path = domain_dir / "delta_gram_meta.json"
    bin_path  = domain_dir / "delta_gram.bin"
    delta_gram = None
    if meta_path.exists() and bin_path.exists():
        meta = json.loads(meta_path.read_text())
        T_meta = meta["n"]
        dtype  = np.dtype(meta["dtype"])
        delta_gram = np.fromfile(bin_path, dtype=dtype).reshape(T_meta, T_meta).astype(float)

    return {
        "K": K,
        "dim_names": dim_names,
        "U": U,
        "G_basis": G_basis,
        "delta_gram": delta_gram,
        "T_proj": U.shape[0],
        "T_gram": delta_gram.shape[0] if delta_gram is not None else None,
        "n_options": _count_options(domain_dir),
    }


def _count_options(domain_dir):
    """Best-effort count of the option pool size."""
    p = Path(domain_dir) / "option_projections.json"
    if not p.exists():
        return None
    try:
        return len(json.loads(p.read_text()))
    except Exception:
        return None


# ----------------------------------------------------------------------------
def center(M):
    """Double-center a Gram matrix: H M H where H = I - 11'/n."""
    n = M.shape[0]
    H = np.eye(n) - np.ones((n, n)) / n
    return H @ M @ H


def per_dim_independence(C_hat):
    """C_hat = V' C V, K x K. Returns array of Indep(v_j) values in (0, 1]."""
    K = C_hat.shape[0]
    diag = np.diag(C_hat)
    # Use pseudoinverse for numerical safety if C_hat is near-singular
    try:
        Cinv = np.linalg.inv(C_hat)
    except np.linalg.LinAlgError:
        Cinv = np.linalg.pinv(C_hat)
    return np.array([1.0 / (Cinv[j, j] * diag[j]) for j in range(K)])


def metrics_for_domain(d):
    """Compute decomposition-quality metrics. Some are returned as np.nan
    when delta_gram is missing."""
    K = d["K"]
    U = d["U"]
    G = d["delta_gram"]

    # Within-subspace covariance (always available)
    # Use ddof=0 (population) so it scales as (1/T) sum of centered ||u_t||^2.
    C_hat = np.cov(U, rowvar=False, ddof=0)
    indep_j = per_dim_independence(C_hat)
    mean_indep = float(np.mean(indep_j))

    # Mean off-diagonal correlation magnitude in the basis
    off = d["G_basis"][np.triu_indices(K, k=1)]
    mean_off_r = float(np.mean(np.abs(off)))

    # Coverage (needs delta_gram)
    if G is not None:
        Gc = center(G)
        T = G.shape[0]
        # Eigenvalues of empirical covariance C in encoder space:
        # nonzero eigvals(C) = (1/T) * nonzero eigvals(Gc)
        evals = np.linalg.eigvalsh(Gc)
        evals = np.maximum(evals, 0.0)  # numerical floor
        evals = np.sort(evals)[::-1]
        # Scale by (1/T) so traces match
        evals_C = evals / T
        tr_C = float(np.sum(evals_C))
        # Numerator: tr(V' C V) = sum of within-subspace variances (centered)
        # which is exactly tr(C_hat) computed above.
        tr_VCV = float(np.trace(C_hat))
        # PCA-K upper bound on coverage
        pca_k_bound = float(np.sum(evals_C[:K]) / tr_C) if tr_C > 0 else float("nan")
        coverage = tr_VCV / tr_C if tr_C > 0 else float("nan")
        cov_over_pcak = coverage / pca_k_bound if pca_k_bound > 0 else float("nan")
    else:
        coverage = float("nan")
        cov_over_pcak = float("nan")

    return {
        "K": K,
        "T_proj": d["T_proj"],
        "T_gram": d["T_gram"],
        "n_options": d["n_options"],
        "coverage": coverage,
        "cov_over_pcak": cov_over_pcak,
        "mean_indep": mean_indep,
        "mean_basis_off_r": mean_off_r,
        "example_dims": d["dim_names"][:N_EXAMPLE_DIMS],
    }


# ----------------------------------------------------------------------------
def fmt(v, dec=3, missing="—"):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return missing
    return f"{v:.{dec}f}"


def fmt_pct(v, dec=1, missing="—"):
    """Format a fraction in [0,1] as a percentage with `dec` decimal places.
    Returns a LaTeX-safe string with `\\%`."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return missing
    return f"{v*100:.{dec}f}\\%"


def print_summary(rows):
    print()
    print("=" * 96)
    print("DECOMPOSITION-QUALITY METRICS")
    print("=" * 96)
    hdr = (f"  {'Domain':<22s} {'K':>3s} {'T_pool':>7s} "
           f"{'Coverage':>10s} {'Cov/PCAK':>10s} {'mean Indep':>12s} "
           f"{'mean |r|':>10s}")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for label, _src, m in rows:
        print(f"  {label:<22s} {m['K']:>3d} {(m['T_gram'] or m['T_proj']):>7d} "
              f"{fmt(m['coverage']):>10s} {fmt(m['cov_over_pcak']):>10s} "
              f"{fmt(m['mean_indep']):>12s} {fmt(m['mean_basis_off_r']):>10s}")
    print()


def latex_table(rows):
    L = []
    L.append(r"\begin{table}[t]")
    L.append(r"  \centering")
    L.append(r"  \small")
    L.append(r"  \caption{Four example domains where the method was applied: "
             r"moral dilemmas \citep{scherrer2024moralchoice}, movies, wines, "
             r"and community alignment.}")
    L.append(r"  \label{tab:domains}")
    L.append(r"  % Requires \usepackage{tabularx} in the preamble.")
    L.append(r"  \begin{tabularx}{\linewidth}{@{}l c >{\raggedright\arraybackslash}X c c c@{}}")
    L.append(r"    \toprule")
    L.append(r"    Domain & $K$ & Example dimensions & "
             r"Cov. & $r_K$ & Indep. \\")
    L.append(r"    \midrule")
    for label, src, m in rows:
        examples = ", ".join(d.lower() for d in m["example_dims"]) + r", $\ldots$"
        coverage = fmt(m["coverage"])
        ratio    = fmt_pct(m["cov_over_pcak"])
        indep    = fmt(m["mean_indep"])
        L.append(f"    {label} & {m['K']} & {examples} & "
                 f"{coverage} & {ratio} & {indep} \\\\")
    L.append(r"    \bottomrule")
    L.append(r"  \end{tabularx}")
    L.append(r"\end{table}")
    return "\n".join(L)


# ----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(DEFAULT_ROOT),
                        help="Path to web-interface/outputs (root of all domain dirs).")
    parser.add_argument("--domains", nargs="+", default=None,
                        help="Subset of domain dir names. Default: all known.")
    parser.add_argument("--latex-out", default=None,
                        help="If given, write the LaTeX table fragment here.")
    args = parser.parse_args()

    root = Path(args.root)
    print(f"Root: {root}")
    if args.domains:
        wanted = list(args.domains)
        domain_specs = [(k, label, src) for (k, label, src) in DOMAIN_DISPLAY if k in wanted]
        # plus any unrecognized ones with default labels
        for k in wanted:
            if k not in [d[0] for d in domain_specs]:
                domain_specs.append((k, k.replace("_", " "), "—"))
    else:
        domain_specs = list(DOMAIN_DISPLAY)

    rows = []
    for key, label, src in domain_specs:
        ddir = root / key
        if not ddir.exists():
            print(f"  [skip] {key}: directory not found ({ddir})")
            continue
        try:
            d = load_domain(ddir)
            m = metrics_for_domain(d)
        except Exception as e:
            print(f"  [error] {key}: {e}")
            continue
        rows.append((label, src, m))

    print_summary(rows)
    tex = latex_table(rows)
    print()
    print("LaTeX TABLE FRAGMENT")
    print("-" * 96)
    print(tex)

    if args.latex_out:
        Path(args.latex_out).write_text(tex + "\n")
        print(f"\nWrote LaTeX fragment to: {args.latex_out}")


if __name__ == "__main__":
    main()
