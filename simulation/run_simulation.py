"""
Simulated Preference Learning Experiment

Tests the hypothesis: does projecting RLHF gradients onto an interpretable
preference subspace speed up learning and reduce misgeneralization vs. standard
gradient updates?

Synthetic users have known ground-truth preferences over K LLM-generated
dimensions. We compare 4 learning conditions on the same choice sequences.
"""

import argparse
import json
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data(embeddings_parquet: str, bt_scores_csv: str, directions_npz: str,
              option_id_column: str = "movie_id"):
    """Load and align option representations.

    Returns
    -------
    embeddings : (N, d) float64  — φ(aᵢ)
    bt_scores  : (N, K) float64  — s(aᵢ), BTL scores per dimension
    V          : (K, d) float64  — direction matrix (rows = unit-length, NOT orthogonal)
    G_inv      : (K, K) float64  — inverse Gram matrix (V V⊤)⁻¹
    mu         : (d,)  float64   — mean embedding
    option_ids : list of str     — canonical order
    dim_names  : list of str     — dimension names in order of dimension_id
    """
    # --- embeddings ---
    parquet_df = pd.read_parquet(embeddings_parquet)
    parquet_df["option_id"] = parquet_df[option_id_column].astype(str)
    parquet_df = parquet_df.sort_values("option_id").reset_index(drop=True)
    option_ids = parquet_df["option_id"].tolist()
    embeddings = np.stack(parquet_df["embedding"].apply(np.array).values)  # (N, d)

    # --- bt_scores ---
    bt_df = pd.read_csv(bt_scores_csv)
    bt_df["option_id"] = bt_df["option_id"].astype(str)

    # Build dimension ordering by dimension_id
    dim_info = (
        bt_df[["dimension_id", "dimension_name"]]
        .drop_duplicates()
        .sort_values("dimension_id")
    )
    dim_names = dim_info["dimension_name"].tolist()
    dim_ids = dim_info["dimension_id"].tolist()

    # Pivot to (N, K) aligned to option_ids order
    bt_pivot = bt_df.pivot(index="option_id", columns="dimension_id", values="bt_score")
    bt_pivot = bt_pivot[dim_ids]  # ensure column order
    bt_pivot = bt_pivot.loc[option_ids]  # ensure row order
    bt_scores = bt_pivot.values.astype(np.float64)  # (N, K)

    # --- directions (raw, non-orthogonalized) ---
    npz = np.load(directions_npz)
    V_raw = npz["directions_raw"].astype(np.float64)   # (K, d)
    mu = npz["mean_embedding"].astype(np.float64)      # (d,)

    # Normalize each row to unit length (preserve direction, drop magnitude)
    norms = np.linalg.norm(V_raw, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    V = V_raw / norms  # (K, d) — unit-length rows, NOT orthogonal

    # Gram matrix and its (regularized) inverse
    G = V @ V.T  # (K, K) — G_ij = cos(v_i, v_j) since rows are unit-length
    # Tikhonov regularization for numerical stability
    G_reg = G + 1e-6 * np.eye(G.shape[0])
    G_inv = np.linalg.inv(G_reg)  # (K, K)

    print(f"  Gram matrix condition number: {np.linalg.cond(G):.1f}")
    off_diag = G - np.eye(G.shape[0])
    print(f"  Max inter-dimension correlation: {np.abs(off_diag).max():.3f}")

    return embeddings, bt_scores, V, G_inv, mu, option_ids, dim_names


# ---------------------------------------------------------------------------
# Synthetic user generation
# ---------------------------------------------------------------------------

def generate_users(num_users: int, K: int, dim_names: list, rng: np.random.Generator):
    """Return list of user dicts with fields: id, archetype, weights (K,)."""
    users = []

    # --- Archetypal users (hand-designed) ---
    archetypes = build_archetypes(K, dim_names)
    for arch in archetypes:
        users.append({
            "id": len(users),
            "archetype": arch["name"],
            "weights": arch["weights"],
        })

    # --- Random users to fill the rest ---
    n_random = max(0, num_users - len(archetypes))
    random_weights = rng.uniform(-1, 1, size=(n_random, K))
    for i, w in enumerate(random_weights):
        users.append({
            "id": len(users),
            "archetype": f"random_{i}",
            "weights": w,
        })

    return users[:num_users]


def build_archetypes(K: int, dim_names: list):
    """Build a small set of hand-designed archetypes based on dimension names.

    Designed for 25 unipolar dimensions (higher = more of that quality).
    Positive weight = user values that quality; negative = actively avoids it.
    """
    def find_dim(keyword):
        keyword = keyword.lower()
        for i, name in enumerate(dim_names):
            if keyword in name.lower():
                return i
        return None

    def make(name, likes, dislikes=None):
        w = np.zeros(K)
        for kw, val in likes:
            idx = find_dim(kw)
            if idx is not None:
                w[idx] = val
        if dislikes:
            for kw, val in dislikes:
                idx = find_dim(kw)
                if idx is not None:
                    w[idx] = -val
        return {"name": name, "weights": w}

    return [
        make("action_thrill_seeker", [
            ("action", 1.0), ("visual spectacle", 0.8), ("adventure", 0.9),
            ("survival", 0.7), ("suspense", 0.5),
        ], [("romantic", 0.5), ("musical", 0.6)]),

        make("drama_enthusiast", [
            ("emotional", 1.0), ("psychological", 0.9), ("moral", 0.8),
            ("cultural", 0.5),
        ], [("action", 0.6), ("humor", 0.4)]),

        make("scifi_nerd", [
            ("sci-fi", 1.0), ("visual spectacle", 0.7), ("time-loop", 0.8),
            ("adventure", 0.5),
        ], [("historical", 0.5), ("musical", 0.4)]),

        make("comedy_lover", [
            ("humor", 1.0), ("satirical", 0.8), ("ensemble", 0.6),
            ("underdog", 0.4),
        ], [("war", 0.5), ("suspense", 0.3)]),

        make("history_buff", [
            ("historical", 1.0), ("cultural", 0.8), ("political", 0.9),
            ("war", 0.7),
        ], [("sci-fi", 0.6), ("time-loop", 0.5)]),

        make("family_movie_night", [
            ("family focus", 0.9), ("family-friendly", 1.0), ("coming-of-age", 0.7),
            ("underdog", 0.6), ("humor", 0.4),
        ], [("war", 0.6), ("political", 0.4)]),

        make("art_house_fan", [
            ("psychological", 1.0), ("nostalgic", 0.7), ("cultural", 0.8),
            ("satirical", 0.6), ("moral", 0.5),
        ], [("action", 0.7), ("family-friendly", 0.5)]),

        make("musical_fan", [
            ("musical", 1.0), ("nostalgic", 0.7), ("ensemble", 0.6),
            ("emotional", 0.8),
        ], [("war", 0.5), ("survival", 0.4)]),

        make("social_justice_advocate", [
            ("social justice", 1.0), ("cultural", 0.8), ("moral", 0.7),
            ("coming-of-age", 0.5),
        ], [("war", 0.3)]),

        make("suspense_thriller_fan", [
            ("suspense", 1.0), ("psychological", 0.8), ("survival", 0.7),
            ("political", 0.5),
        ], [("musical", 0.5), ("family-friendly", 0.4)]),
    ]


# ---------------------------------------------------------------------------
# Choice and slider models
# ---------------------------------------------------------------------------

def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -50, 50)))


