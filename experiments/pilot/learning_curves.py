"""
Within-participant learning curves on the pilot data using leave-one-out
cross-validation at each prefix length.

For each participant at each prefix length t in [3, T]:
  - Do LOO: for each trial i in [0, t), train on the other t-1 trials,
    predict trial i.
  - This yields t binary predictions, all on unseen data.
  - Compute accuracy and mean LL from those t predictions.

All three methods use the same unified fit_btl function:
  1. Baseline: fit theta in R^d (unrestricted, Woodbury for efficiency)
  2. K-dim projection (alpha=0): fit beta in R^K
  3. K-dim projection (deployed alpha): fit beta in R^K with feedback

Usage:
  cd preference-learning-dev

  # Default 3-fit comparison:
  python experiments/pilot/learning_curves.py \\
    --pilot-csv experiments/pilot/data.csv \\
    --embeddings-parquet datasets/dailydilemmas/selected_actions-embedded.parquet \\
    --directions method_directions/outputs/dailydilemmas/directions.npz \\
    --option-id-column action_id \\
    --output-dir experiments/pilot/learning_curves

  # Lambda grid sweep:
  python experiments/pilot/learning_curves.py \\
    --pilot-csv experiments/pilot/data.csv \\
    --embeddings-parquet datasets/dailydilemmas/selected_actions-embedded.parquet \\
    --directions method_directions/outputs/dailydilemmas/directions.npz \\
    --option-id-column action_id \\
    --lambda-partial-grid 0.01,0.1,0.5,1.0,5.0 \\
    --output-dir experiments/pilot/learning_curves_lambda
"""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from calibrate_from_pilot import (
    load_pilot_participants, build_per_trial_arrays,
    sigmoid, heldout_ll,
    perdim_bin_midpoints,
)


def fit_btl(X, X_grad, y, lam, P=None, max_iter=15, tol=1e-7,
            beta_prior=None, mu_prior=0.0):
    """Unified BTL logistic regression.
    Objective: min_b -LL(Xb, y) + (lam/2) b'Pb + (mu/2) ||b - b_prior||^2
    P=None means P=I. beta_prior adds a Gaussian prior."""
    T, p = X.shape
    theta = np.zeros(p)
    use_woodbury = (T * 2 < p) and (P is None) and (beta_prior is None)
    if use_woodbury:
        XXT = X @ X.T
    has_prior = beta_prior is not None and mu_prior > 0
    for _ in range(max_iter):
        logits = X @ theta
        prob = sigmoid(logits)
        w = prob * (1 - prob) + 1e-10
        Ptheta = lam * theta if P is None else lam * (P @ theta)
        grad = X_grad.T @ (prob - y) + Ptheta
        if has_prior:
            grad += mu_prior * (theta - beta_prior)
        if use_woodbury:
            M = np.diag(1.0 / w) + XXT / lam
            v = np.linalg.solve(M, X @ grad)
            d_theta = -(grad / lam - X.T @ v / (lam ** 2))
        else:
            if P is None:
                H = X.T @ (w[:, None] * X) + lam * np.eye(p)
            else:
                H = X.T @ (w[:, None] * X) + lam * P
            if has_prior:
                H += mu_prior * np.eye(p)
            d_theta = np.linalg.solve(H, -grad)
        theta = theta + d_theta
        if np.max(np.abs(d_theta)) < tol:
            break
    return theta


def compute_beta_prior(raw_lam, t_end, K):
    """Compute per-dimension prior mean from feedback observations.
    Averages finite values per dim across [0, t_end). No-feedback dims get 0."""
    bp = np.zeros(K)
    prefix = raw_lam[:t_end]
    for k in range(K):
        vals = prefix[:, k]
        finite = vals[np.isfinite(vals)]
        if len(finite) > 0:
            bp[k] = finite.mean()
    return bp


CONDITION_ORDER = ["choice_only", "inference_affirm", "inference_categories"]
FIT_STYLES = {
    "random_projection": {"color": "#444444", "marker": "o",
                          "label": "Random projection (baseline)"},
    "projection_only":   {"color": "#1f77b4", "marker": "s",
                          "label": "LLM projection (no feedback)"},
    "projection_alpha":  {"color": "#d62728", "marker": "^",
                          "label": "LLM projection + feedback"},
}
LAMBDA_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
                 "#9467bd", "#8c564b", "#e377c2", "#17becf"]
