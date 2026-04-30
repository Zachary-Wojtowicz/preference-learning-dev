"""
Fast direction extraction from pre-computed Qwen2.5-32B mean-pool embeddings.
Produces multiple .pt files — one per method — for use with train.py --directions.

Methods:
  contrast  : SVD of class-discriminant contrast matrix (insecure vs secure)
  pca       : Top-K PCA components of all embeddings
  both      : Runs both (default)

Usage:
  python em_experiment/extract_directions_fast.py \
      --embeddings datasets/em_code_30d/em_code_30d-qwen32b-embedded.parquet \
      --k 30 --method both
"""
import argparse, torch, numpy as np, pandas as pd
from pathlib import Path

BASE = Path('/raid/lingo/ayushn/pref-learn')
OUTDIR = BASE / 'em_experiment'


METHODS = ['contrast', 'pca', 'logistic', 'ica', 'svm', 'meandiff', 'both', 'all']

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--embeddings', required=True)
    p.add_argument('--k', type=int, default=30)
    p.add_argument('--method', default='both', choices=METHODS)
    p.add_argument('--bad_label',  default='insecure',
                   help='Category value for misaligned class')
    p.add_argument('--good_label', default='secure',
                   help='Category value for aligned class')
    p.add_argument('--suffix', default='', help='Extra suffix for output filenames')
    return p.parse_args()


def randomized_svd_top(M, k):
    try:
        from sklearn.utils.extmath import randomized_svd
        _, _, Vt = randomized_svd(M, n_components=k, random_state=0, n_iter=4)
    except Exception:
        _, _, Vt = np.linalg.svd(M, full_matrices=False)
        Vt = Vt[:k]
    return Vt.T  # (d, k)


def contrast_directions(X, labels, bad_label, good_label, k):
    """SVD of class-discriminant contrast matrix."""
    is_bad  = np.array([l == bad_label  for l in labels])
    is_good = np.array([l == good_label for l in labels])

    if is_bad.sum() == 0 or is_good.sum() == 0:
        raise ValueError(f"Labels found: {set(labels)}. Check --bad_label / --good_label.")

    mu_bad  = X[is_bad].mean(0)
    mu_good = X[is_good].mean(0)
    mu_diff = mu_bad - mu_good

    print(f"  n_bad={is_bad.sum()}, n_good={is_good.sum()}")
    print(f"  |mu_bad - mu_good| = {np.linalg.norm(mu_diff):.4f}")

    X_bad_c  = X[is_bad]  - mu_bad
    X_good_c = X[is_good] - mu_good
    scale = float(np.sqrt(max(is_bad.sum(), is_good.sum())))

    C = np.vstack([X_bad_c, X_good_c, mu_diff.reshape(1, -1) * scale])
    print(f"  SVD of contrast matrix {C.shape} ...")
    V = randomized_svd_top(C, k)

    # Orient: first direction points from good → bad
    for i in range(k):
        if np.dot(mu_diff, V[:, i]) < 0:
            V[:, i] = -V[:, i]

    err = np.max(np.abs(V.T @ V - np.eye(k)))
    print(f"  Orthonormality error: {err:.2e}")

    cohen_d = (X[is_bad] @ V).mean(0) - (X[is_good] @ V).mean(0)
    pooled_std = ((X[is_bad] @ V).std(0) + (X[is_good] @ V).std(0)) / 2 + 1e-8
    sep = cohen_d / pooled_std
    print(f"  Top-5 Cohen's d: {sep[:5].tolist()}")
    return V.astype(np.float32), sep


def pca_directions(X, k):
    """Top-K PCA components of centered embeddings."""
    mu = X.mean(0)
    X_c = X - mu
    print(f"  PCA of {X_c.shape} ...")
    V = randomized_svd_top(X_c, k)
    err = np.max(np.abs(V.T @ V - np.eye(k)))
    print(f"  Orthonormality error: {err:.2e}")
    return V.astype(np.float32), mu.astype(np.float32)