def user_chooses(u_a: float, u_b: float, beta: float, rng: np.random.Generator) -> int:
    """Return 1 if option a is chosen, 0 if option b is chosen."""
    p = sigmoid(beta * (u_a - u_b))
    return int(rng.random() < p)


def slider_adjustment(
    phi_a: np.ndarray,
    phi_b: np.ndarray,
    w_star: np.ndarray,
    s_a: np.ndarray,
    s_b: np.ndarray,
    V: np.ndarray,
    mu: np.ndarray,
    noise: float,
) -> np.ndarray:
    """Compute adjusted slider values λ_adjusted ∈ ℝᴷ.

    The interface shows sliders initialized to V(φ(a) − φ(b)).  The user
    adjusts MAGNITUDES to reflect which dimensions mattered for their
    choice.  Direction comes from the choice itself via (y − pred) in the
    update rule, so slider values should be non-negative importance weights
    scaled by the model’s projection magnitude.

    We model the user’s adjustment as:
        importance  = |w*|                      (how much the user cares)
        λ_model     = V(φ(a) − φ(b))            (model’s per-dimension diff)
        λ_adjusted  = (1-noise) · importance ⊙ λ_model + noise · λ_model

    At noise=0, dimensions are re-weighted by user importance.
    At noise=1, sliders are left at the model’s default (= projected update).
    The sign of each component is preserved from λ_model; direction comes
    from (y − pred) in the update function.
    """
    delta_phi = phi_a - phi_b          # (d,)
    lam_model = V @ delta_phi          # (K,)   V is (K,d)
    importance = np.abs(w_star)        # (K,)   non-negative importance
    lam_adjusted = (1 - noise) * importance * lam_model + noise * lam_model
    return lam_adjusted


