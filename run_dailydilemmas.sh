#!/usr/bin/env bash
set -euo pipefail

# run_dailydilemmas.sh — Full pipeline for DailyDilemmas (paired, value-tension dilemmas).
#
# Pair structure is preserved end-to-end: pair-level diversity selection,
# predefined-pairs dimension discovery, Mode-C hybrid BT scoring, and
# pair-respecting trial generation.
#
# Usage:
#   tmux new -s dailydilemmas
#   ./run_dailydilemmas.sh 2>&1 | tee dailydilemmas_$(date +%Y%m%d_%H%M).log

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

log() { echo "[dailydilemmas] [$(date '+%H:%M:%S')] $*"; }

# ---------------------------------------------------------------
# Discover servers
# ---------------------------------------------------------------
log "Discovering servers..."
INSTRUCT_URL=$(python discover_servers.py --type instruct -q) || {
    log "FATAL: No instruct servers. Exiting."; exit 1
}
EMBED_URL=$(python discover_servers.py --type embed -q) || {
    log "FATAL: No embed server. Exiting."; exit 1
}
log "Instruct: $INSTRUCT_URL"
log "Embed:    $EMBED_URL"

# ---------------------------------------------------------------
# Step 1: Prepare data (preserve dilemma pair structure)
# ---------------------------------------------------------------
log "=== Step 1: Prepare data ==="
if [[ -f datasets/dailydilemmas-pairs.csv && -f datasets/dailydilemmas-actions.csv ]]; then
    log "Data already prepared — skipping"
else
    python datasets/prepare_dailydilemmas.py
fi

# ---------------------------------------------------------------
# Step 2: Embed individual actions (with situation + consequence in template)
# ---------------------------------------------------------------
log "=== Step 2: Embed actions ==="
if [[ -f datasets/dailydilemmas-actions-embedded.parquet ]]; then
    log "Embeddings already exist — skipping"
else
    python embed/embedder/embed_csv.py \
        --base-url "$EMBED_URL" \
        --model Qwen/Qwen3-Embedding-8B \
        --api-key dummy \
        --input-csv datasets/dailydilemmas-actions.csv \
        --template-file datasets/dailydilemmas_prompt.txt \
        --output datasets/dailydilemmas-actions-embedded.parquet
fi

# ---------------------------------------------------------------
# Step 3: Select diverse dilemmas (pair-level)
# ---------------------------------------------------------------
log "=== Step 3: Select diverse dilemmas ==="
DATASET_DIR="datasets/dailydilemmas"
if [[ -f "$DATASET_DIR/selected_pairs.csv" ]]; then
    log "Dilemmas already selected — skipping"
else
    python datasets/select_dilemmas.py \
        --pairs-csv datasets/dailydilemmas-pairs.csv \
        --actions-parquet datasets/dailydilemmas-actions-embedded.parquet \
        --id-column action_id \
        --num-dilemmas 150 \
        --output-dir "$DATASET_DIR" \
        --seed 42
fi

# ---------------------------------------------------------------
# Step 4: Generate configs
# ---------------------------------------------------------------
log "=== Step 4: Generate configs ==="

EXAMPLES_CONFIG="method_llm_examples/configs/dailydilemmas.json"
if [[ ! -f "$EXAMPLES_CONFIG" ]]; then
    mkdir -p "$(dirname "$EXAMPLES_CONFIG")"
    cat > "$EXAMPLES_CONFIG" <<'EOF'
{
  "domain": "everyday moral dilemmas",
  "domain_item": "action",
  "choice_context": "Which action is more ethical or understandable?",
  "input_path": "datasets/dailydilemmas/selected_actions.csv",
  "template_path": "datasets/dailydilemmas_prompt.txt",
  "text_column": "text",
  "display_column": "description",
  "id_column": "action_id",
  "max_options": 300
}
EOF
    log "Wrote $EXAMPLES_CONFIG"
fi

