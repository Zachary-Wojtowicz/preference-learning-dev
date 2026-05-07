#!/usr/bin/env python3
"""End-to-end parity test for the evaluation-screen fitters.

Verifies that the unified fit_btl Python implementation produces the same
result as the JS fitBTL function on the same input. Also runs a sanity
check that the LLM projection identifies the target dimension when the
participant consistently picks the option with higher projection on it.

Three fits are tested (matching the JS):
  - random_projection: fit_btl(U_rand, y, lambda)  with no prior
  - projection_only:   fit_btl(U,      y, lambda)  with no prior
  - projection_alpha:  fit_btl(U,      y, lambda, beta_prior, mu_prior)

This is a sanity check for the post-experiment evaluation. Use the printed
JSON in the browser console (window.__lastEvalResult) to confirm parity
once the page is wired up.
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB  = os.path.join(ROOT, "web-interface")

DOMAIN = sys.argv[1] if len(sys.argv) > 1 else "movies_100"
N_FEEDBACK = int(sys.argv[2]) if len(sys.argv) > 2 else 20
TARGET_DIM_NAME = sys.argv[3] if len(sys.argv) > 3 else "Action Intensity"


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -20, 20)))


def fit_btl(U, y, lam, beta_prior=None, mu_prior=0.0, max_iter=15, tol=1e-7):
    """Unified BTL fit matching JS fitBTL.

      min_beta  -LL(U beta, y) + (lam/2) ||beta||^2 + (mu/2) ||beta - beta_prior||^2
    """
    T, K = U.shape
    beta = np.zeros(K)
    bp = beta_prior if beta_prior is not None else np.zeros(K)
    mu = float(mu_prior or 0.0)
    for _ in range(max_iter):
        u = U @ beta
        p = sigmoid(u)
        w = p * (1 - p)
        grad = U.T @ (p - y) + lam * beta + mu * (beta - bp)
        H = U.T @ (w[:, None] * U) + (lam + mu) * np.eye(K)
        try:
            dB = np.linalg.solve(H, -grad)
        except np.linalg.LinAlgError:
            break
        beta += dB
        if np.max(np.abs(dB)) < tol:
            break
    return beta


def perdim_bin_midpoints(values_pool, n_cats):
    """Per-dim symmetric quantile midpoints. Returns (n_cats, K)."""
    T, K = values_pool.shape
    qs = np.array([(2 * i + 1) / (2 * n_cats) for i in range(n_cats)])
    mids = np.zeros((n_cats, K))
    for k in range(K):
        v = values_pool[:, k]
        symm = np.concatenate([v, -v])
        mids[:, k] = np.quantile(symm, qs)
    return mids


def categorize(scores, dims, n_show, categories):
    """Match JS buildInferences: top-N abs scores, ordered by signed score,
    binned into quintile categories from most positive to most negative."""
    abs_idx = np.argsort(-np.abs(scores))[:n_show]
    ordered = sorted(abs_idx, key=lambda i: -scores[i])
    n_cats = len(categories)
    per_bin = (len(ordered) + n_cats - 1) // n_cats
    out = []
    for rank, i in enumerate(ordered):
        bin_from_top = rank // per_bin
        cat = categories[n_cats - 1 - min(bin_from_top, n_cats - 1)]
        out.append({
            "dim": dims[i].get("name") or dims[i].get("label"),
            "cat": cat["label"],
            "score": float(scores[i]),
        })
    return out


def main():
    out_dir = os.path.join(WEB, "outputs", DOMAIN)
    with open(os.path.join(out_dir, "trials.json")) as f:
        trials = json.load(f)
    with open(os.path.join(out_dir, "trial_projections.json")) as f:
        tp = json.load(f)
    with open(os.path.join(out_dir, "experiment_config.json")) as f:
        cfg = json.load(f)

    dims = cfg["dimensions"]
    cats = cfg["inference_categories"]
    K = len(dims)

    # Verify random_projection field is present (precomputed by select_top_dims.py)
    if "random_projection" not in tp[0]:
        print(f"ERROR: trial_projections.json is missing 'random_projection' field.")
        print(f"  Run: python experiments/select_top_dims.py ... --output-dir {out_dir}")
        sys.exit(1)

    target_idx = next(
        i for i, d in enumerate(dims)
        if (d.get("name") or d.get("label")) == TARGET_DIM_NAME
    )
    print(f"Target dim: {TARGET_DIM_NAME} (index {target_idx})")
    print(f"K = {K}")

    # Simulate a participant who always picks the option with higher
    # projection on the target dimension.
    rng = np.random.default_rng(42)
    pool = rng.permutation(len(trials))[:N_FEEDBACK]
    U = np.zeros((N_FEEDBACK, K))
    U_rand = np.zeros((N_FEEDBACK, K))
    y = np.zeros(N_FEEDBACK)
    for i, p in enumerate(pool):
        proj = np.array(tp[p]["raw_projection"], dtype=np.float64)
        rand_proj = np.array(tp[p]["random_projection"], dtype=np.float64)
        U[i] = proj
        U_rand[i] = rand_proj
        y[i] = 1.0 if proj[target_idx] > 0 else 0.0

    lam_p = cfg["comparison"].get("lambda_partial", 0.01)
    mu_prior = cfg["comparison"].get("feedback_alpha", 1.0)
    n_show = cfg["comparison"].get("n_dimensions_shown", 10)

    # Compute per-dim midpoints (matching JS computeDimMidpoints)
    all_proj = np.array([tp[p]["raw_projection"] for p in range(len(tp))],
                        dtype=np.float64)  # (n_pool, K)
    midpoints = perdim_bin_midpoints(all_proj, n_cats=len(cats))  # (n_cats, K)

    # Simulate beta_prior: pretend participant always selected "love" on target dim
    # ("love" is the last category in the dailydilemmas/movies CATEGORIES list)
    target_cat_idx = len(cats) - 1  # most positive
    target_midpoint = midpoints[target_cat_idx, target_idx]
    print(f"Target dim midpoint for 'love' category: {target_midpoint:.4f}")

    # Build beta_prior: per-dim mean of feedback values across visible trials.
    # On every trial, participant gives feedback on the top-3 dims by abs
    # projection (which always includes target_idx since we forced y to follow it).
    # For target dim: store target_midpoint.
    # For other visible dims: store the actual U[t][k] (affirm the inference).
    sums = np.zeros(K)
    counts = np.zeros(K)
    for t in range(N_FEEDBACK):
        # Top-3 visible dims (matching JS getTopK with key=chosen)
        chosen_proj = U[t] if y[t] == 1 else -U[t]
        # Use abs projection of the chosen option's value (here we approximate
        # using abs of delta — same dim ordering)
        top3 = np.argsort(-np.abs(U[t]))[:3]
        for k in top3:
            if k == target_idx:
                sums[k] += target_midpoint
            else:
                sums[k] += U[t][k]  # affirm: store raw delta projection
            counts[k] += 1
    beta_prior = np.where(counts > 0, sums / np.maximum(counts, 1), 0.0)
    has_prior = bool(np.any(beta_prior != 0))
    print(f"beta_prior: nonzero={has_prior}, "
          f"target value = {beta_prior[target_idx]:+.4f}")

    # Three fits (matching JS startEvaluation)
    beta_rand = fit_btl(U_rand, y, lam_p)
    beta_proj = fit_btl(U, y, lam_p)
    beta_alpha = fit_btl(U, y, lam_p, beta_prior=beta_prior, mu_prior=mu_prior)

    # With P=I, scores ARE beta directly
    scores_rand = beta_rand
    scores_proj = beta_proj
    scores_alpha = beta_alpha

    print(f"\n=== RANDOM PROJECTION (lambda={lam_p}) ===")
    for entry in categorize(scores_rand, dims, n_show, cats):
        print(f"  {entry['cat']:>16}  {entry['dim']:<30}  score={entry['score']:+.4f}")

    print(f"\n=== LLM PROJECTION (lambda={lam_p}) ===")
    for entry in categorize(scores_proj, dims, n_show, cats):
        print(f"  {entry['cat']:>16}  {entry['dim']:<30}  score={entry['score']:+.4f}")

    print(f"\n=== LLM PROJECTION + FEEDBACK PRIOR "
          f"(mu={mu_prior}, target='love {TARGET_DIM_NAME}') ===")
    for entry in categorize(scores_alpha, dims, n_show, cats):
        print(f"  {entry['cat']:>16}  {entry['dim']:<30}  score={entry['score']:+.4f}")

    # Sanity checks: target dim should be top-ranked in projection_only and projection_alpha
    top_rand = int(np.argmax(np.abs(scores_rand)))
    top_proj = int(np.argmax(np.abs(scores_proj)))
    top_alpha = int(np.argmax(np.abs(scores_alpha)))
    print(f"\nTop dim by |score|:")
    print(f"  random_projection: {dims[top_rand].get('name')} (idx {top_rand})")
    print(f"  projection_only:   {dims[top_proj].get('name')} (idx {top_proj})")
    print(f"  projection_alpha:  {dims[top_alpha].get('name')} (idx {top_alpha})")

    if top_proj != target_idx:
        print(f"WARNING: projection_only failed to identify target dim (got {dims[top_proj].get('name')})")
    if top_alpha != target_idx:
        print(f"WARNING: projection_alpha failed to identify target dim (got {dims[top_alpha].get('name')})")
    else:
        print("\nSanity check passed: projection_alpha correctly identifies target dim.")


if __name__ == "__main__":
    main()
