#!/usr/bin/env bash
set -euo pipefail

# run_coalign_50.sh — Full pipeline for the curated 50-set subset of the
# Community Alignment Dataset (Meta). English-only, in_balanced_subset_10.
#
# Each "set" = a prompt with 4 candidate LLM responses (letters A/B/C/D).
# All 6 within-set pairs are emitted as predefined pairs (Mode C); cross-set
# random pairs are added by BT only for global identifiability.
#
# Usage:
#   tmux new -s coalign50
#   ./run_coalign_50.sh 2>&1 | tee coalign50_$(date +%Y%m%d_%H%M).log

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

log() { echo "[coalign50] [$(date '+%H:%M:%S')] $*"; }

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
# Step 1: Prepare data (English balanced subset, 4 options per set, 6 pairs per set)
# ---------------------------------------------------------------
log "=== Step 1: Prepare data ==="
if [[ -f datasets/coalign-options.csv && -f datasets/coalign-pairs.csv ]]; then
    log "Data already prepared — skipping"
else
    python datasets/prepare_coalign.py
fi

# ---------------------------------------------------------------
# Step 2: Embed individual options (Prompt + Response)
# ---------------------------------------------------------------
log "=== Step 2: Embed options ==="
if [[ -f datasets/coalign-options-embedded.parquet ]]; then
    log "Embeddings already exist — skipping"
else
    python embed/embedder/embed_csv.py \
        --base-url "$EMBED_URL" \
        --model Qwen/Qwen3-Embedding-8B \
        --api-key dummy \
        --input-csv datasets/coalign-options.csv \
        --template-file datasets/coalign_prompt.txt \
        --output datasets/coalign-options-embedded.parquet
fi

# ---------------------------------------------------------------
# Step 3: Select 50 diverse choice sets (set-level farthest-first)
# ---------------------------------------------------------------
log "=== Step 3: Select diverse choice sets ==="
DATASET_DIR="datasets/coalign_50"
if [[ -f "$DATASET_DIR/selected_pairs.csv" ]]; then
    log "Sets already selected — skipping"
else
    python datasets/select_coalign.py \
        --pairs-csv datasets/coalign-pairs.csv \
        --options-parquet datasets/coalign-options-embedded.parquet \
        --id-column action_id \
        --num-sets 50 \
        --output-dir "$DATASET_DIR" \
        --seed 42
fi

# ---------------------------------------------------------------
# Step 4: Generate configs
# ---------------------------------------------------------------
log "=== Step 4: Generate configs ==="

EXAMPLES_CONFIG="method_llm_examples/configs/coalign_50.json"
if [[ ! -f "$EXAMPLES_CONFIG" ]]; then
    mkdir -p "$(dirname "$EXAMPLES_CONFIG")"
    cat > "$EXAMPLES_CONFIG" <<'EOF'
{
  "domain": "LLM responses to user prompts",
  "domain_item": "response",
  "choice_context": "Which response is better?",
  "input_path": "datasets/coalign_50/selected_options.csv",
  "template_path": "datasets/coalign_prompt.txt",
  "text_column": "text",
  "display_column": "description",
  "id_column": "action_id",
  "max_options": 300
}
EOF
    log "Wrote $EXAMPLES_CONFIG"
fi

