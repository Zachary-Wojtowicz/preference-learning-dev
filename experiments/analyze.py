"""
Dry-run analysis for the dilemmas experiment.

Implements H1 (LOO accuracy), H2 (signed summary Likert), and H3 (paired
prediction-rating difference) per the pre-registration in prereg.md.

Reads the Qualtrics CSV at experiments/dilemmas/data.csv, parses the
embedded experiment_data JSON column, fits per-participant LOO models,
runs the pre-registered tests, and writes figures + a summary JSON to
experiments/dilemmas/analysis_outputs/.

The point of this script (with N~10/cell) is to confirm the analysis
pipeline runs end-to-end on real data, NOT to draw inferences. With
small N, p-values and effect sizes are illustrative only.

Run:
    python experiments/dilemmas/analyze.py

Requires: numpy, pandas, scipy, matplotlib.
"""

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats


# ============================================================================
# Paths
# ============================================================================
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
PROJECTIONS_DIR = REPO_ROOT / "web-interface" / "outputs"

# Default data location is dilemmas/, the original main study. Override with
# `--data path/to/other/data.csv` for any other dataset (movies, wines, etc.).
# When --data is supplied without --out-dir, OUT_DIR auto-routes to
# `<data parent>/analysis_outputs/` (see main()).
DATA_PATH = SCRIPT_DIR / "dilemmas" / "data.csv"
OUT_DIR   = SCRIPT_DIR / "dilemmas" / "analysis_outputs"


# ============================================================================
# Constants (must match the experiment_config.json values used at runtime)
# ============================================================================
LAMBDA_PARTIAL = 0.01     # L2 regularization on beta
FEEDBACK_ALPHA = 2.0      # default mu_prior strength for projection_alpha
NEWTON_ITERS = 15
N_CATS = 5                # number of inference category bins (locked at 5)

# Per-condition feedback-prior strength. Initialized to the scalar default,
# but main() may override per-condition values via CLI flags. This lets the
# user run the analysis at the (different) optimal alpha for each inference
# condition in a single pass — needed because the calibration sweep showed
# affirm and categories often have meaningfully different optima.
FEEDBACK_ALPHA_BY_COND = {
    "inference_affirm":     FEEDBACK_ALPHA,
    "inference_categories": FEEDBACK_ALPHA,
}

# Per-condition mapping: which model is "augmented" (the new method we test)
# and which is the "baseline" it's compared against. This mapping is the
# canonical sign-convention reference for H1/H2/H3.
ROLE_TO_MODEL = {
    "choice_only":          {"augmented": "projection_only",  "baseline": "random_projection"},
    "inference_affirm":     {"augmented": "projection_alpha", "baseline": "projection_only"},
    "inference_categories": {"augmented": "projection_alpha", "baseline": "projection_only"},
}

CONDITIONS = ["choice_only", "inference_affirm", "inference_categories"]
INFERENCE_CONDITIONS = ["inference_affirm", "inference_categories"]


# ============================================================================
# JSON encoder for numpy types
# ============================================================================
class NPEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        return super().default(o)


# ============================================================================
# Data loading
# ============================================================================
def load_qualtrics_csv(path):
    """Read a Qualtrics CSV.
    Row 0 is the column header. Rows 1 and 2 are Qualtrics metadata
    (long-form question text and import IDs). Skip those two."""
    return pd.read_csv(path, skiprows=[1, 2])


def parse_participants(df):
    """Parse the embedded experiment_data JSON for each row."""
    participants = []
    for i, row in df.iterrows():
        raw = row.get("experiment_data")
        if not isinstance(raw, str) or not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"  [WARN] row {i}: could not parse experiment_data: {e}")
            continue
        # Light enrichment from CSV columns
        data["_qualtrics_response_id"] = row.get("ResponseId")
        data["_qualtrics_duration_s"] = row.get("Duration (in seconds)")
        data["_qualtrics_finished"] = row.get("Finished")
        data["_qualtrics_progress"] = row.get("Progress")
        participants.append(data)
    return participants


def load_domain_assets(domain):
    """Load trial_projections.json + experiment_config.json for a domain."""
    base = PROJECTIONS_DIR / domain
    with open(base / "trial_projections.json") as f:
        tp = json.load(f)
    with open(base / "experiment_config.json") as f:
        cfg = json.load(f)
    dim_ids = [d["id"] for d in cfg["dimensions"]]
    categories = cfg["inference_categories"]
    return {
        "trial_projections": tp,
        "config": cfg,
        "dim_ids": dim_ids,
        "categories": categories,
        "n_dims": len(dim_ids),
    }


def compute_dim_midpoints(tp, dim_ids, n_cats=N_CATS):
    """Per-dim quantile midpoints from the symmetrized raw_projection
    distribution (each value v contributes both v and -v to enforce
    symmetry around 0). Returns {dim_id: list of n_cats midpoints}.

    Mirrors computeDimMidpoints in index.html."""
    K = len(dim_ids)
    by_dim = {did: [] for did in dim_ids}
    for entry in tp:
        rp = entry.get("raw_projection")
        if not rp or len(rp) != K:
            continue
        for k in range(K):
            v = rp[k]
            if np.isfinite(v):
                by_dim[dim_ids[k]].extend([v, -v])

    out = {}
    for did, arr in by_dim.items():
        if len(arr) < n_cats:
            out[did] = None
            continue
        a = sorted(arr)
        mids = []
        for i in range(n_cats):
            q = (2 * i + 1) / (2 * n_cats)
            idx = min(int(q * (len(a) - 1)), len(a) - 1)
            mids.append(a[idx])
        out[did] = mids
    return out