# ---------------------------------------------------------------------------
# Gradient updates (all 4 conditions)
# ---------------------------------------------------------------------------

def update_standard(theta, phi_a, phi_b, y, lr):
    """Condition 1: Standard BTL gradient in embedding space."""
    delta = phi_a - phi_b
    pred = sigmoid(theta @ delta)
    theta = theta + lr * (y - pred) * delta
    return theta


def update_projected(theta, phi_a, phi_b, y, lr, V, G_inv):
    """Condition 2: Gradient projected onto interpretable subspace.

    With non-orthogonal V, the oblique projector is P = V⊤ G⁻¹ V
    where G = V V⊤ is the Gram matrix.
    """
    delta = phi_a - phi_b
    pred = sigmoid(theta @ delta)
    grad = (y - pred) * delta
    lam = V @ grad                          # (K,)  project to dimension space
    projected_grad = V.T @ (G_inv @ lam)    # (d,)  lift back with G⁻¹ correction
    theta = theta + lr * projected_grad
    return theta


def update_slider(theta, phi_a, phi_b, y, lr, V, G_inv, lam_adjusted):
    """Condition 3: Slider-adjusted gradient.

    Sliders provide importance-weighted magnitudes (|w*| ⊙ Vδ).
    Direction comes from (y - pred), same as standard/projected.
    G⁻¹ decorrelates before lifting to embedding space.
    """
    delta = phi_a - phi_b
    pred = sigmoid(theta @ delta)
    grad_direction = V.T @ (G_inv @ lam_adjusted)   # (d,)
    theta = theta + lr * (y - pred) * grad_direction
    return theta


def update_partial(theta, phi_a, phi_b, y, lr, V, G_inv, lam_adjusted, proj_lambda):
    """Condition 4: Interpolation between standard and slider-adjusted."""
    delta = phi_a - phi_b
    pred = sigmoid(theta @ delta)
    scalar = y - pred
    standard_part = scalar * delta
    slider_part = scalar * (V.T @ (G_inv @ lam_adjusted))
    theta = theta + lr * ((1 - proj_lambda) * standard_part + proj_lambda * slider_part)
    return theta


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate(
    thetas: dict,
    test_pairs: np.ndarray,
    test_choices: np.ndarray,
    embeddings: np.ndarray,
    bt_scores: np.ndarray,
    V: np.ndarray,
    w_star: np.ndarray,
    N: int,
) -> dict:
    """Compute all evaluation metrics for each condition.

    Parameters
    ----------
    thetas      : dict condition -> theta (d,)
    test_pairs  : (M, 2) int indices into embeddings
    test_choices: (M,) int  — 1 if first option was chosen
    embeddings  : (N, d)
    bt_scores   : (N, K)
    V           : (K, d)
    w_star      : (K,)
    N           : total number of options
    """
    # True utility for all options
    true_utils = bt_scores @ w_star  # (N,)

    results = {}
    for cond, theta in thetas.items():
        # Per-option predicted utility
        pred_utils = embeddings @ theta  # (N,)

        # --- test set ---
        idx_a = test_pairs[:, 0]
        idx_b = test_pairs[:, 1]
        delta_test = embeddings[idx_a] - embeddings[idx_b]   # (M, d)
        logits = delta_test @ theta                            # (M,)
        probs = sigmoid(logits)

        # accuracy
        preds = (probs > 0.5).astype(int)
        accuracy = np.mean(preds == test_choices)

        # log-likelihood
        eps = 1e-10
        ll = np.mean(
            test_choices * np.log(probs + eps)
            + (1 - test_choices) * np.log(1 - probs + eps)
        )

        # utility correlation
        try:
            pearson_r, _ = pearsonr(pred_utils, true_utils)
        except Exception:
            pearson_r = float("nan")
        try:
            spearman_r, _ = spearmanr(pred_utils, true_utils)
        except Exception:
            spearman_r = float("nan")

        # weight recovery: correlate V⊤θ with w*
        theta_proj = V @ theta   # (K,)
        try:
            wr_pearson, _ = pearsonr(theta_proj, w_star)
        except Exception:
            wr_pearson = float("nan")
        try:
            wr_spearman, _ = spearmanr(theta_proj, w_star)
        except Exception:
            wr_spearman = float("nan")

        results[cond] = {
            "accuracy": accuracy,
            "log_likelihood": ll,
            "utility_pearson": pearson_r,
            "utility_spearman": spearman_r,
            "weight_recovery_pearson": wr_pearson,
            "weight_recovery_spearman": wr_spearman,
        }
    return results


