"""
Select the top-D dimensions from the full pipeline outputs and produce
a new output folder for the web experiment.

Reads the full K-dimension outputs (directions, dimension_names, bt_scores,
trial_projections, etc.) and produces a D-dimension version by keeping only
the top-D directions ranked by variance of item projections (the same
criterion used by --n-dims in the simulation and learning curves).

Also precomputes a random D-dim orthonormal projection (V_rand, seeded at
seed+777 to match the simulation/pilot) and stores random_projection per
trial alongside raw_projection. This lets the web interface fit a random
projection baseline without needing access to raw embeddings.

Usage:
  cd preference-learning-dev
  python experiments/select_top_dims.py \\
    --directions method_directions/outputs/dailydilemmas/directions.npz \\
    --embeddings-parquet datasets/dailydilemmas/selected_actions-embedded.parquet \\
    --experiment-dir web-interface/outputs/dailydilemmas \\
    --n-dims 10 \\
    --output-dir web-interface/outputs/dailydilemmas_top10
"""

import argparse
import json
import shutil
from pathlib import Path

import numpy as np


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--directions", required=True,
                   help="Path to directions.npz (full K dimensions).")
    p.add_argument("--embeddings-parquet", required=True,
                   help="Path to embeddings parquet file (for computing "
                        "projection variance and random projections).")
    p.add_argument("--experiment-dir", required=True,
                   help="Path to the full experiment output directory "
                        "(e.g., web-interface/outputs/dailydilemmas).")
    p.add_argument("--n-dims", type=int, required=True,
                   help="Number of top dimensions to keep.")
    p.add_argument("--output-dir", required=True,
                   help="Where to write the reduced-dimension outputs.")
    p.add_argument("--option-id-column", default="action_id",
                   help="Column name in embeddings parquet for option IDs.")
    p.add_argument("--seed", type=int, default=42,
                   help="Base seed; random projection uses seed+777.")
    return p.parse_args()


def generate_random_projection(D, d, seed):
    """Generate a D x d orthonormal random projection via QR decomposition.
    Uses seed+777 to match the simulation/pilot's random projection seeding."""
    rng = np.random.default_rng(seed + 777)
    A = rng.standard_normal((d, D))
    Q, _ = np.linalg.qr(A)  # Q is d x D with orthonormal columns
    return Q.T  # D x d