GEN_CONFIG="method_llm_gen/configs/coalign_50.json"
if [[ ! -f "$GEN_CONFIG" ]]; then
    mkdir -p "$(dirname "$GEN_CONFIG")"
    cat > "$GEN_CONFIG" <<'EOF'
{
  "domain": "coalign_50",
  "choice_context": "Which response is better?",
  "input_path": "datasets/coalign_50/selected_options.csv",
  "template_path": "datasets/coalign_prompt.txt",
  "text_column": "text",
  "display_column": "description",
  "id_column": "action_id",
  "num_dimensions": 15,
  "pair_appearances_per_option": 20,
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
# Step 5: Dimension discovery (using within-set pairs)
# ---------------------------------------------------------------
log "=== Step 5: Dimension discovery ==="
EXAMPLES_OUTPUT="method_llm_examples/outputs/coalign_50"
python method_llm_examples/pipeline.py \
    --config "$EXAMPLES_CONFIG" \
    --predefined-pairs "$DATASET_DIR/predefined_pairs.json" \
    --base-url "$INSTRUCT_URL" \
    --model Qwen/Qwen3-32B \
    --api-key dummy \
    --embeddings-parquet "$DATASET_DIR/selected_options-embedded.parquet" \
    --embedding-base-url "$EMBED_URL" \
    --embedding-model Qwen/Qwen3-Embedding-8B \
    --embedding-column embedding \
    --output-dir "$EXAMPLES_OUTPUT" \
    --dedup-method llm \
    --num-themes 40 \
    --num-dimensions 15 \
    --reasons-per-side 5 \
    --max-workers 32 \
    --seed 42

# ---------------------------------------------------------------
# Step 6: Score options + fit BTL model (Mode C: hybrid sampling)
# ---------------------------------------------------------------
log "=== Step 6: Score + BTL (Mode C) ==="
GEN_OUTPUT="method_llm_gen/outputs/coalign_50"
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
DIRECTIONS_OUTPUT="method_directions/outputs/coalign_50"
mkdir -p "$DIRECTIONS_OUTPUT"
python method_directions/find_directions.py \
    --embeddings-parquet "$DATASET_DIR/selected_options-embedded.parquet" \
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
    --embeddings-parquet "$DATASET_DIR/selected_options-embedded.parquet" \
    --embedding-column embedding \
    --output-dir "$DIRECTIONS_OUTPUT"

python method_directions/evaluate_basis.py \
    --embeddings-parquet "$DATASET_DIR/selected_options-embedded.parquet" \
    --directions "$DIRECTIONS_OUTPUT/directions.npz" \
    --bt-scores "$GEN_OUTPUT/bt_scores.csv" \
    --embedding-column embedding \
    --output-dir "$DIRECTIONS_OUTPUT"

# ---------------------------------------------------------------
# Step 9: Generate experiment trials (within-set pairs only)
# ---------------------------------------------------------------
log "=== Step 9: Generate trials ==="
EXPERIMENT_OUTPUT="web-interface/outputs/coalign_50"
mkdir -p "$EXPERIMENT_OUTPUT"
python web-interface/generate_trials.py \
    --config "$EXAMPLES_CONFIG" \
    --embeddings-parquet "$DATASET_DIR/selected_options-embedded.parquet" \
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
    --embeddings-parquet "$DATASET_DIR/selected_options-embedded.parquet" \
    --bt-scores "$GEN_OUTPUT/bt_scores.csv" \
    --directions "$DIRECTIONS_OUTPUT/directions.npz" \
    --output-dir simulation/outputs/coalign_50 \
    --option-id-column action_id \
    --num-users 50 --num-trials 20 --num-test-pairs 200 \
    --beta 2.0 --participant-noise 0.10 --seed 42

log "=== Step 10b: LLM persona simulation ==="
python simulation/run_llm_simulation.py \
    --embeddings-parquet "$DATASET_DIR/selected_options-embedded.parquet" \
    --bt-scores "$GEN_OUTPUT/bt_scores.csv" \
    --dimensions "$GEN_OUTPUT/dimensions.json" \
    --directions "$DIRECTIONS_OUTPUT/directions.npz" \
    --option-descriptions "$DATASET_DIR/selected_options.csv" \
    --option-template datasets/coalign_prompt.txt \
    --option-id-column action_id \
    --output-dir simulation/outputs/coalign_50_llm \
    --base-url "$INSTRUCT_URL" --api-key dummy \
    --persona-model Qwen/Qwen3-32B --choice-model Qwen/Qwen3-32B \
    --num-personas 20 --num-trials 20 --num-test-pairs 50 \
    --max-workers 4 --seed 42 \
    --domain "LLM responses to user prompts" \
    --choice-context "Which response is better?"

# ---------------------------------------------------------------
# Done
# ---------------------------------------------------------------
log "=========================================="
log "CoAlign 50 pipeline complete!"
log "=========================================="
log "Dimensions:  $EXAMPLES_OUTPUT/dimensions.json"
log "BT scores:   $GEN_OUTPUT/bt_scores.csv"
log "Directions:  $DIRECTIONS_OUTPUT/directions.npz"
log "Evaluation:  $DIRECTIONS_OUTPUT/"
log "Trials:      $EXPERIMENT_OUTPUT/trials.json"
log "Sim (wvec):  simulation/outputs/coalign_50/summary.md"
log "Sim (llm):   simulation/outputs/coalign_50_llm/summary.md"
log ""
log "To serve the experiment locally:"
log "  cd web-interface/ && python3 -m http.server 8080"
log "  Open: http://localhost:8080?domain=coalign_50&pid=test1&condition=inference_categories"
log "=========================================="
