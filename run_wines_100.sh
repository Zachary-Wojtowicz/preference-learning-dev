#!/usr/bin/env bash
set -euo pipefail

# run_wines_100.sh — Complete wines pipeline (data & embeddings already exist)
#
# Usage:
#   tmux new -s wines
#   ./run_wines_100.sh 2>&1 | tee wines_100_$(date +%Y%m%d_%H%M).log

cd "$(dirname "${BASH_SOURCE[0]}")"
log() { echo "[wines] [$(date '+%H:%M:%S')] $*"; }

log "Discovering servers..."
INSTRUCT_URL=$(python discover_servers.py --type instruct -q) || { log "FATAL: No instruct servers"; exit 1; }
EMBED_URL=$(python discover_servers.py --type embed -q) || { log "FATAL: No embed server"; exit 1; }
log "Instruct: $INSTRUCT_URL"
log "Embed:    $EMBED_URL"

EXAMPLES_CONFIG="method_llm_examples/configs/wines_100.json"
GEN_CONFIG="method_llm_gen/configs/wines_100.json"
EMB_PARQUET="datasets/wines_100/wines_100-embedded.parquet"
EXAMPLES_OUTPUT="method_llm_examples/outputs/wines_100"
GEN_OUTPUT="method_llm_gen/outputs/wines_100"
DIR_OUTPUT="method_directions/outputs/wines_100"
EXP_OUTPUT="web-interface/outputs/wines_100"

# ---------------------------------------------------------------
# Step 1: Dimension discovery
# ---------------------------------------------------------------
log "=== Step 1: Dimension discovery ==="
python method_llm_examples/pipeline.py \
    --config "$EXAMPLES_CONFIG" \
    --base-url "$INSTRUCT_URL" \
    --model Qwen/Qwen3-32B \
    --api-key dummy \
    --embeddings-parquet "$EMB_PARQUET" \
    --embedding-base-url "$EMBED_URL" \
    --embedding-model Qwen/Qwen3-Embedding-8B \
    --embedding-column embedding \
    --output-dir "$EXAMPLES_OUTPUT" \
    --dedup-method llm \
    --num-themes 40 \
    --num-pairs 100 \
    --num-dimensions 15 \
    --reasons-per-side 5 \
    --max-workers 32 \
    --seed 42

# ---------------------------------------------------------------
# Step 2: Score + BTL
# ---------------------------------------------------------------
log "=== Step 2: Score + BTL ==="
mkdir -p "$GEN_OUTPUT"
cp -n "$EXAMPLES_OUTPUT/dimensions.json" "$GEN_OUTPUT/dimensions.json" 2>/dev/null || true

python method_llm_gen/pipeline.py run-all \
    --config "$GEN_CONFIG" \
    --base-url "$INSTRUCT_URL" \
    --model Qwen/Qwen3-32B \
    --api-key dummy \
    --output-dir "$GEN_OUTPUT" \
    --seed 42

# ---------------------------------------------------------------
# Step 3: Find directions
# ---------------------------------------------------------------
log "=== Step 3: Find directions ==="
mkdir -p "$DIR_OUTPUT"
python method_directions/find_directions.py \
    --embeddings-parquet "$EMB_PARQUET" \
    --bt-scores "$GEN_OUTPUT/bt_scores.csv" \
    --embedding-column embedding \
    --option-id-column wine_id \
    --output-dir "$DIR_OUTPUT" \
    --seed 42

# ---------------------------------------------------------------
# Step 4: Evaluate
# ---------------------------------------------------------------
log "=== Step 4: Evaluate ==="
python method_directions/evaluate_basis.py --scree \
    --embeddings-parquet "$EMB_PARQUET" \
    --embedding-column embedding \
    --output-dir "$DIR_OUTPUT"

python method_directions/evaluate_basis.py \
    --embeddings-parquet "$EMB_PARQUET" \
    --directions "$DIR_OUTPUT/directions.npz" \
    --bt-scores "$GEN_OUTPUT/bt_scores.csv" \
    --embedding-column embedding \
    --output-dir "$DIR_OUTPUT"

# ---------------------------------------------------------------
# Step 5: Generate experiment trials
# ---------------------------------------------------------------
log "=== Step 5: Generate trials ==="
mkdir -p "$EXP_OUTPUT"
python web-interface/generate_trials.py \
    --config "$EXAMPLES_CONFIG" \
    --embeddings-parquet "$EMB_PARQUET" \
    --dimensions "$GEN_OUTPUT/dimensions.json" \
    --directions "$DIR_OUTPUT/directions.npz" \
    --output-dir "$EXP_OUTPUT" \
    --num-pairs 200 \
    --trials-per-participant 30 \
    --domain wines \
    --choice-context "Which wine would you rather drink tonight?" \
    --seed 42

# ---------------------------------------------------------------
# Step 6: Simulations
# ---------------------------------------------------------------
log "=== Step 6a: Weight-vector simulation ==="
python simulation/run_simulation.py \
    --embeddings-parquet "$EMB_PARQUET" \
    --bt-scores "$GEN_OUTPUT/bt_scores.csv" \
    --directions "$DIR_OUTPUT/directions.npz" \
    --output-dir simulation/outputs/wines_100 \
    --option-id-column wine_id \
    --num-users 50 --num-trials 100 --num-test-pairs 200 \
    --beta 2.0 --slider-noise 0.2 --learning-rate 0.01 \
    --projection-lambda 0.5 --seed 42

log "=== Step 6b: LLM persona simulation ==="
python simulation/run_llm_simulation.py \
    --embeddings-parquet "$EMB_PARQUET" \
    --bt-scores "$GEN_OUTPUT/bt_scores.csv" \
    --dimensions "$GEN_OUTPUT/dimensions.json" \
    --directions "$DIR_OUTPUT/directions.npz" \
    --option-descriptions "datasets/wines_100/wines_100.csv" \
    --option-template datasets/wine_prompt.txt \
    --option-id-column wine_id \
    --output-dir simulation/outputs/wines_100_llm \
    --base-url "$INSTRUCT_URL" --api-key dummy \
    --persona-model Qwen/Qwen3-32B --choice-model Qwen/Qwen3-32B \
    --num-personas 20 --num-trials 50 --num-test-pairs 50 \
    --learning-rate 0.01 --projection-lambda 0.5 \
    --max-workers 4 --seed 42 \
    --domain wines \
    --choice-context "Which wine would you rather drink tonight?"

# ---------------------------------------------------------------
# Done
# ---------------------------------------------------------------
log "=========================================="
log "Wines pipeline complete!"
log "=========================================="
log "Dimensions:  $EXAMPLES_OUTPUT/dimensions.json"
log "BT scores:   $GEN_OUTPUT/bt_scores.csv"
log "Directions:  $DIR_OUTPUT/directions.npz"
log "Evaluation:  $DIR_OUTPUT/summary.md"
log "Trials:      $EXP_OUTPUT/trials.json"
log ""
log "Check evaluation quality:"
log "  cat $DIR_OUTPUT/summary.md"
log ""
log "If some dimensions have R² < 0.1, filter them out and regenerate trials."
log "=========================================="