def logistic_directions(X, labels, bad_label, good_label, k):
    """Logistic regression weight vector as primary direction, padded with PCA of residuals."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler as SS
    y = np.array([1 if l == bad_label else 0 for l in labels])
    Xs = SS().fit_transform(X)
    clf = LogisticRegression(C=1.0, max_iter=1000, solver='lbfgs').fit(Xs, y)
    w = clf.coef_[0]  # (d,)
    w = w / (np.linalg.norm(w) + 1e-8)
    print(f"  Logistic accuracy: {clf.score(Xs, y):.3f}")

    # Fill remaining k-1 dims with PCA of residuals orthogonal to w
    proj = X - (X @ w)[:, None] * w
    _, _, Vt = np.linalg.svd(proj - proj.mean(0), full_matrices=False)
    V_rest = Vt[:k-1].T  # (d, k-1)

    V = np.hstack([w[:, None], V_rest])  # (d, k)
    # Re-orthonormalize
    V, _ = np.linalg.qr(V)
    # Orient first col toward bad
    mu_diff = X[np.array([l == bad_label for l in labels])].mean(0) - \
              X[np.array([l == good_label for l in labels])].mean(0)
    if np.dot(mu_diff, V[:, 0]) < 0:
        V[:, 0] = -V[:, 0]
    err = np.max(np.abs(V.T @ V - np.eye(k)))
    print(f"  Orthonormality error: {err:.2e}")
    return V.astype(np.float32)


def svm_directions(X, labels, bad_label, good_label, k):
    """Linear SVM weight vector (max-margin) as primary direction, padded with PCA of residuals."""
    from sklearn.svm import LinearSVC
    from sklearn.preprocessing import StandardScaler as SS
    y = np.array([1 if l == bad_label else 0 for l in labels])
    Xs = SS().fit_transform(X)
    clf = LinearSVC(C=1.0, max_iter=2000).fit(Xs, y)
    w = clf.coef_[0]
    w = w / (np.linalg.norm(w) + 1e-8)
    print(f"  SVM accuracy: {clf.score(Xs, y):.3f}")

    proj = X - (X @ w)[:, None] * w
    _, _, Vt = np.linalg.svd(proj - proj.mean(0), full_matrices=False)
    V_rest = Vt[:k-1].T
    V = np.hstack([w[:, None], V_rest])
    V, _ = np.linalg.qr(V)
    mu_diff = X[np.array([l == bad_label for l in labels])].mean(0) - \
              X[np.array([l == good_label for l in labels])].mean(0)
    if np.dot(mu_diff, V[:, 0]) < 0:
        V[:, 0] = -V[:, 0]
    err = np.max(np.abs(V.T @ V - np.eye(k)))
    print(f"  Orthonormality error: {err:.2e}")
    return V.astype(np.float32)


def meandiff_directions(X, labels, bad_label, good_label):
    """Single normalized mean-difference direction (no padding)."""
    is_bad  = np.array([l == bad_label  for l in labels])
    is_good = np.array([l == good_label for l in labels])
    mu_bad  = X[is_bad].mean(0)
    mu_good = X[is_good].mean(0)
    w = mu_bad - mu_good
    w = w / (np.linalg.norm(w) + 1e-8)
    sep = (X[is_bad] @ w).mean() - (X[is_good] @ w).mean()
    pooled = ((X[is_bad] @ w).std() + (X[is_good] @ w).std()) / 2 + 1e-8
    print(f"  Mean-diff Cohen's d: {sep/pooled:.3f}")
    V = w[:, None].astype(np.float32)  # (d, 1)
    return V


def ica_directions(X, k):
    """Independent Component Analysis — finds statistically independent directions."""
    from sklearn.decomposition import FastICA
    mu = X.mean(0)
    Xc = X - mu
    ica = FastICA(n_components=k, random_state=0, max_iter=500, tol=1e-3)
    try:
        ica.fit(Xc)
        V = ica.components_.T  # (d, k)
        # Orthonormalize (ICA components are not orthogonal by construction)
        V, _ = np.linalg.qr(V)
        err = np.max(np.abs(V.T @ V - np.eye(k)))
        print(f"  ICA converged. Orthonormality error after QR: {err:.2e}")
    except Exception as e:
        print(f"  ICA failed ({e}), falling back to PCA")
        V, _ = pca_directions(X, k)
        return V
    return V.astype(np.float32)


def save(V, path, meta):
    d = {'V': torch.from_numpy(V), 'k': V.shape[1], 'layer': 48,
         'model': 'Qwen2.5-32B-Instruct', 'n_items': meta.get('n_items', 0)}
    d.update(meta)
    torch.save(d, str(path))
    print(f"  Saved {V.shape} → {path}")


def main():
    args = parse_args()
    emb_path = BASE / args.embeddings if not Path(args.embeddings).is_absolute() else Path(args.embeddings)

    print(f"Loading embeddings: {emb_path}")
    df = pd.read_parquet(str(emb_path))
    X = np.stack(df['embedding'].values).astype(np.float64)
    labels = df['category'].tolist() if 'category' in df.columns else []
    print(f"  Shape: {X.shape}, categories: {set(labels)}")

    suf = args.suffix

    run_contrast = args.method in ('contrast', 'both', 'all')
    run_pca      = args.method in ('pca',      'both', 'all')
    run_logistic = args.method in ('logistic', 'all')
    run_ica      = args.method in ('ica',      'all')
    run_svm      = args.method in ('svm',      'all')
    run_meandiff = args.method in ('meandiff', 'all')

    if run_contrast:
        print(f"\n=== Contrast directions (k={args.k}) ===")
        V, sep = contrast_directions(X, labels, args.bad_label, args.good_label, args.k)
        path = OUTDIR / f'em_directions_contrast_{args.k}d{suf}.pt'
        save(V, path, {'method': 'contrast', 'n_items': len(df), 'sep_scores': sep.tolist()})

    if run_pca:
        print(f"\n=== PCA directions (k={args.k}) ===")
        V, mu = pca_directions(X, args.k)
        path = OUTDIR / f'em_directions_pca_{args.k}d{suf}.pt'
        save(V, path, {'method': 'pca', 'n_items': len(df), 'pca_mean': torch.from_numpy(mu)})

    if run_logistic:
        print(f"\n=== Logistic probe directions (k={args.k}) ===")
        V = logistic_directions(X, labels, args.bad_label, args.good_label, args.k)
        path = OUTDIR / f'em_directions_logistic_{args.k}d{suf}.pt'
        save(V, path, {'method': 'logistic', 'n_items': len(df)})

    if run_ica:
        print(f"\n=== ICA directions (k={args.k}) ===")
        V = ica_directions(X, args.k)
        path = OUTDIR / f'em_directions_ica_{args.k}d{suf}.pt'
        save(V, path, {'method': 'ica', 'n_items': len(df)})

    if run_svm:
        print(f"\n=== SVM directions (k={args.k}) ===")
        V = svm_directions(X, labels, args.bad_label, args.good_label, args.k)
        path = OUTDIR / f'em_directions_svm_{args.k}d{suf}.pt'
        save(V, path, {'method': 'svm', 'n_items': len(df)})

    if run_meandiff:
        print(f"\n=== Mean-difference direction (k=1) ===")
        V = meandiff_directions(X, labels, args.bad_label, args.good_label)
        path = OUTDIR / f'em_directions_meandiff_1d{suf}.pt'
        save(V, path, {'method': 'meandiff', 'n_items': len(df), 'k': 1})

    print("\nDone.")


if __name__ == '__main__':
    main()