GEN_CONFIG="method_llm_gen/configs/dailydilemmas.json"
if [[ ! -f "$GEN_CONFIG" ]]; then
    mkdir -p "$(dirname "$GEN_CONFIG")"
    cat > "$GEN_CONFIG" <<'EOF'
{
  "domain": "dailydilemmas",
  "choice_context": "Which action is more ethical or understandable?",
  "input_path": "datasets/dailydilemmas/selected_actions.csv",
  "template_path": "datasets/dailydilemmas_prompt.txt",
  "text_column": "text",
  "display_column": "description",
  "id_column": "action_id",
  "num_dimensions": 20,
  "pair_appearances_per_option": 30,
  "max_options": 300,
  "dimensions_output_format": "plain",
  "request_timeout_seconds": 180,
  "max_retries": 3,
  "max_workers": 32
}
EOF
    log "Wrote $GEN_CONFIG"
fi

# ---------------------------------------------------------------
# Step 5: Dimension discovery (using original dilemma pairs)
# ---------------------------------------------------------------
log "=== Step 5: Dimension discovery ==="
EXAMPLES_OUTPUT="method_llm_examples/outputs/dailydilemmas"
python method_llm_examples/pipeline.py \
    --config "$EXAMPLES_CONFIG" \
    --predefined-pairs "$DATASET_DIR/predefined_pairs.json" \
    --base-url "$INSTRUCT_URL" \
    --model Qwen/Qwen3-32B \
    --api-key dummy \
    --embeddings-parquet "$DATASET_DIR/selected_actions-embedded.parquet" \
    --embedding-base-url "$EMBED_URL" \
    --embedding-model Qwen/Qwen3-Embedding-8B \
    --embedding-column embedding \
    --output-dir "$EXAMPLES_OUTPUT" \
    --dedup-method llm \
    --num-themes 50 \
    --num-dimensions 20 \
    --reasons-per-side 5 \
    --max-workers 32 \
    --seed 42

# ---------------------------------------------------------------
# Step 6: Score options + fit BTL model (Mode C: hybrid sampling)
# ---------------------------------------------------------------
log "=== Step 6: Score + BTL (Mode C) ==="
GEN_OUTPUT="method_llm_gen/outputs/dailydilemmas"
mkdir -p "$GEN_OUTPUT"
cp -n "$EXAMPLES_OUTPUT/dimensions.json" "$GEN_OUTPUT/dimensions.json" 2>/dev/null || true

python method_llm_gen/pipeline.py run-all \
    --config "$GEN_CONFIG" \
    --predefined-pairs "$DATASET_DIR/predefined_pairs.json" \
    --base-url "$INSTRUCT_URL" \
    --model Qwen/Qwen3-32B \
    --api-key dummy \
    --output-dir "$GEN_OUTPUT" \
    --seed 42

# ---------------------------------------------------------------
# Step 7: Find direction vectors
# ---------------------------------------------------------------
log "=== Step 7: Find directions ==="
DIRECTIONS_OUTPUT="method_directions/outputs/dailydilemmas"
mkdir -p "$DIRECTIONS_OUTPUT"
python method_directions/find_directions.py \
    --embeddings-parquet "$DATASET_DIR/selected_actions-embedded.parquet" \
    --bt-scores "$GEN_OUTPUT/bt_scores.csv" \
    --embedding-column embedding \
    --option-id-column action_id \
    --output-dir "$DIRECTIONS_OUTPUT" \
    --seed 42

# ---------------------------------------------------------------
# Step 8: Evaluate basis
# ---------------------------------------------------------------
log "=== Step 8: Evaluate ==="
python method_directions/evaluate_basis.py --scree \
    --embeddings-parquet "$DATASET_DIR/selected_actions-embedded.parquet" \
    --embedding-column embedding \
    --output-dir "$DIRECTIONS_OUTPUT"

python method_directions/evaluate_basis.py \
    --embeddings-parquet "$DATASET_DIR/selected_actions-embedded.parquet" \
    --directions "$DIRECTIONS_OUTPUT/directions.npz" \
    --bt-scores "$GEN_OUTPUT/bt_scores.csv" \
    --embedding-column embedding \
    --output-dir "$DIRECTIONS_OUTPUT"

