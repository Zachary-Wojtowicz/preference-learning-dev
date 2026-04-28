#!/usr/bin/env python3
"""End-to-end test for the evaluation-screen fitters.

Loads movies_100 data, simulates a participant who consistently picks the
'higher Action Intensity' option, runs the same Newton+L2 fits the JS does,
and prints out which dimensions get inferred (top 10 with quintile categories)
under standard vs partial.

This is a sanity check — both fits should land on Action Intensity at the top,
with related dimensions nearby. Use the printed JSON in the browser console
(window.__lastEvalResult) to confirm parity once the page is wired up.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB  = os.path.join(ROOT, "web-interface")

DOMAIN = sys.argv[1] if len(sys.argv) > 1 else "movies_100"
N_FEEDBACK = int(sys.argv[2]) if len(sys.argv) > 2 else 20
TARGET_DIM_NAME = sys.argv[3] if len(sys.argv) > 3 else "Action Intensity"

def sigmoid(x): return 1 / (1 + np.exp(-np.clip(x, -20, 20)))

def fit_standard(D, y, lam, max_iter=15):
    T = len(D); alpha = np.zeros(T)
    for _ in range(max_iter):
        u = D @ alpha
        p = sigmoid(u); w = p * (1 - p)
        rhs = -(p - y + lam * alpha)
        A = (w[:, None] * D) + lam * np.eye(T)
        try: dA = np.linalg.solve(A, rhs)
        except np.linalg.LinAlgError: break
        alpha += dA
        if np.max(np.abs(dA)) < 1e-7: break
    return alpha

def fit_partial(U, y, G, beta0, lam, max_iter=15):
    T, K = U.shape; beta = beta0.copy()
    for _ in range(max_iter):
        u = U @ beta
        p = sigmoid(u); w = p * (1 - p)
        grad = U.T @ (p - y) + lam * G @ (beta - beta0)
        H = U.T @ (w[:, None] * U) + lam * G
        try: dB = np.linalg.solve(H, -grad)
        except np.linalg.LinAlgError: break
        beta += dB
        if np.max(np.abs(dB)) < 1e-7: break
    return beta

def categorize(scores, dims, n_show, categories):
    abs_idx = np.argsort(-np.abs(scores))[:n_show]
    ordered = sorted(abs_idx, key=lambda i: -scores[i])
    n_cats = len(categories); per_bin = (len(ordered) + n_cats - 1) // n_cats
    out = []
    for rank, i in enumerate(ordered):
        bin_from_top = rank // per_bin
        cat = categories[n_cats - 1 - min(bin_from_top, n_cats - 1)]
        out.append({"dim": dims[i].get("name") or dims[i].get("label"), "cat": cat["label"], "score": float(scores[i])})
    return out

def main():
    out_dir = os.path.join(WEB, "outputs", DOMAIN)
    with open(os.path.join(out_dir, "trials.json")) as f: trials = json.load(f)
    with open(os.path.join(out_dir, "trial_projections.json")) as f: tp = json.load(f)
    with open(os.path.join(out_dir, "experiment_config.json")) as f: cfg = json.load(f)
    G = np.array(cfg["gram_matrix"], dtype=np.float64)
    dims = cfg["dimensions"]; cats = cfg["inference_categories"]
    K = len(dims)
    target_idx = next(i for i, d in enumerate(dims) if (d.get("name") or d.get("label")) == TARGET_DIM_NAME)
    print(f"Target dim: {TARGET_DIM_NAME} (index {target_idx})")

    # Load delta gram bin
    bin_path = os.path.join(out_dir, "delta_gram.bin")
    flat = np.fromfile(bin_path, dtype=np.float32)
    n_pool = int(round(np.sqrt(flat.size)))
    D_full = flat.reshape(n_pool, n_pool).astype(np.float64)

    # Simulate participant: pick first N_FEEDBACK trials, choose option with higher target_idx projection
    rng = np.random.default_rng(42)
    pool = rng.permutation(len(trials))[:N_FEEDBACK]
    y = np.zeros(N_FEEDBACK)
    U = np.zeros((N_FEEDBACK, K))
    for i, p in enumerate(pool):
        proj = tp[p]["raw_projection"]
        U[i] = proj
        # If trial's projection of (a-b) on target dim > 0, A is higher → choose A (y=1)
        y[i] = 1.0 if proj[target_idx] > 0 else 0.0
    D = D_full[np.ix_(pool, pool)]

    lam_s = cfg["comparison"]["lambda_standard"]
    lam_p = cfg["comparison"]["lambda_partial"]
    n_show = cfg["comparison"]["n_dimensions_shown"]

    # Standard fit
    alpha = fit_standard(D, y, lam_s)
    scores_std = U.T @ alpha   # K-vec: theta·v_k = sum_t alpha_t * (V delta_t)[k]

    # Partial fit (no multipliers — choice-only path)
    beta0_zero = np.zeros(K)
    beta_p = fit_partial(U, y, G, beta0_zero, lam_p)
    scores_part = G @ beta_p

    # Simulate inference categories: pretend participant marked "love" on target_idx every trial
    multipliers_mean = np.zeros(K); multipliers_mean[target_idx] = 1.5
    beta0_inf = np.linalg.solve(G, multipliers_mean)
    beta_inf = fit_partial(U, y, G, beta0_inf, lam_p)
    scores_inf = G @ beta_inf

    print(f"\n=== STANDARD (kernel logreg, lambda={lam_s}) ===")
    for entry in categorize(scores_std, dims, n_show, cats):
        print(f"  {entry['cat']:>16}  {entry['dim']:<30}  score={entry['score']:+.4f}")

    print(f"\n=== PARTIAL (K-dim, lambda={lam_p}, no multipliers) ===")
    for entry in categorize(scores_part, dims, n_show, cats):
        print(f"  {entry['cat']:>16}  {entry['dim']:<30}  score={entry['score']:+.4f}")

    print(f"\n=== PARTIAL + INFERENCE PRIOR ('love {TARGET_DIM_NAME}') ===")
    for entry in categorize(scores_inf, dims, n_show, cats):
        print(f"  {entry['cat']:>16}  {entry['dim']:<30}  score={entry['score']:+.4f}")

    # Sanity check: target dim should be top-ranked in all three
    top_std  = int(np.argmax(np.abs(scores_std)))
    top_part = int(np.argmax(np.abs(scores_part)))
    top_inf  = int(np.argmax(np.abs(scores_inf)))
    print(f"\nTop dim by |score|: standard={dims[top_std].get('name')}, partial={dims[top_part].get('name')}, partial+inf={dims[top_inf].get('name')}")
    assert top_std == target_idx, "Standard fit failed to identify target dim"
    assert top_part == target_idx, "Partial fit failed to identify target dim"
    assert top_inf == target_idx, "Partial+inference fit failed to identify target dim"
    print("All sanity checks passed.")

if __name__ == "__main__":
    main()