# ============================================================================
# BTL fitter (port of fitBTL from web-interface/index.html)
# ============================================================================
def fit_btl(U, y, lam=LAMBDA_PARTIAL, beta_prior=None, mu_prior=0.0,
            max_iter=NEWTON_ITERS, tol=1e-7):
    """Newton + L2 + optional Gaussian prior on beta.

    Objective:
        min_beta -LL(U @ beta, y) + (lam/2)||beta||^2 + (mu/2)||beta - bp||^2

    Use mu_prior=0 (and beta_prior=None) for plain L2 (projection_only,
    random_projection). Use mu_prior>0 with a non-zero beta_prior for
    projection_alpha.
    """
    U = np.asarray(U, dtype=float)
    y = np.asarray(y, dtype=float)
    T, K = U.shape
    if T == 0:
        return np.zeros(K)
    bp = np.zeros(K) if beta_prior is None else np.asarray(beta_prior, dtype=float)
    mu = float(mu_prior)
    beta = np.zeros(K)
    I = np.eye(K)
    for _ in range(max_iter):
        u = U @ beta
        p = 1.0 / (1.0 + np.exp(-np.clip(u, -50, 50)))
        w = p * (1 - p)
        grad = U.T @ (p - y) + lam * beta + mu * (beta - bp)
        H = (U.T * w) @ U + (lam + mu) * I
        try:
            dB = np.linalg.solve(H, -grad)
        except np.linalg.LinAlgError:
            break
        beta = beta + dB
        if np.max(np.abs(dB)) < tol:
            break
    return beta


def predict_p_a(beta, U_row):
    """Probability that the participant chose option a, given fitted beta."""
    u = float(np.dot(U_row, beta))
    return 1.0 / (1.0 + np.exp(-np.clip(u, -50, 50)))


def fit_btl_with_rescaled_prior(U, y, lam=LAMBDA_PARTIAL, beta_prior_raw=None,
                                mu_prior=0.0, max_iter=NEWTON_ITERS, tol=1e-7):
    """Two-stage BTL fit that addresses the units mismatch between
    feedback-derived priors and the BTL-logit beta.

    `beta_prior_raw` is built from raw_projection-derived category midpoints,
    so it lives on delta-projection scale (typically ~O(0.1) for dailydilemmas).
    The data-fitted beta lives on BTL-logit scale (~O(10)) because logits =
    U @ beta need to be O(1) when U is O(0.1). Without rescaling, mu_prior=2.0
    effectively shrinks beta toward ~0 instead of toward the participant's
    stated preferences (cosine is fine; only magnitude is wrong --
    see diagnose_scale.py).

    This function fits twice:
      Stage 1: data-only fit -> learn the participant's beta magnitude.
      Stage 2: rescale the prior to match,
                  beta_prior_eff = (||beta_data|| / ||beta_prior_raw||) * beta_prior_raw
               then refit with the rescaled prior.

    After this, mu_prior parameterizes "trust in feedback direction", with
    magnitude inherited from the data-only fit, rather than conflating
    direction and magnitude.

    Cost: 2 BTL fits per call (vs 1 for plain fit_btl). Negligible at
    K=10, T=20.
    """
    # Stage 1: data-only fit sets the magnitude.
    beta_data = fit_btl(U, y, lam=lam, beta_prior=None, mu_prior=0.0,
                        max_iter=max_iter, tol=tol)
    if beta_prior_raw is None:
        return beta_data
    bp_raw = np.asarray(beta_prior_raw, dtype=float)
    raw_norm = float(np.linalg.norm(bp_raw))
    if raw_norm < 1e-12:
        # No usable feedback signal; rescaled prior would be 0, no effect.
        return beta_data
    # Stage 2: rescale prior to data-fit magnitude, then refit.
    s = float(np.linalg.norm(beta_data)) / raw_norm
    beta_prior_scaled = s * bp_raw
    return fit_btl(U, y, lam=lam, beta_prior=beta_prior_scaled,
                   mu_prior=mu_prior, max_iter=max_iter, tol=tol)


# ============================================================================
# Per-participant feature construction
# ============================================================================
def build_design_matrices(participant, trial_projections):
    """Build U (T x K LLM proj), U_rand (T x K random proj), y (T) for the
    participant's seen trials. Returns None if any required projection is
    missing (e.g., wines_100 currently lacks random_projection)."""
    responses = participant.get("responses") or []
    T = len(responses)
    if T == 0:
        return None
    U_rows, Ur_rows, y_vals = [], [], []
    for r in responses:
        pi = r.get("pair_index")
        if pi is None:
            # Backward compat: derive from trial_id "tN" -> N-1
            tid = r.get("trial_id", "")
            try:
                pi = int(tid.lstrip("t")) - 1
            except ValueError:
                return None
        if pi < 0 or pi >= len(trial_projections):
            return None
        tp = trial_projections[pi]
        rp = tp.get("raw_projection")
        rdp = tp.get("random_projection")
        if rp is None or rdp is None:
            return None
        U_rows.append(rp)
        Ur_rows.append(rdp)
        y_vals.append(1.0 if r.get("chosen") == "a" else 0.0)
    return (np.array(U_rows, dtype=float),
            np.array(Ur_rows, dtype=float),
            np.array(y_vals, dtype=float))


def build_beta_prior(participant, dim_ids, midpoints_by_did, n_dims,
                     categories, train_indices=None):
    """Build beta_prior from the participant's inference_values. If
    train_indices is given (LOO), only those response indices contribute.

    Mirrors buildEvalInputs in index.html: each visible-dim feedback contributes
    one value to its column's running mean, with action='remove' -> 0 and
    everything else -> midpoint(category)."""
    K = n_dims
    cat_key_to_idx = {c["key"]: i for i, c in enumerate(categories)}
    sums = np.zeros(K)
    counts = np.zeros(K)

    responses = participant.get("responses") or []
    idxs = train_indices if train_indices is not None else range(len(responses))

    for i in idxs:
        r = responses[i]
        iv = r.get("inference_values") or {}
        for did, info in iv.items():
            if did not in dim_ids:
                continue
            k = dim_ids.index(did)
            action = (info or {}).get("action", "none")
            if action == "remove":
                value = 0.0
            else:
                cat = info.get("category")
                cat_idx = cat_key_to_idx.get(cat)
                mids = midpoints_by_did.get(did)
                if cat_idx is None or mids is None:
                    continue
                value = mids[cat_idx]
            sums[k] += value
            counts[k] += 1

    bp = np.zeros(K)
    for k in range(K):
        if counts[k] > 0:
            bp[k] = sums[k] / counts[k]
    return bp