# ---------------------------------------------------------------
# Step 9: Generate experiment trials (using original dilemma pairs)
# ---------------------------------------------------------------
log "=== Step 9: Generate trials ==="
EXPERIMENT_OUTPUT="web-interface/outputs/dailydilemmas"
mkdir -p "$EXPERIMENT_OUTPUT"
python web-interface/generate_trials.py \
    --config "$EXAMPLES_CONFIG" \
    --embeddings-parquet "$DATASET_DIR/selected_actions-embedded.parquet" \
    --dimensions "$GEN_OUTPUT/dimensions.json" \
    --directions "$DIRECTIONS_OUTPUT/directions.npz" \
    --output-dir "$EXPERIMENT_OUTPUT" \
    --pairs-csv "$DATASET_DIR/selected_pairs.csv" \
    --pair-a-column action_0_id \
    --pair-b-column action_1_id \
    --trials-per-participant 30 \
    --seed 42

# ---------------------------------------------------------------
# Step 10: Simulations
# ---------------------------------------------------------------
log "=== Step 10a: Weight-vector simulation ==="
python simulation/run_simulation.py \
    --embeddings-parquet "$DATASET_DIR/selected_actions-embedded.parquet" \
    --bt-scores "$GEN_OUTPUT/bt_scores.csv" \
    --directions "$DIRECTIONS_OUTPUT/directions.npz" \
    --output-dir simulation/outputs/dailydilemmas \
    --option-id-column action_id \
    --num-users 50 --num-trials 100 --num-test-pairs 200 \
    --beta 2.0 --slider-noise 0.2 --learning-rate 0.01 \
    --projection-lambda 0.5 --seed 42

log "=== Step 10b: LLM persona simulation ==="
python simulation/run_llm_simulation.py \
    --embeddings-parquet "$DATASET_DIR/selected_actions-embedded.parquet" \
    --bt-scores "$GEN_OUTPUT/bt_scores.csv" \
    --dimensions "$GEN_OUTPUT/dimensions.json" \
    --directions "$DIRECTIONS_OUTPUT/directions.npz" \
    --option-descriptions "$DATASET_DIR/selected_actions.csv" \
    --option-template datasets/dailydilemmas_prompt.txt \
    --option-id-column action_id \
    --output-dir simulation/outputs/dailydilemmas_llm \
    --base-url "$INSTRUCT_URL" --api-key dummy \
    --persona-model Qwen/Qwen3-32B --choice-model Qwen/Qwen3-32B \
    --num-personas 20 --num-trials 50 --num-test-pairs 50 \
    --learning-rate 0.01 --projection-lambda 0.5 \
    --max-workers 4 --seed 42 \
    --domain "everyday moral dilemmas" \
    --choice-context "Which action is more ethical or understandable?"

# ---------------------------------------------------------------
# Done
# ---------------------------------------------------------------
log "=========================================="
log "DailyDilemmas pipeline complete!"
log "=========================================="
log "Dimensions:  $EXAMPLES_OUTPUT/dimensions.json"
log "BT scores:   $GEN_OUTPUT/bt_scores.csv"
log "Directions:  $DIRECTIONS_OUTPUT/directions.npz"
log "Evaluation:  $DIRECTIONS_OUTPUT/"
log "Trials:      $EXPERIMENT_OUTPUT/trials.json"
log "Sim (wvec):  simulation/outputs/dailydilemmas/summary.md"
log "Sim (llm):   simulation/outputs/dailydilemmas_llm/summary.md"
log ""
log "To serve the experiment:"
log "  cp $EXPERIMENT_OUTPUT/trials.json web-interface/trials.json"
log "  cp $EXPERIMENT_OUTPUT/experiment_config.json web-interface/experiment_config.json"
log "  cd web-interface/ && python3 -m http.server 8080"
log "  Open: http://localhost:8080?domain=dailydilemmas"
log "=========================================="
