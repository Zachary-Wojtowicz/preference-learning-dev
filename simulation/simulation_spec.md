# Task: Simulated Preference Learning Experiment

## Goal

Build a Python simulation that tests the core hypothesis from the paper: **does projecting RLHF gradients onto an interpretable preference subspace speed up learning and reduce misgeneralization, compared to standard (unprojected) gradient updates?**

The simulation replaces human subjects with synthetic users who have known ground-truth preferences over the LLM-generated dimensions. This lets us measure convergence speed and generalization precisely, since we know the true utility function.

## Prerequisites

This script depends on outputs from two earlier pipeline stages:

1. **BTL scores** (`method_llm_gen_fork/outputs/<run>/bt_scores.csv`): Each option's score on each of K LLM-generated dimensions.
2. **Direction vectors** (`method_directions/outputs/<run>/directions.npz`): The K direction vectors in embedding space (from `find_directions.py`), plus the mean embedding.
3. **Embeddings** (the original parquet): Raw embeddings for all options.

## Conceptual Setup

### Option representation

Each option (e.g., movie/wine) aᵢ has:
- An embedding φ(aᵢ) ∈ ℝᵈ (from the parquet)
- A feature vector s(aᵢ) ∈ ℝᴷ of BTL scores across the K interpretable dimensions
- A projection λ(aᵢ) = V⊤(φ(aᵢ) − μ) ∈ ℝᴷ where V is the orthonormal direction matrix and μ is the mean embedding

### Synthetic user profiles

Each synthetic user is defined by a ground-truth weight vector w* ∈ ℝᴷ over the K interpretable dimensions. The user's true utility for option a is:

    u*(a) = w*⊤ s(a)

where s(a) is the BTL score vector. Generate a population of synthetic users by sampling w* from a distribution — e.g., each component from Uniform(-1, 1), or from a few hand-designed "persona" archetypes (e.g., "action lover" has high weight on intensity, low on romance). Include both random and archetypal users.

### Choice model

Given a binary choice between options a and a', the synthetic user chooses a with probability:

    P(a ≻ a') = σ(β · (u*(a) − u*(a')))

where σ is the logistic sigmoid and β is a temperature parameter controlling choice noise (β=1 for moderate noise, β→∞ for deterministic). Add β as a configurable parameter.

### Slider adjustment model

After the user makes a choice, the system shows K slider values — these are the model's current decomposition of the choice along the K dimensions. The synthetic user "adjusts" these sliders toward their true preferences. Specifically:

- The model's inferred decomposition for the choice (a chosen over a') is: λ_model = V⊤(φ(a) − φ(a'))
- The user's "true" decomposition is: λ_true = w* ⊙ (s(a) − s(a')), where ⊙ is element-wise multiplication — i.e., each dimension's contribution is the score difference weighted by how much the user cares about that dimension.
- The adjusted slider values are: λ_adjusted = (1 − noise) · λ_true + noise · λ_model, where noise ∈ [0, 1] controls how imperfectly the user adjusts (noise=0 means perfect adjustment, noise=1 means no adjustment). Make this a configurable parameter.

## Learning Algorithms to Compare

Implement three conditions that learn a preference vector θ ∈ ℝᵈ from a sequence of choices:

### Condition 1: Standard gradient (baseline)

Standard BTL gradient update in embedding space:

    θ ← θ + η · (y − σ(θ⊤δ)) · δ