# ============================================================================
# H1: LOO accuracy
# ============================================================================
def loo_accuracy(U, y, lam=LAMBDA_PARTIAL, beta_prior_fn=None, mu_prior=0.0,
                 rescale_prior=True):
    """Leave-one-out CV accuracy.

    beta_prior_fn(train_indices) -> K-vector or None. When provided, the
    prior is rebuilt for each LOO fold using only the training trials,
    so the held-out trial's feedback never leaks into its own prediction.

    rescale_prior=True (default, post-fix behavior): per fold, the feedback
    prior is rescaled to match the data-only fit magnitude before being
    used as the BTL anchor (see fit_btl_with_rescaled_prior). Costs one
    extra fit per fold.

    rescale_prior=False (legacy behavior): pass the raw delta-scale prior
    directly into the optimizer. This was the original implementation, but
    it caused mu_prior=2.0 to act as near-zero shrinkage. Kept only for
    backward-compatibility checks.
    """
    T = len(y)
    correct = 0
    for t in range(T):
        train_idx = np.concatenate([np.arange(t), np.arange(t + 1, T)])
        U_tr, y_tr = U[train_idx], y[train_idx]
        if beta_prior_fn is not None and mu_prior > 0:
            bp_raw = beta_prior_fn(train_idx)
            if rescale_prior:
                beta = fit_btl_with_rescaled_prior(
                    U_tr, y_tr, lam=lam,
                    beta_prior_raw=bp_raw, mu_prior=mu_prior)
            else:
                beta = fit_btl(U_tr, y_tr, lam=lam,
                               beta_prior=bp_raw, mu_prior=mu_prior)
        else:
            beta = fit_btl(U_tr, y_tr, lam=lam,
                           beta_prior=None, mu_prior=0.0)
        p_a = predict_p_a(beta, U[t])
        pred = 1 if p_a >= 0.5 else 0
        if pred == int(y[t]):
            correct += 1
    return correct / T


def compute_loo_per_participant(participant, domain_assets, midpoints):
    """Return {model_name: loo_accuracy} for the relevant models."""
    tp = domain_assets["trial_projections"]
    dim_ids = domain_assets["dim_ids"]
    categories = domain_assets["categories"]
    n_dims = domain_assets["n_dims"]

    out = build_design_matrices(participant, tp)
    if out is None:
        return None
    U, U_rand, y = out
    cond = participant["condition"]

    result = {}
    # Always fit: random_projection and projection_only
    result["random_projection"] = loo_accuracy(U_rand, y, lam=LAMBDA_PARTIAL)
    result["projection_only"]   = loo_accuracy(U,      y, lam=LAMBDA_PARTIAL)
    # projection_alpha: only in inference conditions, and only if any feedback
    # was provided (otherwise the prior collapses to 0 and it's identical to
    # projection_only). Uses the per-condition alpha from FEEDBACK_ALPHA_BY_COND
    # (set in main() from --alpha / --alpha-affirm / --alpha-categories).
    if cond in INFERENCE_CONDITIONS:
        bp_fn = lambda idxs: build_beta_prior(
            participant, dim_ids, midpoints, n_dims, categories, train_indices=idxs)
        alpha_for_cond = FEEDBACK_ALPHA_BY_COND.get(cond, FEEDBACK_ALPHA)
        result["projection_alpha"] = loo_accuracy(
            U, y, lam=LAMBDA_PARTIAL, beta_prior_fn=bp_fn, mu_prior=alpha_for_cond)
    return result


# ============================================================================
# H2: signed summary Likert
# ============================================================================
def decode_signed_likert(participant):
    """Sign convention (per pre-reg): positive = preferred the augmented
    summary. The raw Likert in evaluation.rating_numeric uses +/- to
    indicate B/A side preferred; we re-sign based on which side's model
    is the augmented one for this condition."""
    cond = participant.get("condition")
    ev = participant.get("evaluation") or {}
    rating = ev.get("rating_numeric")
    if rating is None or cond not in ROLE_TO_MODEL:
        return None
    augmented = ROLE_TO_MODEL[cond]["augmented"]
    left = ev.get("left_model")
    right = ev.get("right_model")
    # rating > 0 means B (right) preferred; rating < 0 means A (left) preferred
    if right == augmented:
        return float(rating)
    elif left == augmented:
        return float(-rating)
    return None


# ============================================================================
# H3: paired (augmented - baseline) prediction rating difference
# ============================================================================
def decode_pred_diff(participant):
    """Return augmented_rating - baseline_rating from the two prediction trials."""
    pc = participant.get("prediction_check") or {}
    trials = pc.get("trials") or []
    if len(trials) != 2:
        return None
    aug = next((t for t in trials if t.get("role") == "augmented"), None)
    base = next((t for t in trials if t.get("role") == "baseline"), None)
    if aug is None or base is None:
        return None
    if aug.get("rating_numeric") is None or base.get("rating_numeric") is None:
        return None
    return float(aug["rating_numeric"] - base["rating_numeric"])


# ============================================================================
# Inclusion criterion (per pre-reg)
# ============================================================================
def is_complete(p):
    """Per pre-reg: include only participants who completed all 20 trials,
    the summary comparison, and both prediction-rating trials."""
    if len(p.get("responses") or []) != p.get("num_trials"):
        return False
    ev = p.get("evaluation") or {}
    if ev.get("rating_numeric") is None:
        return False
    pc = p.get("prediction_check") or {}
    trials = pc.get("trials") or []
    if len(trials) != 2:
        return False
    if any(t.get("rating_numeric") is None for t in trials):
        return False
    return True


# ============================================================================
# Statistical helpers
# ============================================================================
def holm_bonferroni(pvals):
    """Holm-Bonferroni adjusted p-values for a family. Returns np.array."""
    pvals = np.asarray(pvals, dtype=float)
    n = len(pvals)
    if n == 0:
        return np.array([])
    order = np.argsort(pvals)
    adj = np.empty(n)
    running = 0.0
    for rank, idx in enumerate(order):
        a = (n - rank) * pvals[idx]
        running = max(running, a)
        adj[idx] = min(running, 1.0)
    return adj


def cohens_dz(diffs):
    diffs = np.asarray(diffs, dtype=float)
    diffs = diffs[~np.isnan(diffs)]
    if len(diffs) < 2 or diffs.std(ddof=1) == 0:
        return float("nan")
    return diffs.mean() / diffs.std(ddof=1)


