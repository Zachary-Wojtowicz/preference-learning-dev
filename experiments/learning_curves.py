"""
learning_curves.py — LOO accuracy as a function of training set size.

Visualizes how quickly each method learns preferences from progressively more
training data. Designed to show the value-add of the feedback prior under
sparse training, and how that advantage decays as more choices are observed.

Two parameter sets are supported:

  --config deployed:  the parameters actually run in the experiment
                      (scheme=quintile_midpoints, α=2.0, λ=0.01)
  --config optimal:   the ex-post optimum from calibrate_methods.py
                      (scheme=linear_uniform, α=0.3, λ=0.01)
  --config both:      both figures + a comparison panel  (DEFAULT)

For each (condition, model, train_size), reports LOO-style accuracy averaged
across participants. At training size n < T-1, n training trials are randomly
subsampled (with N_REPEATS resamples per held-out trial); at n = T-1 this
reduces to the standard full-LOO. Train/test splits are SHARED across configs
within a participant, so running --config both costs only one extra
projection_alpha fit per fold-repeat (vs running deployed and optimal
separately, which would double everything).

Outputs (to analysis_outputs/):
    learning_curves_deployed.png
    learning_curves_optimal.png
    learning_curves_compared.png    (only with --config both)
    learning_curves.json            (means + 95% CIs per cell)

Usage:
    python experiments/dilemmas/learning_curves.py
    python experiments/dilemmas/learning_curves.py --config deployed
    python experiments/dilemmas/learning_curves.py --train-sizes 1 5 10 19
    python experiments/dilemmas/learning_curves.py --n-repeats 5

Reuses helpers from analyze.py and calibrate_methods.py.
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from scipy import stats

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from analyze import (  # noqa: E402
    load_qualtrics_csv, parse_participants, load_domain_assets,
    build_design_matrices, build_beta_prior,
    fit_btl, fit_btl_with_rescaled_prior, predict_p_a,
    is_complete,
    LAMBDA_PARTIAL,
    DATA_PATH, INFERENCE_CONDITIONS, CONDITIONS,
)
from calibrate_methods import midpoints_for_scheme  # noqa: E402


# ============================================================================
# Configurations
# ============================================================================
CONFIGS = {
    "deployed": {
        "scheme": "quintile_midpoints",
        "alpha":  2.0,
        "lam":    0.01,
        "label":   "Deployed parameters",
        "subtitle": "scheme=quintile_midpoints, alpha=2.0, lambda=0.01",
        "filename": "learning_curves_deployed.png",
    },
    "optimal": {
        "scheme": "linear_uniform",
        "alpha":  0.3,
        "lam":    0.01,
        "label":   "Ex-post optimal parameters",
        "subtitle": "scheme=linear_uniform, alpha=0.3, lambda=0.01",
        "filename": "learning_curves_optimal.png",
    },
}

DEFAULT_TRAIN_SIZES = [1, 3, 5, 10, 15, 19]
DEFAULT_N_REPEATS = 3


# ============================================================================
# Plot styling
# ============================================================================
COND_LABELS = {
    "choice_only":          "Choice only",
    "inference_affirm":     "Affirm/remove",
    "inference_categories": "Category select",
}

MODEL_LABELS = {
    "random_projection": "Random projection",
    "projection_only":   "Semantic projection",
    "projection_alpha":  "Semantic + feedback",
}

MODEL_COLORS = {
    "random_projection": "#9ca3af",
    "projection_only":   "#3b82f6",
    "projection_alpha":  "#dc2626",
}

MODELS_PER_COND = {
    "choice_only":          ["random_projection", "projection_only"],
    "inference_affirm":     ["random_projection", "projection_only", "projection_alpha"],
    "inference_categories": ["random_projection", "projection_only", "projection_alpha"],
}


# ============================================================================
# Per-participant learning curves (multi-config, shared splits)
# ============================================================================
def participant_curves(participant, domain_assets,
                       midpoints_by_config, alphas_by_config,
                       train_sizes, n_repeats):
    """Compute per-(config, model, train_size) accuracy for one participant.

    Splits (held-out trial + train subsample) are shared across configs, so
    random_projection and projection_only are computed once even when multiple
    configs are requested; only projection_alpha branches per config.
    """
    tp = domain_assets["trial_projections"]
    dim_ids = domain_assets["dim_ids"]
    categories = domain_assets["categories"]
    n_dims = domain_assets["n_dims"]
    cond = participant.get("condition", "")
    is_inf = cond in INFERENCE_CONDITIONS

    out = build_design_matrices(participant, tp)
    if out is None:
        return None
    U, U_rand, y = out
    T = len(y)
    if T < 2:
        return None

    pid = participant.get("participant_id") or id(participant)
    pid_seed = abs(hash(str(pid))) % (2**31)

    n_sizes = len(train_sizes)
    correct = defaultdict(lambda: np.zeros(n_sizes))
    total   = defaultdict(lambda: np.zeros(n_sizes))
    config_names = list(midpoints_by_config.keys())

    for ni, n_train in enumerate(train_sizes):
        rng = np.random.RandomState(pid_seed + 7919 * ni)
        for t in range(T):
            other = np.array([i for i in range(T) if i != t])
            yt = int(y[t])
            if n_train >= len(other):
                subsets = [other]
            else:
                subsets = [rng.choice(other, size=n_train, replace=False)
                           for _ in range(n_repeats)]

            for idx in subsets:
                U_tr   = U[idx]
                Ur_tr  = U_rand[idx]
                y_tr   = y[idx]

                # random_projection (config-independent)
                beta_rp = fit_btl(Ur_tr, y_tr, lam=LAMBDA_PARTIAL)
                rp_ok = int((1 if predict_p_a(beta_rp, U_rand[t]) >= 0.5 else 0) == yt)

                # projection_only (config-independent)
                beta_po = fit_btl(U_tr, y_tr, lam=LAMBDA_PARTIAL)
                po_ok = int((1 if predict_p_a(beta_po, U[t]) >= 0.5 else 0) == yt)

                for cname in config_names:
                    correct[(cname, "random_projection")][ni] += rp_ok
                    total  [(cname, "random_projection")][ni] += 1
                    correct[(cname, "projection_only")][ni] += po_ok
                    total  [(cname, "projection_only")][ni] += 1

                # projection_alpha (config-dependent, inference only)
                if is_inf:
                    for cname in config_names:
                        alpha = alphas_by_config[cname]
                        if alpha <= 0:
                            continue
                        bp_raw = build_beta_prior(
                            participant, dim_ids,
                            midpoints_by_config[cname],
                            n_dims, categories, train_indices=idx)
                        beta_pa = fit_btl_with_rescaled_prior(
                            U_tr, y_tr, lam=LAMBDA_PARTIAL,
                            beta_prior_raw=bp_raw, mu_prior=alpha)
                        pa_ok = int((1 if predict_p_a(beta_pa, U[t]) >= 0.5 else 0) == yt)
                        correct[(cname, "projection_alpha")][ni] += pa_ok
                        total  [(cname, "projection_alpha")][ni] += 1

    results = {}
    for key, c in correct.items():
        t_arr = total[key]
        acc = np.divide(c, t_arr, out=np.full_like(c, np.nan, dtype=float),
                        where=t_arr > 0)
        results[key] = acc
    return results


def compute_all_curves(participants, domain_assets,
                       midpoints_by_config_by_domain,
                       alphas_by_config, train_sizes, n_repeats):
    """Driver: compute per-(config, cond, model) arrays of shape
    (n_participants, n_train_sizes)."""
    config_names = list(midpoints_by_config_by_domain.keys())
    curves = {cname: {cond: defaultdict(list) for cond in CONDITIONS}
              for cname in config_names}

    n = len(participants)
    print(f"  Running {n} participants x {len(train_sizes)} train sizes x "
          f"{n_repeats} repeats x {len(config_names)} config(s) ...")
    for i, p in enumerate(participants, start=1):
        cond = p.get("condition")
        domain = p.get("domain")
        if cond not in CONDITIONS or domain not in domain_assets:
            continue
        mp_by_cfg = {cname: m_by_dom[domain]
                     for cname, m_by_dom in midpoints_by_config_by_domain.items()}
        res = participant_curves(p, domain_assets[domain],
                                 mp_by_cfg, alphas_by_config,
                                 train_sizes, n_repeats)
        if res is None:
            continue
        for (cname, model), accs in res.items():
            curves[cname][cond][model].append(accs)
        if i % 50 == 0 or i == n:
            print(f"    ... {i}/{n}")

    for cname in curves:
        for cond in curves[cname]:
            for model in list(curves[cname][cond].keys()):
                curves[cname][cond][model] = np.array(curves[cname][cond][model])
    return curves


# ============================================================================
# Aggregation + plotting
# ============================================================================
def mean_ci_by_size(arr, conf=0.95):
    """arr has shape (n_participants, n_train_sizes). Returns (mean, ci_half)
    arrays of length n_train_sizes (95% CI via t-distribution)."""
    if arr.size == 0:
        return None, None
    means = np.nanmean(arr, axis=0)
    n_per = np.sum(~np.isnan(arr), axis=0)
    sems = np.where(n_per > 1,
                     np.nanstd(arr, axis=0, ddof=1) / np.sqrt(np.maximum(n_per, 1)),
                     0.0)
    df = np.maximum(n_per - 1, 1)
    t_crit = stats.t.ppf((1 + conf) / 2, df=df)
    return means, t_crit * sems


def _draw_band(ax, x, mean, ci, color, label, linestyle="-"):
    ax.plot(x, mean, marker="o", linewidth=2, color=color,
            label=label, linestyle=linestyle, markersize=5)
    ax.fill_between(x, mean - ci, mean + ci, alpha=0.18, color=color,
                     linewidth=0)


def plot_one_config(curves_for_config, train_sizes, config_meta,
                    cond_counts, out_path):
    """Three-panel learning curve for a single config."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), sharey=True)
    for ax, cond in zip(axes, CONDITIONS):
        cond_data = curves_for_config[cond]
        for model in MODELS_PER_COND[cond]:
            arr = cond_data.get(model)
            if arr is None or len(arr) == 0:
                continue
            mean, ci = mean_ci_by_size(arr)
            if mean is None:
                continue
            _draw_band(ax, train_sizes, mean, ci,
                       MODEL_COLORS[model], MODEL_LABELS[model])
        n = cond_counts.get(cond, 0)
        ax.set_title(f"{COND_LABELS[cond]}  (N={n})", fontsize=11)
        ax.set_xlabel("Training trials")
        if ax is axes[0]:
            ax.set_ylabel("LOO accuracy")
        ax.axhline(0.5, color="black", linewidth=0.5, linestyle="--", alpha=0.4)
        ax.legend(loc="lower right", framealpha=0.92, fontsize=9)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.set_xticks(train_sizes)
        ax.set_ylim(0.45, 0.78)

    fig.suptitle(f"{config_meta['label']}  ({config_meta['subtitle']})",
                 fontsize=12, y=1.02)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_compared(curves, train_sizes, cond_counts, out_path):
    """Three-panel: random/projection_only drawn once (shared across configs);
    projection_alpha shown for both configs as dashed (deployed) and solid
    (optimal) lines."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), sharey=True)

    for ax, cond in zip(axes, CONDITIONS):
        for model in ["random_projection", "projection_only"]:
            arr = curves["deployed"][cond].get(model)
            if arr is None or len(arr) == 0:
                continue
            mean, ci = mean_ci_by_size(arr)
            if mean is None:
                continue
            _draw_band(ax, train_sizes, mean, ci,
                       MODEL_COLORS[model], MODEL_LABELS[model])

        if "projection_alpha" in MODELS_PER_COND[cond]:
            for cname, lstyle, suffix in [("deployed", "--", "deployed"),
                                            ("optimal",  "-",  "optimal")]:
                arr = curves[cname][cond].get("projection_alpha")
                if arr is None or len(arr) == 0:
                    continue
                mean, ci = mean_ci_by_size(arr)
                if mean is None:
                    continue
                _draw_band(ax, train_sizes, mean, ci,
                           MODEL_COLORS["projection_alpha"],
                           f"Semantic + feedback ({suffix})",
                           linestyle=lstyle)

        n = cond_counts.get(cond, 0)
        ax.set_title(f"{COND_LABELS[cond]}  (N={n})", fontsize=11)
        ax.set_xlabel("Training trials")
        if ax is axes[0]:
            ax.set_ylabel("LOO accuracy")
        ax.axhline(0.5, color="black", linewidth=0.5, linestyle="--", alpha=0.4)
        ax.legend(loc="lower right", framealpha=0.92, fontsize=8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.set_xticks(train_sizes)
        ax.set_ylim(0.45, 0.78)

    fig.suptitle("Learning curves: deployed vs ex-post optimal parameters",
                 fontsize=12, y=1.02)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()


# ============================================================================
# Main
# ============================================================================
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(DATA_PATH))
    parser.add_argument("--out-dir", default=str(SCRIPT_DIR / "analysis_outputs"))
    parser.add_argument("--config", default="both",
                        choices=["deployed", "optimal", "both"],
                        help="Which parameter set(s) to evaluate.")
    parser.add_argument("--train-sizes", nargs="+", type=int,
                        default=DEFAULT_TRAIN_SIZES,
                        help=f"Training-set sizes to sweep (default: {DEFAULT_TRAIN_SIZES})")
    parser.add_argument("--n-repeats", type=int, default=DEFAULT_N_REPEATS,
                        help=f"Random subsets per (participant, fold, size) "
                             f"when n_train < T-1 (default: {DEFAULT_N_REPEATS})")
    args = parser.parse_args()

    data_path = Path(args.data).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(exist_ok=True, parents=True)
    train_sizes = sorted(args.train_sizes)
    n_repeats = max(1, int(args.n_repeats))

    if args.config == "both":
        config_names = ["deployed", "optimal"]
    else:
        config_names = [args.config]

    print(f"Reading {data_path}")
    df = load_qualtrics_csv(data_path)
    participants = [p for p in parse_participants(df) if is_complete(p)]
    print(f"  {len(participants)} complete participants")
    cond_counts = defaultdict(int)
    for p in participants:
        cond_counts[p["condition"]] += 1
    for c in CONDITIONS:
        print(f"    {c}: N = {cond_counts[c]}")

    print(f"\nTrain sizes: {train_sizes}")
    print(f"Repeats:     {n_repeats}")
    print(f"Configs:     {config_names}\n")

    domains = sorted({p.get("domain") for p in participants if p.get("domain")})
    domain_assets = {}
    for d in domains:
        domain_assets[d] = load_domain_assets(d)

    midpoints_by_config_by_domain = {}
    alphas_by_config = {}
    for cname in config_names:
        cfg = CONFIGS[cname]
        alphas_by_config[cname] = cfg["alpha"]
        midpoints_by_config_by_domain[cname] = {}
        for d in domains:
            a = domain_assets[d]
            midpoints_by_config_by_domain[cname][d] = midpoints_for_scheme(
                cfg["scheme"], a["dim_ids"], a["trial_projections"])

    print("Computing learning curves ...")
    curves = compute_all_curves(
        participants, domain_assets,
        midpoints_by_config_by_domain, alphas_by_config,
        train_sizes, n_repeats)

    for cname in config_names:
        cfg = CONFIGS[cname]
        out_path = out_dir / cfg["filename"]
        plot_one_config(curves[cname], train_sizes, cfg, cond_counts, out_path)
        print(f"\nWrote: {out_path}")

    if len(config_names) == 2:
        cmp_path = out_dir / "learning_curves_compared.png"
        plot_compared(curves, train_sizes, cond_counts, cmp_path)
        print(f"Wrote: {cmp_path}")

    summary = {}
    for cname in config_names:
        summary[cname] = {}
        for cond in CONDITIONS:
            summary[cname][cond] = {}
            for model in MODELS_PER_COND[cond]:
                arr = curves[cname][cond].get(model)
                if arr is None or len(arr) == 0:
                    continue
                mean, ci = mean_ci_by_size(arr)
                summary[cname][cond][model] = {
                    "n_participants": int(arr.shape[0]),
                    "train_sizes": train_sizes,
                    "mean": [float(m) for m in mean],
                    "ci_half": [float(c) for c in ci],
                }
    json_path = out_dir / "learning_curves.json"
    with open(json_path, "w") as f:
        json.dump({
            "data_path": str(data_path),
            "configs": {cname: CONFIGS[cname] for cname in config_names},
            "train_sizes": train_sizes,
            "n_repeats": n_repeats,
            "n_per_condition": dict(cond_counts),
            "summary": summary,
        }, f, indent=2)
    print(f"Wrote: {json_path}")

    print("\nReading guide:")
    print("  - Each curve plots mean LOO accuracy +/- 95% CI vs training-set size.")
    print("  - At small training sizes, the feedback prior matters most;")
    print("    curves should converge as more choices are observed.")
    print("  - In the 'compared' figure, the gap between solid (optimal) and")
    print("    dashed (deployed) projection_alpha lines shows the value lost")
    print("    by miscalibration.")


if __name__ == "__main__":
    main()