where δ = φ(a) − φ(a') and y = 1 if a was chosen.

### Condition 2: Fully projected gradient

Project the gradient onto the interpretable subspace V:

    θ ← θ + η · (y − σ(θ⊤δ)) · (VV⊤)δ

This discards all gradient components outside the K-dimensional interpretable subspace.

### Condition 3: Slider-adjusted gradient (the proposed method)

Use the human-adjusted slider values to construct the gradient:

    θ ← θ + η · (y − σ(θ⊤δ)) · V λ_adjusted

where λ_adjusted comes from the slider adjustment model above. This replaces the raw embedding-space gradient with one that lives in the interpretable subspace AND reflects the user's stated reasons for their choice.

### Condition 4 (optional): Partial projection

The λ-interpolation from the paper:

    θ ← θ + η · ((1−λ) · (y − σ(θ⊤δ)) · δ + λ · (y − σ(θ⊤δ)) · V λ_adjusted)

where λ ∈ [0, 1] controls the projection strength.

## Simulation Loop

For each synthetic user:

1. Initialize θ = 0 (or small random).
2. For trial t = 1, ..., T:
   a. **Sample a pair**: randomly draw two options from the pool (or use an active-learning strategy — start with random).
   b. **User chooses**: simulate the choice using the BTL model above.
   c. **Compute slider values**: compute the model's decomposition and the user's adjustment.
   d. **Update θ**: apply the gradient update for each condition (run all conditions in parallel on the same choice sequence so they see the same data).
   e. **Evaluate**: compute the current model's predictive accuracy on a held-out test set of option pairs.

### Evaluation metrics (computed every trial or every N trials)

- **Choice prediction accuracy**: On a fixed test set of ~200 random pairs not used for training, compute the fraction where the model correctly predicts the user's choice (i.e., σ(θ⊤δ) > 0.5 when the user would choose a).
- **Choice prediction log-likelihood**: Average log-likelihood on the test set.
- **Utility correlation**: Pearson/Spearman correlation between the model's predicted utility θ⊤φ(aᵢ) and the user's true utility w*⊤s(aᵢ) across all options.
- **Weight recovery** (interpretable subspace only): Correlation between the model's projection onto V (i.e., V⊤θ) and the user's true weights w*.

## Outputs

Write to `simulation/outputs/<run_name>/`:

1. **`learning_curves.csv`**: One row per (user_id, condition, trial_number) with columns for all evaluation metrics. This is the primary data for plotting convergence curves.

2. **`user_profiles.json`**: The generated synthetic user weight vectors and their archetypes.

3. **`summary.md`**: A markdown report with:
   - Experimental parameters (number of users, trials, dimensions, noise levels, etc.).
   - A table showing average metrics at trial T (final) for each condition.
   - Learning curve summaries: average across users of choice prediction accuracy vs. trial number, for each condition.
   - Key finding: at what trial does each condition first reach 75% accuracy? (or whatever threshold is reasonable).

4. **`learning_curves.png`** (optional but very helpful): Plot average choice prediction accuracy (y-axis) vs. trial number (x-axis), one line per condition, with shaded standard error bands across users.

## CLI Interface

```
python simulation/run_simulation.py \
  --embeddings-parquet datasets/movielens-32m-enriched-50-embedded.parquet \
  --bt-scores method_llm_gen/outputs/<run>/bt_scores.csv \
  --directions method_directions/outputs/<run>/directions.npz \
  --output-dir simulation/outputs/<run_name> \
  --num-users 50 \
  --num-trials 100 \
  --num-test-pairs 200 \
  --beta 2.0 \
  --slider-noise 0.2 \
  --learning-rate 0.01 \
  --projection-lambda 0.5 \
  --seed 42
```

## Dependencies

`numpy`, `pandas`, `scikit-learn`, `scipy`, `pyarrow`, `matplotlib` (for optional plot). No deep learning libraries.

## Key Design Notes

- All conditions see the **same sequence of option pairs and choices** per user. The only difference is how they process the gradient. This is critical for a fair comparison.
- Use the **BTL scores** s(a) (not the projected embeddings λ(a)) as the ground truth for synthetic user utility. The BTL scores are the "true" feature values; the projected embeddings are the model's approximation. The gap between them is exactly what the R² diagnostic from `find_directions.py` measures.
- Start simple: random pair sampling, fixed learning rate, no momentum. These can be added later.
- The simulation should be fast enough to run in a few minutes for 50 users × 100 trials × 3 conditions. All the heavy computation (embeddings, directions) is pre-loaded; the inner loop is just dot products and sigmoid evaluations.