def rank_biserial(diffs):
    """Rank-biserial correlation effect size for one-sample Wilcoxon."""
    d = np.asarray(diffs, dtype=float)
    d = d[~np.isnan(d) & (d != 0)]
    if len(d) == 0:
        return float("nan")
    ranks = stats.rankdata(np.abs(d))
    pos = ranks[d > 0].sum()
    neg = ranks[d < 0].sum()
    total = pos + neg
    return (pos - neg) / total if total > 0 else float("nan")


def safe_one_sample_wilcoxon(vals, alternative="greater"):
    """Returns (W, p, n_used) or (None, None, n_used) if test undefined."""
    v = np.asarray(vals, dtype=float)
    v = v[~np.isnan(v)]
    if len(v) < 2 or np.all(v == 0):
        return None, None, len(v)
    try:
        res = stats.wilcoxon(v, alternative=alternative,
                             zero_method="wilcox", correction=False)
        return float(res.statistic), float(res.pvalue), len(v)
    except ValueError:
        return None, None, len(v)


def t_ci(vals, conf=0.95):
    """Two-sided t-distribution CI on the mean.

    Returns (mean, ci_half_width) such that the CI is [mean - hw, mean + hw].
    Empty input -> (0, 0). Single value -> (mean, 0).
    """
    v = np.asarray(vals, dtype=float)
    v = v[~np.isnan(v)]
    n = len(v)
    if n == 0:
        return 0.0, 0.0
    if n < 2:
        return float(v.mean()), 0.0
    sem = float(v.std(ddof=1) / np.sqrt(n))
    t_crit = float(stats.t.ppf((1 + conf) / 2, df=n - 1))
    return float(v.mean()), t_crit * sem


# ============================================================================
# Aggregate analyses
# ============================================================================
def run_h1(participants, domain_assets_by_domain, midpoints_by_domain):
    """Per condition, paired one-sided t-test on (LOO_aug - LOO_base)."""
    by_cond = defaultdict(list)
    raw_loos = []
    for p in participants:
        domain = p.get("domain")
        if domain not in domain_assets_by_domain:
            continue
        loo = compute_loo_per_participant(
            p, domain_assets_by_domain[domain], midpoints_by_domain[domain])
        if loo is None:
            continue
        cond = p["condition"]
        aug_name = ROLE_TO_MODEL[cond]["augmented"]
        base_name = ROLE_TO_MODEL[cond]["baseline"]
        if aug_name not in loo or base_name not in loo:
            continue
        diff = loo[aug_name] - loo[base_name]
        by_cond[cond].append({
            "pid": p.get("participant_id"),
            "aug_name": aug_name, "aug_acc": loo[aug_name],
            "base_name": base_name, "base_acc": loo[base_name],
            "diff": diff,
        })
        raw_loos.append({"pid": p.get("participant_id"),
                         "condition": cond, "domain": domain, **loo})

    results = {}
    p_for_holm = []
    cond_order = []
    for cond in CONDITIONS:
        rows = by_cond.get(cond) or []
        diffs = np.array([r["diff"] for r in rows])
        n = len(diffs)
        cell = {"n": n, "rows": rows}
        if n >= 2 and diffs.std(ddof=1) > 0:
            t, p_two = stats.ttest_1samp(diffs, popmean=0.0)
            p_one = float(p_two / 2 if t > 0 else 1 - p_two / 2)
            cell.update({
                "mean_diff": float(diffs.mean()),
                "sd_diff":   float(diffs.std(ddof=1)),
                "t":         float(t),
                "p_one_sided": p_one,
                "d_z":       float(cohens_dz(diffs)),
            })
            p_for_holm.append(p_one)
            cond_order.append(cond)
        else:
            cell.update({
                "mean_diff": float(diffs.mean()) if n else None,
                "sd_diff":   None, "t": None, "p_one_sided": None, "d_z": None,
            })
        results[cond] = cell

    if p_for_holm:
        for cond, a in zip(cond_order, holm_bonferroni(p_for_holm)):
            results[cond]["p_holm"] = float(a)

    return {"by_cond": results, "raw_loo": raw_loos}


def run_h2(participants):
    by_cond = defaultdict(list)
    for p in participants:
        s = decode_signed_likert(p)
        if s is None:
            continue
        by_cond[p["condition"]].append({"pid": p.get("participant_id"), "signed": s})

    results = {}
    p_for_holm = []
    cond_order = []
    for cond in CONDITIONS:
        rows = by_cond.get(cond) or []
        vals = np.array([r["signed"] for r in rows])
        W, p, n_used = safe_one_sample_wilcoxon(vals, alternative="greater")
        cell = {
            "n": len(vals),
            "n_used_in_test": n_used,
            "rows": rows,
            "median": float(np.median(vals)) if len(vals) else None,
            "mean":   float(vals.mean())     if len(vals) else None,
            "W": W, "p_one_sided": p,
            "rb": float(rank_biserial(vals)) if len(vals) else None,
            "is_manipulation_check": cond == "choice_only",
        }
        results[cond] = cell
        # H2 family for Holm = inference conditions only (per pre-reg)
        if cond in INFERENCE_CONDITIONS and p is not None:
            p_for_holm.append(p)
            cond_order.append(cond)

    if p_for_holm:
        for cond, a in zip(cond_order, holm_bonferroni(p_for_holm)):
            results[cond]["p_holm"] = float(a)

    return results


def run_h3(participants):
    by_cond = defaultdict(list)
    for p in participants:
        d = decode_pred_diff(p)
        if d is None:
            continue
        by_cond[p["condition"]].append({"pid": p.get("participant_id"), "diff": d})

    results = {}
    p_for_holm = []
    cond_order = []
    for cond in CONDITIONS:
        rows = by_cond.get(cond) or []
        vals = np.array([r["diff"] for r in rows])
        W, p, n_used = safe_one_sample_wilcoxon(vals, alternative="greater")
        cell = {
            "n": len(vals),
            "n_used_in_test": n_used,
            "rows": rows,
            "median": float(np.median(vals)) if len(vals) else None,
            "mean":   float(vals.mean())     if len(vals) else None,
            "W": W, "p_one_sided": p,
            "rb": float(rank_biserial(vals)) if len(vals) else None,
        }
        results[cond] = cell
        if p is not None:
            p_for_holm.append(p)
            cond_order.append(cond)

    if p_for_holm:
        for cond, a in zip(cond_order, holm_bonferroni(p_for_holm)):
            results[cond]["p_holm"] = float(a)

    return results


