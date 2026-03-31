# Task: Find Preference Direction Vectors in Embedding Space

## Context

You have two data sources that need to be joined:

1. **Embeddings**: A parquet file (e.g., `datasets/wine-130k_embedded.parquet` or the movie equivalent) containing one row per choice option with an `embedding` column (a list of floats, ~3584-dimensional) and an identifier column (e.g., `row_id` or `title`).

2. **BTL scores**: A CSV file (e.g., `method_llm_gen/outputs/<run>/bt_scores.csv`) containing columns `dimension_id`, `dimension_name`, `option_id`, `display_text`, and `bt_score`. Each row gives one option's score on one dimension. Scores are continuous, normalized to [-1, 1].

The goal is to find, for each LLM-generated dimension k, a direction vector vₖ ∈ ℝᵈ in embedding space such that the dot product ⟨vₖ, φ(aᵢ)⟩ approximates the BTL score sₖ(aᵢ). These direction vectors will later be used as the columns of a projection matrix V.

## What to Build

Write a single Python script `find_directions.py` (place it in `method_directions/`) that does the following:

### Step 0 — Load and join data

Read the embeddings parquet and the BTL scores CSV. Join them on option ID so you have, for each option, both its embedding vector and its scores on all K dimensions. Drop any options that appear in one file but not the other. Report how many options and dimensions you're working with.

### Step 1 — Ridge regression (primary method)

For each dimension k:

- Let X be the N × d matrix of embeddings (centered: subtract the mean embedding) and y be the N-vector of BTL scores for dimension k.
- Fit a ridge regression: vₖ = argmin ‖Xvₖ − y‖² + α‖vₖ‖². Use sklearn's `RidgeCV` with a range of alphas (e.g., `[0.01, 0.1, 1, 10, 100, 1000]`) and leave-one-out cross-validation to select alpha automatically.
- Record the best alpha, the in-sample R², and the cross-validated R² (from RidgeCV's built-in scoring).
- Store the resulting coefficient vector vₖ ∈ ℝᵈ.

### Step 2 — Contrastive mean difference (sanity check)

For each dimension k:

- Sort options by their BTL score on dimension k.
- Take the top M options and bottom M options (use M = max(5, N // 10), but make M a CLI argument with default).
- Compute vₖ_contrast = mean(embeddings of top-M) − mean(embeddings of bottom-M).
- Normalize to unit length.
- Also normalize the ridge vector to unit length for comparison.
- Compute cosine similarity between the ridge direction and the contrastive direction.

### Step 3 — Held-out evaluation

For each dimension k:

- Run a proper train/test split: randomly hold out 20% of options.
- Fit ridge on the 80% training set.
- On the 20% test set, compute predicted scores as ŷᵢ = vₖ⊤ φ(aᵢ) and report: Pearson correlation between ŷ and true BTL scores, Spearman rank correlation, and R².
- Average these across dimensions to get an overall summary.

### Step 4 — Orthogonalize

After fitting all K ridge directions:

- Stack them into a K × d matrix.
- Run QR decomposition to produce an orthonormal basis V (K × d).
- Report how much the orthogonalization changed each direction (cosine similarity between pre- and post-orthogonalization vectors). Large changes indicate the original dimensions were redundant in embedding space.

## Outputs

Write the following to an output directory (default `method_directions/outputs/<run_name>/`):

1. **`directions.npz`**: The raw ridge direction vectors (K × d), the orthogonalized direction vectors (K × d), the mean embedding (1 × d), and the best ridge alphas (K,).

2. **`evaluation.csv`**: One row per dimension with columns: `dimension_id`, `dimension_name`, `ridge_alpha`, `r2_insample`, `r2_cv`, `r2_heldout`, `pearson_heldout`, `spearman_heldout`, `cosine_ridge_vs_contrastive`, `cosine_pre_vs_post_orthogonalization`.

3. **`summary.md`**: A human-readable markdown report that shows:
   - Overall statistics (number of options, dimensions, embedding dimensionality).
   - A table of per-dimension evaluation metrics from evaluation.csv.
   - Average held-out R² across dimensions (this is the key diagnostic: is the linear assumption justified?).
   - For each dimension, the top 3 and bottom 3 options by *predicted* score (from the ridge direction), alongside their *actual* BTL score, so you can eyeball whether the direction makes sense.
   - Flag any dimensions where the cosine similarity between ridge and contrastive directions is below 0.5, or where held-out R² is below 0.1 — these are unreliable.

## CLI Interface

```
python method_directions/find_directions.py \
  --embeddings-parquet datasets/wine-130k_embedded.parquet \
  --bt-scores method_llm_gen/outputs/<run>/bt_scores.csv \
  --embedding-column embedding \
  --option-id-column option_id \
  --output-dir method_directions/outputs/<run_name> \
  --contrastive-m 10 \
  --test-fraction 0.2 \
  --seed 42
```

## Dependencies

Only standard scientific Python: `numpy`, `pandas`, `scikit-learn`, `scipy`, `pyarrow`. No deep learning libraries needed for this step.