# ---------------------------------------------------------------------------
# Main simulation
# ---------------------------------------------------------------------------

def run_simulation(args):
    rng = np.random.default_rng(args.seed)

    # --- Load data ---
    print("Loading data...")
    embeddings, bt_scores, V, G_inv, mu, option_ids, dim_names = load_data(
        args.embeddings_parquet, args.bt_scores, args.directions,
        option_id_column=args.option_id_column,
    )
    N, d = embeddings.shape
    K = V.shape[0]
    print(f"  Options: {N}, Embedding dim: {d}, Dimensions: {K}")
    print(f"  Dimensions: {dim_names}")

    # Pre-compute projections λ(aᵢ) = V⊤(φ(aᵢ) − μ) for reference (not used in training)
    # (not required by learning algorithms but stored for potential diagnostics)
    centered = embeddings - mu[np.newaxis, :]   # (N, d)
    lambdas = centered @ V.T                    # (N, K)

    # --- Generate synthetic users ---
    print("Generating synthetic users...")
    users = generate_users(args.num_users, K, dim_names, rng)
    print(f"  Generated {len(users)} users")

    # --- Build fixed test set ---
    all_indices = np.arange(N)
    test_idx_a = rng.integers(0, N, size=args.num_test_pairs)
    test_idx_b = rng.integers(0, N, size=args.num_test_pairs)
    # Avoid self-pairs
    mask = test_idx_a == test_idx_b
    while mask.any():
        test_idx_b[mask] = rng.integers(0, N, size=mask.sum())
        mask = test_idx_a == test_idx_b
    test_pairs = np.stack([test_idx_a, test_idx_b], axis=1)  # (M, 2)

    conditions = ["standard", "projected", "slider", "partial"]

    # Collect learning curve rows
    lc_rows = []

    # --- Per-user simulation ---
    print("Running simulation...")
    for user in users:
        uid = user["id"]
        w_star = user["weights"]   # (K,)
        true_utils = bt_scores @ w_star  # (N,) true utility per option

        # Pre-compute test choices for this user (fixed, deterministic evaluation)
        test_u_a = true_utils[test_pairs[:, 0]]
        test_u_b = true_utils[test_pairs[:, 1]]
        test_probs = sigmoid(args.beta * (test_u_a - test_u_b))
        # For evaluation, use expected choice (deterministic threshold)
        test_choices = (test_probs > 0.5).astype(int)

        # Initialize θ for each condition
        thetas = {c: np.zeros(d) for c in conditions}

        # Evaluate at trial 0 (before any data)
        metrics_0 = evaluate(thetas, test_pairs, test_choices, embeddings, bt_scores, V, w_star, N)
        for cond in conditions:
            row = {"user_id": uid, "condition": cond, "trial": 0}
            row.update(metrics_0[cond])
            lc_rows.append(row)

        # Training loop
        for t in range(1, args.num_trials + 1):
            # Sample a pair (all conditions see the same pair)
            idx_a, idx_b = rng.choice(N, size=2, replace=False)
            phi_a = embeddings[idx_a]
            phi_b = embeddings[idx_b]
            s_a = bt_scores[idx_a]
            s_b = bt_scores[idx_b]
            u_a = true_utils[idx_a]
            u_b = true_utils[idx_b]

            # User makes a choice
            y = user_chooses(u_a, u_b, args.beta, rng)

            # Compute slider adjustment (same for conditions 3 & 4)
            # IMPORTANT: Always use A-B frame (same as delta = phi_a - phi_b in
            # the update functions).  The sign of (y - pred) already encodes
            # the choice direction, so lam_adj must NOT be flipped.
            lam_adj = slider_adjustment(phi_a, phi_b, w_star, s_a, s_b, V, mu, args.slider_noise)

            # Update each condition
            thetas["standard"] = update_standard(thetas["standard"], phi_a, phi_b, y, args.learning_rate)
            thetas["projected"] = update_projected(thetas["projected"], phi_a, phi_b, y, args.learning_rate, V, G_inv)
            thetas["slider"] = update_slider(thetas["slider"], phi_a, phi_b, y, args.learning_rate, V, G_inv, lam_adj)
            thetas["partial"] = update_partial(
                thetas["partial"], phi_a, phi_b, y, args.learning_rate, V, G_inv, lam_adj, args.projection_lambda
            )

            # Evaluate
            metrics = evaluate(thetas, test_pairs, test_choices, embeddings, bt_scores, V, w_star, N)
            for cond in conditions:
                row = {"user_id": uid, "condition": cond, "trial": t}
                row.update(metrics[cond])
                lc_rows.append(row)

        if (uid + 1) % 10 == 0 or uid == len(users) - 1:
            print(f"  User {uid + 1}/{len(users)} done")

    # --- Save outputs ---
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. learning_curves.csv
    lc_df = pd.DataFrame(lc_rows)
    lc_df.to_csv(output_dir / "learning_curves.csv", index=False)
    print(f"Saved learning_curves.csv ({len(lc_df)} rows)")

    # 2. user_profiles.json
    user_profiles = []
    for u in users:
        profile = {
            "id": int(u["id"]),
            "archetype": u["archetype"],
            "weights": {dim_names[k]: float(u["weights"][k]) for k in range(K)},
        }
        user_profiles.append(profile)
    with open(output_dir / "user_profiles.json", "w") as f:
        json.dump(user_profiles, f, indent=2)
    print("Saved user_profiles.json")

    # 3. summary.md
    write_summary(lc_df, users, conditions, dim_names, args, output_dir)
    print("Saved summary.md")

    # 4. learning_curves.png
    try:
        plot_learning_curves(lc_df, conditions, output_dir)
        print("Saved learning_curves.png")
    except Exception as e:
        print(f"Warning: could not save plot: {e}")


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def write_summary(lc_df, users, conditions, dim_names, args, output_dir):
    n_users = len(users)
    n_archetypes = sum(1 for u in users if not u["archetype"].startswith("random"))

    lines = []
    lines.append("# Simulation Summary\n")

    lines.append("## Experimental Parameters\n")
    lines.append(f"| Parameter | Value |")
    lines.append(f"|-----------|-------|")
    lines.append(f"| Number of users | {n_users} ({n_archetypes} archetypes, {n_users - n_archetypes} random) |")
    lines.append(f"| Number of trials | {args.num_trials} |")
    lines.append(f"| Number of test pairs | {args.num_test_pairs} |")
    lines.append(f"| Number of dimensions (K) | {len(dim_names)} |")
    lines.append(f"| Dimensions | {', '.join(dim_names)} |")
    lines.append(f"| Beta (choice noise) | {args.beta} |")
    lines.append(f"| Slider noise | {args.slider_noise} |")
    lines.append(f"| Learning rate | {args.learning_rate} |")
    lines.append(f"| Projection lambda (partial) | {args.projection_lambda} |")
    lines.append(f"| Random seed | {args.seed} |")
    lines.append("")

    # Final metrics table
    final_df = lc_df[lc_df["trial"] == args.num_trials]
    lines.append("## Final Performance (at last trial)\n")
    headers = ["Condition", "Accuracy", "Log-Likelihood", "Utility Pearson", "Weight Recovery Pearson"]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for cond in conditions:
        cdf = final_df[final_df["condition"] == cond]
        acc = cdf["accuracy"].mean()
        ll = cdf["log_likelihood"].mean()
        up = cdf["utility_pearson"].mean()
        wr = cdf["weight_recovery_pearson"].mean()
        lines.append(f"| {cond} | {acc:.3f} | {ll:.4f} | {up:.3f} | {wr:.3f} |")
    lines.append("")

    # Learning curve summary table (accuracy at every 10 trials)
    lines.append("## Learning Curve (Average Accuracy by Trial)\n")
    milestone_trials = [0] + list(range(10, args.num_trials + 1, 10))
    headers2 = ["Trial"] + conditions
    lines.append("| " + " | ".join(headers2) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers2)) + " |")
    for t in milestone_trials:
        tdf = lc_df[lc_df["trial"] == t]
        row_parts = [str(t)]
        for cond in conditions:
            val = tdf[tdf["condition"] == cond]["accuracy"].mean()
            row_parts.append(f"{val:.3f}")
        lines.append("| " + " | ".join(row_parts) + " |")
    lines.append("")

    # Threshold analysis
    threshold = 0.75
    lines.append(f"## First Trial to Reach {int(threshold*100)}% Accuracy\n")
    lines.append("| Condition | First Trial ≥ 75% Accuracy |")
    lines.append("|-----------|--------------------------|")
    for cond in conditions:
        cdf = lc_df[lc_df["condition"] == cond].groupby("trial")["accuracy"].mean()
        reached = cdf[cdf >= threshold]
        if reached.empty:
            lines.append(f"| {cond} | Never reached |")
        else:
            lines.append(f"| {cond} | {reached.index[0]} |")
    lines.append("")

    lines.append("## Key Findings\n")
    final_accs = {}
    for cond in conditions:
        final_accs[cond] = final_df[final_df["condition"] == cond]["accuracy"].mean()
    best = max(final_accs, key=final_accs.get)
    lines.append(
        f"- **Best final accuracy**: {best} ({final_accs[best]:.3f})"
    )
    lines.append(
        f"- **Standard baseline accuracy**: {final_accs['standard']:.3f}"
    )
    gain = final_accs["slider"] - final_accs["standard"]
    lines.append(
        f"- **Slider vs standard gain**: {gain:+.3f}"
    )

    with open(output_dir / "summary.md", "w") as f:
        f.write("\n".join(lines) + "\n")


