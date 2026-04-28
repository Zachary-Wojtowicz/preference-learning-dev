#!/usr/bin/env python3
"""Export delta-gram matrix and add comparison config for the model-comparison evaluation screen.

For each domain, produces:
  outputs/<domain>/delta_gram.bin       float32 binary, T_pool x T_pool, row-major
  outputs/<domain>/delta_gram_meta.json {"trial_ids": [...], "n": T_pool}

And updates outputs/<domain>/experiment_config.json with a "comparison" block.

Usage:
  python3 export_eval_data.py                     # all known domains
  python3 export_eval_data.py movies_100 wines_100
"""
import json
import os
import sys
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB  = os.path.join(ROOT, "web-interface")

DOMAINS = {
    "movies_100": {
        "parquet": "datasets/movies_100/movielens-32m-enriched-qwen3emb-100-embedded.parquet",
        "id_col":  "movie_id",
    },
    "scruples_dilemmas": {
        "parquet": "datasets/scruples_dilemmas/selected_actions-embedded.parquet",
        "id_col":  "action_id",
    },
    "wines_100": {
        "parquet": "datasets/wines_100/wines_100-embedded.parquet",
        "id_col":  "wine_id",
    },
    "scruples_200": {
        "parquet": "datasets/scruples_200/scruples_200-embedded.parquet",
        "id_col":  "action_id",
    },
}

DEFAULT_COMPARISON = {
    "lambda_standard":     10.0,
    "lambda_partial":      1.0,
    "slider_prior_weight": 1.0,
    "n_dimensions_shown":  10,
    "show_for_conditions": [
        "choice_only", "choice_readonly_sliders", "choice_adjustable_sliders",
        "choice_checkboxes", "inference_affirm", "inference_categories",
    ],
}

def export_domain(domain: str):
    cfg = DOMAINS[domain]
    parquet_path = os.path.join(ROOT, cfg["parquet"])
    out_dir      = os.path.join(WEB, "outputs", domain)
    trials_path  = os.path.join(out_dir, "trials.json")
    cfg_path     = os.path.join(out_dir, "experiment_config.json")

    if not os.path.exists(parquet_path):
        print(f"  [{domain}] SKIP: parquet not found at {parquet_path}")
        return
    if not os.path.exists(trials_path):
        print(f"  [{domain}] SKIP: trials.json not found")
        return

    df = pd.read_parquet(parquet_path)
    df["__id_str"] = df[cfg["id_col"]].astype(str)
    id_to_emb = {row["__id_str"]: np.asarray(row["embedding"], dtype=np.float32)
                 for _, row in df.iterrows()}

    with open(trials_path) as f:
        trials = json.load(f)

    n = len(trials)
    d = len(next(iter(id_to_emb.values())))
    deltas = np.zeros((n, d), dtype=np.float32)
    trial_ids = []
    for i, t in enumerate(trials):
        a_id = str(t["option_a_id"])
        b_id = str(t["option_b_id"])
        if a_id not in id_to_emb or b_id not in id_to_emb:
            raise RuntimeError(f"{domain} trial {t['trial_id']}: missing embedding for {a_id} or {b_id}")
        deltas[i] = id_to_emb[a_id] - id_to_emb[b_id]
        trial_ids.append(t["trial_id"])

    D = deltas @ deltas.T
    D = D.astype(np.float32)
    print(f"  [{domain}] D: {D.shape}, range [{D.min():.4f}, {D.max():.4f}], diag mean {np.diag(D).mean():.4f}")

    bin_path  = os.path.join(out_dir, "delta_gram.bin")
    meta_path = os.path.join(out_dir, "delta_gram_meta.json")
    D.tofile(bin_path)
    with open(meta_path, "w") as f:
        json.dump({"trial_ids": trial_ids, "n": n, "dtype": "float32", "shape": [n, n]}, f)
    print(f"  [{domain}] wrote {bin_path} ({os.path.getsize(bin_path)//1024} KB)")

    with open(cfg_path) as f:
        ec = json.load(f)
    ec.setdefault("comparison", {})
    for k, v in DEFAULT_COMPARISON.items():
        ec["comparison"].setdefault(k, v)
    with open(cfg_path, "w") as f:
        json.dump(ec, f, indent=2)
    print(f"  [{domain}] updated experiment_config.json comparison block")

if __name__ == "__main__":
    targets = sys.argv[1:] if len(sys.argv) > 1 else list(DOMAINS.keys())
    for d in targets:
        if d not in DOMAINS:
            print(f"Unknown domain: {d}")
            continue
        export_domain(d)
    print("\nDone.")
