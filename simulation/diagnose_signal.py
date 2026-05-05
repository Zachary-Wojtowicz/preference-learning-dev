#!/usr/bin/env python3
"""Diagnose the choice signal magnitude in the simulation."""
import numpy as np
import pandas as pd
import json

# Load
parquet = pd.read_parquet("datasets/dailydilemmas/selected_actions-embedded.parquet")
parquet["option_id"] = parquet["action_id"].astype(str)
parquet = parquet.sort_values("option_id").reset_index(drop=True)
embeddings = np.stack(parquet["embedding"].apply(np.array).values).astype(np.float64)

npz = np.load("method_directions/outputs/dailydilemmas/directions.npz")
V_raw = npz["directions_raw"].astype(np.float64)
mu = npz["mean_embedding"].astype(np.float64)
norms = np.linalg.norm(V_raw, axis=1, keepdims=True)
norms[norms == 0] = 1.0
V = V_raw / norms

# Top 10 by variance
centered = embeddings - embeddings.mean(axis=0)
proj_var = np.var(centered @ V.T, axis=0)
top_idx = np.argsort(-proj_var)[:10]
top_idx.sort()
V = V[top_idx]

with open("datasets/dailydilemmas/predefined_pairs.json") as f:
    pairs_raw = json.load(f)
id_to_idx = {oid: i for i, oid in enumerate(parquet["option_id"].tolist())}
pairs = [(id_to_idx[str(p["option_a_id"])], id_to_idx[str(p["option_b_id"])])
         for p in pairs_raw if str(p["option_a_id"]) in id_to_idx and str(p["option_b_id"]) in id_to_idx]
print(f"Pairs: {len(pairs)}")

# Compute U for all pairs
rng = np.random.default_rng(42)
sample = rng.choice(len(pairs), size=min(2000, len(pairs)), replace=False)
deltas = np.array([embeddings[pairs[i][0]] - embeddings[pairs[i][1]] for i in sample])
U = deltas @ V.T  # (n, K)
print(f"U shape: {U.shape}")
print(f"U scale: mean abs = {np.abs(U).mean():.4f}, std = {U.std():.4f}, max abs = {np.abs(U).max():.4f}")
print(f"Per-dim std: {U.std(axis=0)}")

# Synthesize a sparse user with mag in [1.5, 3.0]
w_star = np.zeros(10)
active = rng.choice(10, size=3, replace=False)
w_star[active] = rng.uniform(1.5, 3.0, size=3) * rng.choice([-1, 1], size=3)
print(f"\nSynthetic user w_star: {w_star}")
print(f"||w_star|| = {np.linalg.norm(w_star):.3f}")

# Choice signal: U · w_star
signals = U @ w_star
print(f"\nChoice signal U·w_star: mean abs = {np.abs(signals).mean():.4f}, std = {signals.std():.4f}")

# At beta=2.0, what's the prob of choosing 'correct'?
beta = 2.0
correct_probs = 1.0 / (1.0 + np.exp(-beta * np.abs(signals)))
print(f"\nAt beta={beta}, mean P(correct) = {correct_probs.mean():.3f}")
print(f"This is the BAYES-OPTIMAL accuracy ceiling for this beta.")

# At beta=10
beta = 10.0
correct_probs = 1.0 / (1.0 + np.exp(-beta * np.abs(signals)))
print(f"At beta={beta}, mean P(correct) = {correct_probs.mean():.3f}")

# Show U values are in what range
print(f"\n|U| values are SMALL because embeddings are already nearly unit-norm")
print(f"|phi_a - phi_b| typical magnitude: {np.linalg.norm(deltas, axis=1).mean():.3f}")
print(f"After projection onto K=10 directions: {np.linalg.norm(U, axis=1).mean():.3f}")