def plot_learning_curves(lc_df, conditions, output_dir):
    condition_colors = {
        "standard": "#e74c3c",
        "projected": "#3498db",
        "slider": "#2ecc71",
        "partial": "#9b59b6",
    }
    condition_labels = {
        "standard": "Standard (baseline)",
        "projected": "Projected",
        "slider": "Slider-adjusted",
        "partial": "Partial projection",
    }

    trials = sorted(lc_df["trial"].unique())

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    for ax_idx, (metric, ylabel) in enumerate([
        ("accuracy", "Choice Prediction Accuracy"),
        ("utility_pearson", "Utility Correlation (Pearson r)"),
    ]):
        ax = axes[ax_idx]
        for cond in conditions:
            cdf = lc_df[lc_df["condition"] == cond]
            means = []
            sems = []
            for t in trials:
                vals = cdf[cdf["trial"] == t][metric].dropna().values
                means.append(vals.mean())
                sems.append(vals.std() / np.sqrt(max(len(vals), 1)))
            means = np.array(means)
            sems = np.array(sems)
            color = condition_colors.get(cond, "gray")
            label = condition_labels.get(cond, cond)
            ax.plot(trials, means, label=label, color=color, linewidth=2)
            ax.fill_between(trials, means - sems, means + sems, alpha=0.2, color=color)

        ax.set_xlabel("Trial", fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_title(ylabel, fontsize=13, fontweight="bold")
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        if metric == "accuracy":
            ax.axhline(0.75, color="gray", linestyle="--", alpha=0.5, label="75% threshold")
        ax.set_xlim(0, max(trials))

    fig.suptitle("Preference Learning Simulation: Gradient Projection Comparison", fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(output_dir / "learning_curves.png", dpi=150, bbox_inches="tight")
    plt.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Simulated preference learning experiment comparing gradient update strategies."
    )
    parser.add_argument(
        "--embeddings-parquet",
        required=True,
        help="Path to the embeddings parquet file.",
    )
    parser.add_argument(
        "--bt-scores",
        required=True,
        help="Path to bt_scores.csv from the LLM generation pipeline.",
    )
    parser.add_argument(
        "--directions",
        required=True,
        help="Path to directions.npz from find_directions.py.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write outputs into.",
    )
    parser.add_argument("--num-users", type=int, default=50, help="Number of synthetic users.")
    parser.add_argument("--num-trials", type=int, default=100, help="Number of training trials per user.")
    parser.add_argument("--num-test-pairs", type=int, default=200, help="Number of held-out test pairs.")
    parser.add_argument("--beta", type=float, default=2.0, help="Choice noise temperature.")
    parser.add_argument("--slider-noise", type=float, default=0.2, help="Slider adjustment noise (0=perfect).")
    parser.add_argument("--learning-rate", type=float, default=0.01, help="Gradient update learning rate.")
    parser.add_argument(
        "--projection-lambda",
        type=float,
        default=0.5,
        help="Interpolation weight for partial projection (condition 4).",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument("--option-id-column", default="movie_id",
                        help="Name of the option-id column in the parquet file (default: movie_id).")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_simulation(args)