def main():
    args = parse_args()
    src = Path(args.experiment_dir)
    dst = Path(args.output_dir)
    dst.mkdir(parents=True, exist_ok=True)

    # 1. Load directions and embeddings
    npz = np.load(args.directions)
    V_raw = npz["directions_raw"].astype(np.float64)
    K_full, d = V_raw.shape
    norms = np.linalg.norm(V_raw, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    V = V_raw / norms  # unit-normalize

    # Load embeddings
    import pandas as pd
    parq = pd.read_parquet(args.embeddings_parquet)
    parq[args.option_id_column] = parq[args.option_id_column].astype(str)
    parq = parq.sort_values(args.option_id_column).reset_index(drop=True)
    option_ids = parq[args.option_id_column].tolist()
    embeddings = np.stack(parq["embedding"].apply(np.array).values).astype(np.float64)
    oid_to_idx = {oid: i for i, oid in enumerate(option_ids)}

    # 2. Select top-D dims by variance of item projections
    centered = embeddings - embeddings.mean(axis=0)
    proj_var = np.var(centered @ V.T, axis=0)  # (K_full,)
    top_idx = np.argsort(-proj_var)[:args.n_dims]
    top_idx.sort()  # preserve original ordering
    D = len(top_idx)

    print(f"Full K={K_full}, selecting top D={D} by variance of item projections")
    print(f"  Selected indices: {top_idx.tolist()}")
    print(f"  Projection variances: {proj_var[top_idx].round(6).tolist()}")
    print(f"  Dropped: {[i for i in range(K_full) if i not in top_idx]}")

    V_selected = V[top_idx]  # D x d (unit-normalized)

    # 3. Generate random projection V_rand (D x d, orthonormal)
    V_rand = generate_random_projection(D, d, args.seed)
    print(f"  Generated random projection V_rand: {V_rand.shape}, "
          f"orthonormal check max|V V^T - I|={np.abs(V_rand @ V_rand.T - np.eye(D)).max():.6e}")

    # 4. Rewrite dimension_names.json
    dim_names_path = src / "dimension_names.json"
    if dim_names_path.exists():
        with open(dim_names_path) as f:
            all_names = json.load(f)
        selected_names = [all_names[i] for i in top_idx]
        with open(dst / "dimension_names.json", "w") as f:
            json.dump(selected_names, f, indent=2)
        print(f"  dimension_names.json: {K_full} -> {D} entries")
        for i, (idx, name) in enumerate(zip(top_idx, selected_names)):
            label = name.get("name", name.get("label", f"dim_{idx}"))
            print(f"    [{i}] (was {idx}): {label}")
    else:
        print("  WARNING: dimension_names.json not found in source")

    # 5. Rewrite trial_projections.json: trim to D dims AND add random_projection
    tp_path = src / "trial_projections.json"
    if tp_path.exists():
        with open(tp_path) as f:
            trial_projections = json.load(f)
        n_added_rand = 0
        for tp in trial_projections:
            # Trim raw_projection to top-D
            if "raw_projection" in tp:
                full_proj = tp["raw_projection"]
                tp["raw_projection"] = [full_proj[i] for i in top_idx]
            if "option_a_projection" in tp:
                tp["option_a_projection"] = [tp["option_a_projection"][i] for i in top_idx]
            if "option_b_projection" in tp:
                tp["option_b_projection"] = [tp["option_b_projection"][i] for i in top_idx]
            # Compute random projection: V_rand @ (phi_a - phi_b)
            oa_id = str(tp.get("option_a_id", ""))
            ob_id = str(tp.get("option_b_id", ""))
            if oa_id in oid_to_idx and ob_id in oid_to_idx:
                phi_a = embeddings[oid_to_idx[oa_id]]
                phi_b = embeddings[oid_to_idx[ob_id]]
                delta = phi_a - phi_b
                tp["random_projection"] = (V_rand @ delta).tolist()
                n_added_rand += 1
            else:
                tp["random_projection"] = [0.0] * D  # fallback (shouldn't happen)
        with open(dst / "trial_projections.json", "w") as f:
            json.dump(trial_projections, f)
        print(f"  trial_projections.json: trimmed to {D} dims, "
              f"added random_projection for {n_added_rand}/{len(trial_projections)} trials")
    else:
        print("  WARNING: trial_projections.json not found in source")

    # 6. Copy experiment_config.json and update n_dims field
    config_path = src / "experiment_config.json"
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
        config["n_dims"] = D
        config["n_dims_full"] = K_full
        config["selected_dim_indices"] = top_idx.tolist()
        # Filter dimensions list to just the top-D
        if "dimensions" in config and isinstance(config["dimensions"], list):
            config["dimensions"] = [config["dimensions"][i] for i in top_idx]
        # Filter gram_matrix to D x D submatrix (kept for backward compat,
        # but the updated JS no longer uses it for fitting)
        if "gram_matrix" in config and isinstance(config["gram_matrix"], list):
            G_full = np.array(config["gram_matrix"])
            G_sub = G_full[np.ix_(top_idx, top_idx)]
            config["gram_matrix"] = G_sub.tolist()
        with open(dst / "experiment_config.json", "w") as f:
            json.dump(config, f, indent=2)
        print(f"  experiment_config.json: added n_dims={D}, filtered dimensions and gram_matrix")
    else:
        print("  WARNING: experiment_config.json not found in source")

    # 7. Copy other files unchanged. Note: delta_gram.bin and option_gram.bin
    # are no longer used by the updated JS (no kernel fit), but we copy them
    # for backward compatibility.
    same_dir = src.resolve() == dst.resolve()

    # trials.json: filter sliders down to the top-D dims so feedback IDs
    # match the dimension IDs in experiment_config.json. Without this,
    # users would be shown sliders for dims that aren't in the model and
    # their feedback would be silently dropped.
    trials_path = src / "trials.json"
    if trials_path.exists():
        with open(trials_path) as f:
            trials_data = json.load(f)
        # top_idx contains 0-indexed selected dim positions in the FULL ordering.
        # Slider dimension_id is 1-indexed in trials.json (matches the original
        # full ordering), so we keep sliders whose (dimension_id - 1) is in top_idx.
        top_idx_set = set(int(i) for i in top_idx.tolist())
        n_kept_total, n_orig_total = 0, 0
        for trial in trials_data:
            if "sliders" not in trial or not isinstance(trial["sliders"], list):
                continue
            n_orig_total += len(trial["sliders"])
            kept = []
            for s in trial["sliders"]:
                did = s.get("dimension_id")
                if did is not None and (int(did) - 1) in top_idx_set:
                    kept.append(s)
            trial["sliders"] = kept
            n_kept_total += len(kept)
        with open(dst / "trials.json", "w") as f:
            json.dump(trials_data, f)
        print(f"  trials.json: filtered sliders {n_orig_total} -> {n_kept_total} "
              f"({n_kept_total // max(len(trials_data), 1)} per trial)")

    for fname in ["polished_labels.json", "option_pairs.json",
                  "predefined_pairs.json", "delta_gram.bin", "delta_gram_meta.json",
                  "option_gram.bin", "option_gram_meta.json", "option_projections.json"]:
        fpath = src / fname
        if fpath.exists():
            if same_dir:
                print(f"  {fname}: already in place (in-place update)")
            else:
                shutil.copy2(fpath, dst / fname)
                print(f"  {fname}: copied unchanged")

    # 8. Save the selected directions and V_rand as a new npz
    np.savez(dst / "directions.npz",
             directions_raw=npz["directions_raw"][top_idx],
             mean_embedding=npz["mean_embedding"],
             V_rand=V_rand)
    print(f"  directions.npz: saved {D} directions + V_rand")

    # 9. Summary
    V_norm = V_selected
    G = V_norm @ V_norm.T
    print(f"\nResult: D={D}, cond(G)={np.linalg.cond(G):.1f}, "
          f"max off-diag |G|={np.abs(G - np.eye(D)).max():.3f}")
    print(f"Output written to: {dst}")


if __name__ == "__main__":
    main()