CAT_KEYS = ["skip", "not_into", "indifferent", "like", "love"]


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pilot-csv", required=True)
    p.add_argument("--embeddings-parquet", required=True)
    p.add_argument("--directions", required=True)
    p.add_argument("--option-id-column", default="action_id")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--min-prefix", type=int, default=3,
                   help="Minimum prefix length for LOO (default 3).")
    p.add_argument("--lambda-partial", type=float, default=0.01)
    p.add_argument("--n-dims", type=int, default=None,
                   help="Use only the top-D directions (by norm). "
                        "Default: use all K dimensions.")
    p.add_argument("--lambda-partial-grid", type=str, default=None,
                   help="Comma-separated lambda values to compare.")
    p.add_argument("--alpha-deployed", type=float, default=1.0)
    p.add_argument("--lambda-standard", type=float, default=0.01)
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def build_U_adj(U, raw_lam, alpha):
    U_adj = U.copy()
    has_replacement = np.isfinite(raw_lam)
    if has_replacement.any():
        U_adj[has_replacement] = ((1.0 - alpha) * U[has_replacement]
                                  + alpha * raw_lam[has_replacement])
    return U_adj


def loo_one_participant(deltas, U, raw_lam, visible_mask, y, G, args,
                        V_rand=None, G_rand=None, lambda_grid=None):
    """LOO CV at each rolling prefix length. All three methods use fit_btl."""
    T = len(y)
    K = U.shape[1]
    min_t = max(args.min_prefix, 3)
    if T < min_t:
        return []

    U_rand = deltas @ V_rand.T if V_rand is not None else None
    mu_prior = args.alpha_deployed  # independent of lambda

    rows = []
    for t in range(min_t, T + 1):
        all_idx = np.arange(t)
        y_prefix = y[:t].astype(float)

        if len(np.unique(y_prefix)) < 2:
            continue

        if lambda_grid is not None:
            fit_configs = [("random_projection", None)]
            for lam in lambda_grid:
                fit_configs.append((f"proj_l={lam}", lam))
        else:
            fit_configs = [("random_projection", None),
                           ("projection_only", args.lambda_partial),
                           ("projection_alpha", args.lambda_partial)]

        logits_loo = {name: np.zeros(t) for name, _ in fit_configs}

        for held_out in range(t):
            train_idx = np.concatenate([all_idx[:held_out],
                                        all_idx[held_out+1:]])
            y_train = y_prefix[train_idx]

            if len(np.unique(y_train)) < 2:
                for name in logits_loo:
                    logits_loo[name][held_out] = 0.0
                continue

            # Random projection baseline (P=I)
            beta_rand = fit_btl(U_rand[train_idx], U_rand[train_idx],
                                y_train, args.lambda_standard)
            logits_loo["random_projection"][held_out] = U_rand[held_out] @ beta_rand

            if lambda_grid is not None:
                for name, lam in fit_configs:
                    if name == "random_projection":
                        continue
                    beta = fit_btl(U[train_idx], U[train_idx],
                                   y_train, lam)
                    logits_loo[name][held_out] = U[held_out] @ beta
            else:
                beta_p0 = fit_btl(U[train_idx], U[train_idx],
                                   y_train, args.lambda_partial)
                logits_loo["projection_only"][held_out] = \
                    U[held_out] @ beta_p0

                # Feedback-as-prior: pull beta toward feedback values
                # Skip if no feedback was given (beta_prior all zeros)
                bp = compute_beta_prior(raw_lam, t, K)
                if np.any(bp != 0):
                    beta_dp = fit_btl(U[train_idx], U[train_idx],
                                       y_train, args.lambda_partial,
                                       beta_prior=bp, mu_prior=mu_prior)
                    logits_loo["projection_alpha"][held_out] = \
                        U[held_out] @ beta_dp
                else:
                    logits_loo["projection_alpha"][held_out] = \
                        logits_loo["projection_only"][held_out]

        y_true = y_prefix
        for fit_label, logits in logits_loo.items():
            preds = (logits > 0).astype(float)
            acc = float((preds == y_true).mean())
            ll = heldout_ll(logits, y_true)
            rows.append({"t": t, "fit": fit_label,
                         "test_acc": acc, "test_ll": ll})

    return rows