# ============================================================================
# Figures
# ============================================================================
COND_LABELS = {
    "choice_only":          "Choice only",
    "inference_affirm":     "Affirm/remove",
    "inference_categories": "Category select",
}
COND_COLORS = {
    "choice_only":          "#6b7280",
    "inference_affirm":     "#3b82f6",
    "inference_categories": "#10b981",
}


def _strip_with_median(ax, conds, vals_per_cond, ylim, ylabel, title, jitter_seed):
    rng = np.random.RandomState(jitter_seed)
    for i, cond in enumerate(conds):
        vals = vals_per_cond.get(cond) or []
        if not vals:
            continue
        jitter = rng.uniform(-0.15, 0.15, size=len(vals))
        ax.scatter(np.full(len(vals), i) + jitter, vals,
                   color=COND_COLORS[cond], alpha=0.7, s=50, edgecolor="white",
                   linewidth=0.5)
        ax.scatter(i, np.median(vals), color="black", marker="_", s=400, zorder=3,
                   linewidths=3)
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--", alpha=0.5)
    ax.set_xticks(np.arange(len(conds)))
    ax.set_xticklabels([COND_LABELS[c] for c in conds], fontsize=9)
    if ylim is not None:
        ax.set_ylim(*ylim)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def fig_main(h1, h2, h3, out_path, alpha_by_cond=None):
    """Three-panel figure: per-condition mean ± 95% CI for H1, H2, H3.

    Y-axes are data-driven (so the actual effect sizes are visible rather
    than buried in a full Likert range). Significance markers (* ** ***)
    are drawn above bars based on the unadjusted one-sided p-value.
    """
    if alpha_by_cond is None:
        alpha_by_cond = FEEDBACK_ALPHA_BY_COND
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5))

    def sig_marker(p):
        if p is None:
            return ""
        if p < 0.001: return "***"
        if p < 0.01:  return "**"
        if p < 0.05:  return "*"
        return ""

    def plot_panel(ax, vals_per_cond, p_per_cond, ylabel, title):
        means, cis, ns, sigs = [], [], [], []
        for cond in CONDITIONS:
            vs = vals_per_cond.get(cond) or []
            mean, ci = t_ci(vs)
            means.append(mean); cis.append(ci); ns.append(len(vs))
            sigs.append(sig_marker(p_per_cond.get(cond)))
        x = np.arange(len(CONDITIONS))
        colors = [COND_COLORS[c] for c in CONDITIONS]
        ax.bar(x, means, yerr=cis, capsize=6, color=colors, alpha=0.88,
               edgecolor="white", linewidth=1.2,
               error_kw={"linewidth": 1.4, "ecolor": "#1a1a1a"})
        ax.axhline(0, color="black", linewidth=0.7, linestyle="-", alpha=0.6)
        ax.set_xticks(x)
        ax.set_xticklabels([f"{COND_LABELS[c]}\n(N={n})"
                            for c, n in zip(CONDITIONS, ns)],
                           fontsize=9)
        ax.set_ylabel(ylabel, fontsize=10)
        ax.set_title(title, fontsize=11)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        # Tight y-axis with 0 always visible. Extra headroom on top for
        # significance markers.
        lows  = [m - c for m, c in zip(means, cis)] + [0]
        highs = [m + c for m, c in zip(means, cis)] + [0]
        lo, hi = min(lows), max(highs)
        span = hi - lo if hi > lo else 0.1
        ax.set_ylim(lo - span * 0.18, hi + span * 0.30)
        # Place significance markers just above the upper CI (or below for negatives).
        for xi, mean, ci, sig in zip(x, means, cis, sigs):
            if not sig:
                continue
            if mean >= 0:
                y = mean + ci + span * 0.05
                va = "bottom"
            else:
                y = mean - ci - span * 0.05
                va = "top"
            ax.text(xi, y, sig, ha="center", va=va, fontsize=12,
                    fontweight="bold", color="#1a1a1a")

    h1_vals = {c: [r["diff"] for r in (h1["by_cond"].get(c, {}).get("rows") or [])]
               for c in CONDITIONS}
    h1_p = {c: h1["by_cond"].get(c, {}).get("p_one_sided") for c in CONDITIONS}
    plot_panel(axes[0], h1_vals, h1_p,
               "LOO accuracy: augmented − baseline",
               "H1: predictive accuracy lift")

    h2_vals = {c: [r["signed"] for r in (h2.get(c, {}).get("rows") or [])]
               for c in CONDITIONS}
    h2_p = {c: h2.get(c, {}).get("p_one_sided") for c in CONDITIONS}
    plot_panel(axes[1], h2_vals, h2_p,
               "Signed Likert  (+ = preferred augmented)",
               "H2: summary preference")

    h3_vals = {c: [r["diff"] for r in (h3.get(c, {}).get("rows") or [])]
               for c in CONDITIONS}
    h3_p = {c: h3.get(c, {}).get("p_one_sided") for c in CONDITIONS}
    plot_panel(axes[2], h3_vals, h3_p,
               "Augmented − baseline rating",
               "H3: prediction endorsement")

    a_aff = alpha_by_cond.get("inference_affirm")
    a_cat = alpha_by_cond.get("inference_categories")
    if a_aff is not None and a_cat is not None and a_aff != a_cat:
        alpha_str = (f"\u03b1$_{{\\mathrm{{affirm}}}}$={a_aff}, "
                     f"\u03b1$_{{\\mathrm{{categories}}}}$={a_cat}")
    else:
        alpha_str = f"\u03b1={a_aff if a_aff is not None else FEEDBACK_ALPHA}"
    fig.suptitle(
        f"Per-condition means \u00b1 95% CI  "
        f"({alpha_str}, \u03bb={LAMBDA_PARTIAL}; "
        f"* p<.05, ** p<.01, *** p<.001 one-sided, unadjusted)",
        fontsize=10, y=1.03)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()


# ============================================================================
# Reporting
# ============================================================================
def fmt(x, fmt_spec=".3f", missing="—"):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return missing
    return format(x, fmt_spec)