def plot_curves(df, output_path, lambda_grid=None, lambda_standard=0.01):
    conds_present = [c for c in CONDITION_ORDER
                     if c in df["condition"].unique()]
    if not conds_present:
        return
    fig, axes = plt.subplots(2, len(conds_present),
                              figsize=(4.8 * len(conds_present), 8),
                              sharex=True, squeeze=False)

    if lambda_grid is not None:
        styles = {"random_projection": {"color": "#444444", "marker": "o",
                                "label": f"random proj (l={lambda_standard})"}}
        markers = ["s", "^", "D", "v", "P", "X", "*", "h"]
        for i, lam in enumerate(lambda_grid):
            name = f"proj_l={lam}"
            styles[name] = {
                "color": LAMBDA_COLORS[i % len(LAMBDA_COLORS)],
                "marker": markers[i % len(markers)],
                "label": f"projection (l={lam})",
            }
    else:
        styles = FIT_STYLES

    rng_boot = np.random.default_rng(42)
    N_BOOT = 2000
    use_bootstrap = False  # match simulation default

    for col_idx, cond in enumerate(conds_present):
        cdf = df[df["condition"] == cond]
        n_part = cdf["qualtrics_id"].nunique() if not cdf.empty else 0
        pids = cdf["qualtrics_id"].unique()
        for row_idx, (metric, ylabel, hline) in enumerate([
                ("test_acc", "LOO accuracy", 0.5),
                ("test_ll", "LOO log-likelihood", None)]):
            ax = axes[row_idx, col_idx]
            for fit_label, style in styles.items():
                sub = cdf[cdf["fit"] == fit_label]
                if sub.empty:
                    continue
                ts = sorted(sub["t"].unique())
                means, ci_lo, ci_hi = [], [], []
                for t_val in ts:
                    t_sub = sub[sub["t"] == t_val]
                    vals = t_sub.set_index("qualtrics_id")[metric]
                    present = vals.index.intersection(pids)
                    if len(present) < 2:
                        means.append(vals.mean())
                        ci_lo.append(vals.mean())
                        ci_hi.append(vals.mean())
                        continue
                    v = vals.loc[present].values
                    m = v.mean()
                    means.append(m)
                    if use_bootstrap:
                        boot_means = np.array([
                            v[rng_boot.integers(0, len(v), size=len(v))].mean()
                            for _ in range(N_BOOT)
                        ])
                        ci_lo.append(np.percentile(boot_means, 2.5))
                        ci_hi.append(np.percentile(boot_means, 97.5))
                    else:
                        sem = v.std() / np.sqrt(len(v))
                        ci_lo.append(m - 1.96 * sem)
                        ci_hi.append(m + 1.96 * sem)
                means = np.array(means)
                ci_lo = np.array(ci_lo)
                ci_hi = np.array(ci_hi)
                ax.plot(ts, means, marker=style["marker"],
                        color=style["color"], label=style["label"],
                        linewidth=2, markersize=4)
                ax.fill_between(ts, ci_lo, ci_hi,
                                color=style["color"], alpha=0.10)
            if hline is not None:
                ax.axhline(hline, color="gray", linestyle="--", alpha=0.5)
            if row_idx == 0:
                # ax.set_title(f"{cond}\n(n={n_part})", fontweight="bold")
                ax.set_title(f"{cond}", fontweight="bold")
            if row_idx == 1:
                ax.set_xlabel("prefix length (# trials used)")
            if col_idx == 0:
                ax.set_ylabel(ylabel)
            ax.grid(True, alpha=0.3)
            if col_idx == 0 and row_idx == 0:
                ax.legend(loc="lower right", fontsize=7)

    ci_label = f"bootstrap 95% CI, {N_BOOT} resamples" if use_bootstrap else "95% CI (1.96 x SEM)"
    mode_label = "lambda sweep" if lambda_grid else "LOO"
    fig.suptitle(f"Pilot learning curves -- {mode_label}\n"
                  f"(shaded regions = {ci_label})",
                  fontsize=12, fontweight="bold")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_results(df, output_path):
    """Pilot analogues of the simulation's predicted_dv.png.

    Panel 1: Per-participant LOO accuracy advantage (LLM projection - random)
             at final T, shown as mean + 95% CI per condition, with
             significance brackets (paired Wilcoxon vs 0).
    Panel 2: Final-T LOO accuracy by fit type and condition (bar chart),
             analogous to the simulation's Spearman panel.
    """
    from scipy.stats import wilcoxon

    # Get final-t data per participant
    max_t = df.groupby('qualtrics_id')['t'].max()
    final = df.merge(max_t.reset_index().rename(columns={'t': 'max_t'}),
                     on='qualtrics_id')
    final = final[final['t'] == final['max_t']]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # --- Panel 1: Accuracy advantage (LLM proj - random) per condition ---
    ax = axes[0]
    cond_labels = []
    cond_means = []
    cond_ci_lo = []
    cond_ci_hi = []
    cond_pvals = []
    cond_colors = ['#1f77b4', '#ff7f0e', '#2ca02c']
    conds_present = [c for c in CONDITION_ORDER if c in final['condition'].unique()]

    for cond in conds_present:
        cdf = final[final['condition'] == cond]
        rand_acc = cdf[cdf['fit'] == 'random_projection'].set_index('qualtrics_id')['test_acc']
        proj_acc = cdf[cdf['fit'] == 'projection_only'].set_index('qualtrics_id')['test_acc']
        pids = rand_acc.index.intersection(proj_acc.index)
        if len(pids) < 2:
            continue
        diff = proj_acc.loc[pids].values - rand_acc.loc[pids].values
        m = diff.mean()
        sem = diff.std() / np.sqrt(len(diff))
        cond_labels.append(cond.replace('_', '\n'))
        cond_means.append(m)
        cond_ci_lo.append(m - 1.96 * sem)
        cond_ci_hi.append(m + 1.96 * sem)
        try:
            _, p = wilcoxon(diff, zero_method='zsplit')
        except ValueError:
            p = float('nan')
        cond_pvals.append(p)

    if cond_labels:
        x = np.arange(len(cond_labels))
        cond_means = np.array(cond_means)
        cond_ci_lo = np.array(cond_ci_lo)
        cond_ci_hi = np.array(cond_ci_hi)
        yerr = np.array([cond_means - cond_ci_lo, cond_ci_hi - cond_means])
        ax.bar(x, cond_means, width=0.5, color=cond_colors[:len(x)],
               alpha=0.7, edgecolor='black', linewidth=0.5)
        ax.errorbar(x, cond_means, yerr=yerr, fmt='none', ecolor='black',
                    capsize=6, capthick=1.5, linewidth=1.5)
        ax.axhline(0, color='gray', linestyle='--', alpha=0.5, label='no advantage')
        ax.set_xticks(x)
        ax.set_xticklabels(cond_labels)
        ax.set_ylabel('LOO accuracy advantage\n(LLM projection - random)')
        ax.set_title('LLM basis advantage\n(mean + 95% CI)', fontweight='bold')
        ax.legend(loc='lower right', fontsize=8)
        # Add p-value annotations
        for i, p in enumerate(cond_pvals):
            if p < 0.001:
                sig = '***'
            elif p < 0.01:
                sig = '**'
            elif p < 0.05:
                sig = '*'
            else:
                sig = 'ns'
            y_pos = max(cond_ci_hi[i], 0) + 0.01
            ax.text(i, y_pos, f'{sig}\np={p:.3f}', ha='center', fontsize=8)

    # --- Panel 2: Final-T LOO accuracy by fit type (grouped bars) ---
    ax = axes[1]
    fit_labels = ['random_projection', 'projection_only', 'projection_alpha']
    width = 0.25
    x = np.arange(len(conds_present))
    for i, fit in enumerate(fit_labels):
        means = []
        cis = []
        for cond in conds_present:
            cdf = final[(final['condition'] == cond) & (final['fit'] == fit)]
            if cdf.empty:
                means.append(0)
                cis.append(0)
            else:
                m = cdf['test_acc'].mean()
                sem = cdf['test_acc'].std() / np.sqrt(len(cdf))
                means.append(m)
                cis.append(1.96 * sem)
        ax.bar(x + (i - 1) * width, means, width, yerr=cis,
               color=FIT_STYLES[fit]['color'], label=FIT_STYLES[fit]['label'],
               alpha=0.7, edgecolor='black', linewidth=0.5,
               capsize=4)
    ax.axhline(0.5, color='gray', linestyle='--', alpha=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels([c.replace('_', '\n') for c in conds_present])
    ax.set_ylabel('LOO accuracy')
    ax.set_title('Final-T LOO accuracy by method\n(mean + 95% CI)', fontweight='bold')
    ax.legend(loc='lower right', fontsize=7)
    ax.grid(True, alpha=0.2, axis='y')

    fig.suptitle('Pilot results -- method comparison at final prefix',
                 fontsize=13, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    lambda_grid = None
    if args.lambda_partial_grid:
        lambda_grid = [float(x.strip())
                       for x in args.lambda_partial_grid.split(",")]
        print(f"Lambda grid mode: {lambda_grid}")

    print("Loading pilot...")
    parts = load_pilot_participants(args.pilot_csv)
    print(f"  found {len(parts)} participants")

    print("Loading embeddings + directions...")
    parq = pd.read_parquet(args.embeddings_parquet)
    parq[args.option_id_column] = parq[args.option_id_column].astype(str)
    parq = parq.sort_values(args.option_id_column).reset_index(drop=True)
    option_ids = parq[args.option_id_column].tolist()
    embeddings = np.stack(
        parq["embedding"].apply(np.array).values).astype(np.float64)
    oid_to_idx = {oid: i for i, oid in enumerate(option_ids)}

    npz = np.load(args.directions)
    V_raw = npz["directions_raw"].astype(np.float64)
    norms = np.linalg.norm(V_raw, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    V = V_raw / norms
    K = V.shape[0]

    # Select top-D dimensions if --n-dims is set
    if args.n_dims is not None and args.n_dims < K:
        # Rank by variance of item projections: Var(v_k^T (phi - mu))
        # Matches "variance_captured" from evaluate_basis.py
        centered = embeddings - embeddings.mean(axis=0)
        proj_var = np.var(centered @ V.T, axis=0)  # (K,)
        top_idx = np.argsort(-proj_var)[:args.n_dims]
        top_idx.sort()
        V = V[top_idx]
        K = args.n_dims
        print(f"  Selected top {K} dimensions (by variance of item projections)")

    G = V @ V.T
    print(f"  K={K}, N options={len(option_ids)}")

    # Generate random orthonormal basis for baseline (same D as LLM basis)
    rng_rand = np.random.default_rng(args.seed + 777)
    V_rand = rng_rand.standard_normal((K, embeddings.shape[1]))
    V_rand, _ = np.linalg.qr(V_rand.T)
    V_rand = V_rand[:, :K].T  # (K, d) orthonormal rows
    G_rand = V_rand @ V_rand.T  # = I_K
    print(f"  Random baseline: {K} orthonormal directions")

    rng_mp = np.random.default_rng(args.seed + 999)
    N = len(option_ids)
    n_pairs = min(2000, N * (N - 1) // 2)
    a = rng_mp.integers(0, N, size=n_pairs)
    b = rng_mp.integers(0, N, size=n_pairs)
    mask = a == b
    while mask.any():
        b[mask] = rng_mp.integers(0, N, size=int(mask.sum()))
        mask = a == b
    delta_proj = (embeddings[a] - embeddings[b]) @ V.T
    bin_midpoints = perdim_bin_midpoints(delta_proj, n_cats=5)

    print(f"\nLOO evaluation per participant (min prefix={args.min_prefix})...")
    rows = []
    n_used = 0
    n_skipped = 0
    for p in parts:
        try:
            deltas, U, raw_lam, vis, actions, y = build_per_trial_arrays(
                p, embeddings, V, oid_to_idx, K,
                bin_midpoints=bin_midpoints, cat_keys=CAT_KEYS)
        except KeyError:
            n_skipped += 1
            continue
        part_rows = loo_one_participant(
            deltas, U, raw_lam, vis, y, G, args,
            V_rand=V_rand, G_rand=G_rand,
            lambda_grid=lambda_grid)
        if not part_rows:
            n_skipped += 1
            continue
        n_used += 1
        for r in part_rows:
            rows.append({
                "qualtrics_id": p["qualtrics_id"],
                "condition": p["condition"],
                "domain": p["domain"],
                **r,
            })
        if n_used % 5 == 0:
            print(f"  {n_used} participants done...")
    print(f"  {n_used} participants used, {n_skipped} skipped")

    df = pd.DataFrame(rows)
    df.to_csv(output_dir / "learning_curves.csv", index=False)
    print(f"\nWrote {output_dir / 'learning_curves.csv'} ({len(df)} rows)")

    plot_curves(df, output_dir / "learning_curves.png",
                lambda_grid=lambda_grid,
                lambda_standard=args.lambda_standard)
    print(f"Wrote {output_dir / 'learning_curves.png'}")

    if lambda_grid is None:
        plot_results(df, output_dir / "pilot_results.png")
        print(f"Wrote {output_dir / 'pilot_results.png'}")

    print("\n=== SUMMARY (final prefix = max t per participant) ===")
    fit_labels = sorted(df["fit"].unique())
    for cond in CONDITION_ORDER:
        cdf = df[df["condition"] == cond]
        if cdf.empty:
            continue
        max_t = cdf.groupby("qualtrics_id")["t"].max()
        final = cdf.merge(max_t.reset_index().rename(columns={"t": "max_t"}),
                          on="qualtrics_id")
        final = final[final["t"] == final["max_t"]]
        n = final["qualtrics_id"].nunique()
        # print(f"\n{cond} (n={n}):")
        for fit in fit_labels:
            s = final[final["fit"] == fit]
            if s.empty:
                continue
            print(f"  {fit:20s}: LOO acc={s['test_acc'].mean():.3f}  "
                  f"LOO ll={s['test_ll'].mean():.4f}")


if __name__ == "__main__":
    main()