def print_report(participants_all, participants_kept, h1, h2, h3):
    excluded = len(participants_all) - len(participants_kept)
    print("=" * 78)
    print("DRY-RUN ANALYSIS SUMMARY")
    print("=" * 78)
    print(f"  Participants total:     {len(participants_all)}")
    print(f"  Excluded (incomplete):  {excluded}")
    print(f"  Participants analyzed:  {len(participants_kept)}")
    cond_counts = defaultdict(int)
    for p in participants_kept:
        cond_counts[p["condition"]] += 1
    for c in CONDITIONS:
        print(f"     {c:<22} N = {cond_counts.get(c, 0)}")
    print()

    # H1
    print("-" * 78)
    print("H1 — LOO accuracy: augmented − baseline (per condition)")
    print("     paired one-sided t-test, alternative > 0; Holm-Bonferroni across conditions")
    print("-" * 78)
    print(f"  {'condition':<22} {'N':>3} {'Δacc':>7} {'t':>7} {'p_one':>9} {'p_holm':>9} {'d_z':>7}")
    for cond in CONDITIONS:
        r = h1["by_cond"].get(cond) or {}
        print(f"  {cond:<22} {r.get('n', 0):>3} "
              f"{fmt(r.get('mean_diff'), '+.3f'):>7} "
              f"{fmt(r.get('t'), '+.2f'):>7} "
              f"{fmt(r.get('p_one_sided'), '.4f'):>9} "
              f"{fmt(r.get('p_holm'), '.4f'):>9} "
              f"{fmt(r.get('d_z'), '+.2f'):>7}")
    print()

    # H2
    print("-" * 78)
    print("H2 — Signed summary Likert > 0  (+ = preferred augmented)")
    print("     one-sample Wilcoxon, alternative > 0; Holm across inference conditions")
    print("     (choice_only is a manipulation check, not part of H2)")
    print("-" * 78)
    print(f"  {'condition':<22} {'N':>3} {'med':>5} {'mean':>6} {'W':>6} {'p_one':>9} {'p_holm':>9} {'r_rb':>6}")
    for cond in CONDITIONS:
        r = h2.get(cond) or {}
        marker = " *mc" if r.get("is_manipulation_check") else ""
        print(f"  {cond:<22} {r.get('n', 0):>3} "
              f"{fmt(r.get('median'), '+.1f'):>5} "
              f"{fmt(r.get('mean'), '+.2f'):>6} "
              f"{fmt(r.get('W'), '.1f'):>6} "
              f"{fmt(r.get('p_one_sided'), '.4f'):>9} "
              f"{fmt(r.get('p_holm'), '.4f'):>9} "
              f"{fmt(r.get('rb'), '+.2f'):>6}{marker}")
    print()

    # H3
    print("-" * 78)
    print("H3 — augmented − baseline prediction rating > 0")
    print("     one-sample Wilcoxon on paired diff, alternative > 0; Holm across conditions")
    print("-" * 78)
    print(f"  {'condition':<22} {'N':>3} {'med':>5} {'mean':>6} {'W':>6} {'p_one':>9} {'p_holm':>9} {'r_rb':>6}")
    for cond in CONDITIONS:
        r = h3.get(cond) or {}
        print(f"  {cond:<22} {r.get('n', 0):>3} "
              f"{fmt(r.get('median'), '+.1f'):>5} "
              f"{fmt(r.get('mean'), '+.2f'):>6} "
              f"{fmt(r.get('W'), '.1f'):>6} "
              f"{fmt(r.get('p_one_sided'), '.4f'):>9} "
              f"{fmt(r.get('p_holm'), '.4f'):>9} "
              f"{fmt(r.get('rb'), '+.2f'):>6}")
    print()
    print("Note: with N ~ 10 / cell, p-values and effect sizes are illustrative.")
    print("      This run is a pipeline check, not a powered test.")


# ============================================================================
# Markdown summary (shareable with collaborators)
# ============================================================================
def write_summary_md(participants_all, participants_kept, h1, h2, h3,
                     alpha_by_cond, out_path):
    """Write a self-contained markdown summary suitable for sharing with
    collaborators. Includes sample sizes, hyperparameters, results tables
    with effect sizes and 95% CIs, and brief methodology notes.

    `alpha_by_cond` is a dict mapping condition name to the \u03b1 used for
    that condition. When affirm and categories use the same value, a single
    row is shown; otherwise the rows are split.
    """
    excluded = len(participants_all) - len(participants_kept)
    cond_counts = defaultdict(int)
    for p in participants_kept:
        cond_counts[p["condition"]] += 1

    def ci_str(vals, n_dec=3):
        if not vals:
            return "\u2014"
        mean, hw = t_ci(vals)
        if hw == 0:
            return "\u2014"
        fmt_str = f"+.{n_dec}f"
        return f"[{format(mean - hw, fmt_str)}, {format(mean + hw, fmt_str)}]"

    L = []
    L.append("# Dilemmas analysis summary")
    L.append("")
    L.append(f"_Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} "
             f"by `analyze.py` from `data.csv` "
             f"(N={len(participants_all)} responses, {len(participants_kept)} analyzed)._")
    L.append("")
    L.append("![Main figure](main_figure.png)")
    L.append("")
    L.append("## Sample")
    L.append("")
    L.append(f"- **Total responses:** {len(participants_all)}")
    L.append(f"- **Excluded (incomplete):** {excluded}")
    L.append(f"- **Analyzed:** {len(participants_kept)}")
    L.append("")
    L.append("| Condition | N |")
    L.append("|---|---|")
    for c in CONDITIONS:
        L.append(f"| {COND_LABELS[c]} | {cond_counts.get(c, 0)} |")
    L.append("")
    L.append("## Hyperparameters")
    L.append("")
    L.append("| Parameter | Value |")
    L.append("|---|---|")
    a_aff = alpha_by_cond.get("inference_affirm")
    a_cat = alpha_by_cond.get("inference_categories")
    if a_aff == a_cat:
        L.append(f"| \u03b1 (feedback prior strength) | **{a_aff}** |")
    else:
        L.append(f"| \u03b1 affirm/remove | **{a_aff}** |")
        L.append(f"| \u03b1 category select | **{a_cat}** |")
    L.append(f"| \u03bb (L2 regularization) | {LAMBDA_PARTIAL} |")
    L.append(f"| D (number of dimensions) | 10 |")
    L.append(f"| T (trials per participant) | 20 |")
    L.append(f"| Inference categories | {N_CATS} (per-dim quintile) |")
    L.append("")

    # H1
    L.append("## H1: predictive accuracy lift")
    L.append("")
    L.append("Per-participant LOO accuracy (augmented \u2212 baseline). "
             "Paired one-sided t-test against 0; Holm-Bonferroni across the 3 conditions.")
    L.append("")
    L.append("| Condition | N | \u0394acc | 95% CI | t | p (one-sided) | p_holm | d_z |")
    L.append("|---|---|---|---|---|---|---|---|")
    for c in CONDITIONS:
        r = h1["by_cond"].get(c) or {}
        n = r.get("n", 0)
        diffs = [row["diff"] for row in (r.get("rows") or [])]
        L.append(f"| {COND_LABELS[c]} | {n} | "
                 f"{fmt(r.get('mean_diff'), '+.3f')} | {ci_str(diffs, 3)} | "
                 f"{fmt(r.get('t'), '+.2f')} | "
                 f"{fmt(r.get('p_one_sided'), '.4f')} | "
                 f"{fmt(r.get('p_holm'), '.4f')} | "
                 f"{fmt(r.get('d_z'), '+.2f')} |")
    L.append("")

    # H2
    L.append("## H2: summary preference")
    L.append("")
    L.append("Signed 6-point Likert (positive = preferred augmented summary). "
             "One-sample Wilcoxon, alternative > 0; Holm-Bonferroni across the "
             "two inference conditions. `choice_only` is shown as a manipulation "
             "check (marked *mc*) and is not part of the H2 family.")
    L.append("")
    L.append("| Condition | N | mean | 95% CI | median | W | p (one-sided) | p_holm | r_rb |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for c in CONDITIONS:
        r = h2.get(c) or {}
        n = r.get("n", 0)
        vals = [row["signed"] for row in (r.get("rows") or [])]
        marker = " *(mc)*" if r.get("is_manipulation_check") else ""
        L.append(f"| {COND_LABELS[c]}{marker} | {n} | "
                 f"{fmt(r.get('mean'), '+.2f')} | {ci_str(vals, 2)} | "
                 f"{fmt(r.get('median'), '+.1f')} | "
                 f"{fmt(r.get('W'), '.1f')} | "
                 f"{fmt(r.get('p_one_sided'), '.4f')} | "
                 f"{fmt(r.get('p_holm'), '.4f')} | "
                 f"{fmt(r.get('rb'), '+.2f')} |")
    L.append("")

    # H3
    L.append("## H3: prediction endorsement")
    L.append("")
    L.append("Per-participant paired difference (augmented \u2212 baseline) on a "
             "6-point accuracy rating. One-sample Wilcoxon, alternative > 0; "
             "Holm-Bonferroni across the 3 conditions.")
    L.append("")
    L.append("| Condition | N | mean \u0394 | 95% CI | median | W | p (one-sided) | p_holm | r_rb |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for c in CONDITIONS:
        r = h3.get(c) or {}
        n = r.get("n", 0)
        vals = [row["diff"] for row in (r.get("rows") or [])]
        L.append(f"| {COND_LABELS[c]} | {n} | "
                 f"{fmt(r.get('mean'), '+.2f')} | {ci_str(vals, 2)} | "
                 f"{fmt(r.get('median'), '+.1f')} | "
                 f"{fmt(r.get('W'), '.1f')} | "
                 f"{fmt(r.get('p_one_sided'), '.4f')} | "
                 f"{fmt(r.get('p_holm'), '.4f')} | "
                 f"{fmt(r.get('rb'), '+.2f')} |")
    L.append("")

    L.append("## Notes")
    L.append("")
    L.append("- **Sign convention:** positive = preferred augmented model. "
             "In `choice_only`, augmented = semantic projection (vs random); "
             "in inference conditions, augmented = semantic projection + "
             "feedback prior (vs semantic projection alone).")
    L.append("- **Inclusion:** participants who completed all 20 trials, the "
             "summary comparison, and both prediction ratings.")
    L.append("- **All p-values are one-sided.** `p_holm` adjusts within each "
             "hypothesis family; H2 corrects across the two inference conditions "
             "only (`choice_only` H2 is a manipulation check).")
    L.append("- **CIs:** 95%, t-distribution with df = n\u22121.")
    L.append("- **Effect sizes:** d_z (paired Cohen's d) for H1; r_rb "
             "(rank-biserial correlation) for H2 and H3.")
    L.append("")

    with open(out_path, "w") as f:
        f.write("\n".join(L))


# ============================================================================
# Per-participant CSV (for downstream analysis or spot-checking)
# ============================================================================
def write_per_participant_csv(participants, h1, h2, h3, out_path):
    h1_lookup = {r["pid"]: r for r in h1["raw_loo"]}
    rows = []
    for p in participants:
        pid = p.get("participant_id")
        cond = p.get("condition")
        loo = h1_lookup.get(pid, {})
        signed = decode_signed_likert(p)
        pdiff = decode_pred_diff(p)
        rows.append({
            "participant_id": pid,
            "qualtrics_response_id": p.get("_qualtrics_response_id"),
            "condition": cond,
            "domain": p.get("domain"),
            "n_trials": len(p.get("responses") or []),
            "loo_random":     loo.get("random_projection"),
            "loo_proj_only":  loo.get("projection_only"),
            "loo_proj_alpha": loo.get("projection_alpha"),
            "h1_augmented":   loo.get(ROLE_TO_MODEL.get(cond, {}).get("augmented")),
            "h1_baseline":    loo.get(ROLE_TO_MODEL.get(cond, {}).get("baseline")),
            "h2_signed_likert": signed,
            "h3_aug_minus_base": pdiff,
        })
    pd.DataFrame(rows).to_csv(out_path, index=False)


# ============================================================================
# Main
# ============================================================================
def main():
    global DATA_PATH, OUT_DIR, FEEDBACK_ALPHA, LAMBDA_PARTIAL, FEEDBACK_ALPHA_BY_COND

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=None,
                        help=f"Qualtrics CSV path (default: {DATA_PATH})")
    parser.add_argument("--out-dir", default=None,
                        help="Output directory "
                             "(default: <data parent>/analysis_outputs)")
    parser.add_argument("--alpha", type=float, default=None,
                        help=f"Feedback prior strength \u03b1 applied to BOTH "
                             f"inference conditions, unless overridden by "
                             f"--alpha-affirm / --alpha-categories "
                             f"(default: {FEEDBACK_ALPHA})")
    parser.add_argument("--alpha-affirm", type=float, default=None,
                        dest="alpha_affirm",
                        help="Feedback prior strength \u03b1 for the "
                             "inference_affirm condition only. Overrides "
                             "--alpha for that cell.")
    parser.add_argument("--alpha-categories", type=float, default=None,
                        dest="alpha_categories",
                        help="Feedback prior strength \u03b1 for the "
                             "inference_categories condition only. Overrides "
                             "--alpha for that cell.")
    parser.add_argument("--lambda-partial", type=float, default=None,
                        dest="lambda_partial",
                        help=f"L2 regularization \u03bb "
                             f"(default: {LAMBDA_PARTIAL})")
    args = parser.parse_args()

    # Override module-level globals so existing function calls (which reference
    # these names at call time, not import time) pick up the overrides.
    if args.data is not None:
        DATA_PATH = Path(args.data).resolve()
    if args.out_dir is not None:
        OUT_DIR = Path(args.out_dir).resolve()
    elif args.data is not None:
        # Auto-route outputs alongside the data file when --data is given
        # without --out-dir, so dilemmas/analysis_outputs isn't clobbered.
        OUT_DIR = DATA_PATH.parent / "analysis_outputs"
    OUT_DIR.mkdir(exist_ok=True, parents=True)
    if args.lambda_partial is not None:
        LAMBDA_PARTIAL = float(args.lambda_partial)

    # Resolve per-condition alphas. Precedence (per cell):
    #   --alpha-<cond>  >  --alpha  >  module default (FEEDBACK_ALPHA == 2.0)
    base_alpha = float(args.alpha) if args.alpha is not None else FEEDBACK_ALPHA
    alpha_affirm = (float(args.alpha_affirm)
                    if args.alpha_affirm is not None else base_alpha)
    alpha_categories = (float(args.alpha_categories)
                        if args.alpha_categories is not None else base_alpha)
    FEEDBACK_ALPHA_BY_COND = {
        "inference_affirm":     alpha_affirm,
        "inference_categories": alpha_categories,
    }
    # Keep the scalar in sync with --alpha for downstream display (figure
    # suptitle, summary.md, summary.json). When per-condition flags diverge,
    # the scalar reflects --alpha (or the default), and the per-condition
    # values are reported separately.
    FEEDBACK_ALPHA = base_alpha

    print(f"Reading {DATA_PATH}")
    print(f"  Output dir:       {OUT_DIR}")
    if alpha_affirm == alpha_categories:
        print(f"  \u03b1 (feedback):     {alpha_affirm}  (both inference conds)")
    else:
        print(f"  \u03b1 (affirm):       {alpha_affirm}")
        print(f"  \u03b1 (categories):   {alpha_categories}")
    print(f"  \u03bb (L2 regulariz): {LAMBDA_PARTIAL}")
    df = load_qualtrics_csv(DATA_PATH)
    print(f"  CSV rows (after metadata skip): {len(df)}")

    participants_all = parse_participants(df)
    print(f"  Participants parsed:            {len(participants_all)}")

    participants = [p for p in participants_all if is_complete(p)]
    print(f"  Participants complete:          {len(participants)}")

    domains = sorted({p.get("domain") for p in participants if p.get("domain")})
    print(f"  Domains in data: {domains}")
    domain_assets_by_domain = {}
    midpoints_by_domain = {}
    for d in domains:
        try:
            assets = load_domain_assets(d)
            domain_assets_by_domain[d] = assets
            midpoints_by_domain[d] = compute_dim_midpoints(
                assets["trial_projections"], assets["dim_ids"], n_cats=N_CATS)
            print(f"    [{d}] n_dims={assets['n_dims']}, "
                  f"n_pairs={len(assets['trial_projections'])}")
        except FileNotFoundError as e:
            print(f"    [{d}] WARNING: missing files in {PROJECTIONS_DIR/d}: {e}")

    print("\nRunning H1 (LOO accuracy)...")
    h1 = run_h1(participants, domain_assets_by_domain, midpoints_by_domain)
    print("Running H2 (summary Likert)...")
    h2 = run_h2(participants)
    print("Running H3 (prediction rating diff)...")
    h3 = run_h3(participants)

    summary = {
        "n_total":    len(participants_all),
        "n_complete": len(participants),
        "constants": {
            "lambda_partial": LAMBDA_PARTIAL,
            "feedback_alpha": FEEDBACK_ALPHA,
            "feedback_alpha_by_cond": FEEDBACK_ALPHA_BY_COND,
            "newton_iters":   NEWTON_ITERS,
            "n_cats":         N_CATS,
        },
        "role_to_model": ROLE_TO_MODEL,
        "h1": h1["by_cond"],
        "h1_loo_per_participant": h1["raw_loo"],
        "h2": h2,
        "h3": h3,
    }
    summary_path = OUT_DIR / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, cls=NPEncoder)
    print(f"\nWrote: {summary_path}")

    csv_path = OUT_DIR / "per_participant.csv"
    write_per_participant_csv(participants, h1, h2, h3, csv_path)
    print(f"Wrote: {csv_path}")

    fig_path = OUT_DIR / "main_figure.png"
    fig_main(h1, h2, h3, fig_path, alpha_by_cond=FEEDBACK_ALPHA_BY_COND)
    print(f"Wrote: {fig_path}")

    summary_md_path = OUT_DIR / "summary.md"
    write_summary_md(participants_all, participants, h1, h2, h3,
                     FEEDBACK_ALPHA_BY_COND, summary_md_path)
    print(f"Wrote: {summary_md_path}")

    print()
    print_report(participants_all, participants, h1, h2, h3)


if __name__ == "__main__":
    main()
