#!/usr/bin/env bash
set -euo pipefail

# run_pipeline.sh — Run the full preference-learning pipeline on any dataset.
#
# Usage:
#   ./run_pipeline.sh configs/movies_100.yaml
#   ./run_pipeline.sh configs/scruples_200.yaml
#
# The config file specifies all dataset-specific parameters.
# Server discovery is automatic via discover_servers.py.
#
# Each step checks for existing output and skips if found.
# To re-run a step, delete its output files first.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ---------------------------------------------------------------
# Parse config (YAML-like key: value, one per line)
# ---------------------------------------------------------------
CONFIG_FILE="${1:?Usage: $0 <config.yaml>}"

if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "ERROR: Config file not found: $CONFIG_FILE"
    exit 1
fi

get_config() {
    local key="$1"
    local default="${2:-}"
    local val
    val=$(grep "^${key}:" "$CONFIG_FILE" | head -1 | sed "s/^${key}:[[:space:]]*//" | sed 's/[[:space:]]*$//')
    if [[ -z "$val" ]]; then
        echo "$default"
    else
        echo "$val"
    fi
}

# Required fields
DATASET_NAME=$(get_config "name")
INPUT_CSV=$(get_config "input_csv")
ID_COLUMN=$(get_config "id_column")
TEMPLATE_FILE=$(get_config "template_file")
DOMAIN=$(get_config "domain")
DOMAIN_ITEM=$(get_config "domain_item")
CHOICE_CONTEXT=$(get_config "choice_context")
TEXT_COLUMN=$(get_config "text_column" "text")
DISPLAY_COLUMN=$(get_config "display_column" "title")

# Optional fields with defaults
NUM_OPTIONS=$(get_config "num_options" "100")
NUM_DIMENSIONS=$(get_config "num_dimensions" "25")
NUM_PAIRS=$(get_config "num_pairs" "100")
NUM_THEMES=$(get_config "num_themes" "50")
REASONS_PER_SIDE=$(get_config "reasons_per_side" "5")
PAIR_APPEARANCES=$(get_config "pair_appearances_per_option" "30")
MAX_WORKERS=$(get_config "max_workers" "32")
SEED=$(get_config "seed" "42")
EMBEDDING_MODEL=$(get_config "embedding_model" "Qwen/Qwen3-Embedding-8B")
INSTRUCT_MODEL=$(get_config "instruct_model" "Qwen/Qwen3-32B")

# Filtering (optional)
FILTER_EXPR=$(get_config "filter" "")
AUX_CSV=$(get_config "aux_csv" "")
AUX_JOIN_COLUMN=$(get_config "aux_join_column" "")

# Derived paths — all predictable
DATASET_DIR="datasets/${DATASET_NAME}"
INPUT_STEM=$(basename "${INPUT_CSV}" .csv)
EMBEDDED_FULL="datasets/${INPUT_STEM}-embedded.parquet"
SELECTED_CSV="${DATASET_DIR}/${DATASET_NAME}.csv"
EMBEDDED_SELECTED="${DATASET_DIR}/${DATASET_NAME}-embedded.parquet"
EXAMPLES_CONFIG="method_llm_examples/configs/${DATASET_NAME}.json"
GEN_CONFIG="method_llm_gen/configs/${DATASET_NAME}.json"
EXAMPLES_OUTPUT="method_llm_examples/outputs/${DATASET_NAME}"
GEN_OUTPUT="method_llm_gen/outputs/${DATASET_NAME}"
DIRECTIONS_OUTPUT="method_directions/outputs/${DATASET_NAME}"

echo "============================================"
echo "Pipeline: ${DATASET_NAME}"
echo "============================================"
echo "Input CSV:       ${INPUT_CSV}"
echo "ID column:       ${ID_COLUMN}"
echo "Num options:     ${NUM_OPTIONS}"
echo "Num dimensions:  ${NUM_DIMENSIONS}"
echo "Embed model:     ${EMBEDDING_MODEL}"
echo "Instruct model:  ${INSTRUCT_MODEL}"
echo "============================================"
echo ""

# ---------------------------------------------------------------
# Discover servers
# ---------------------------------------------------------------
echo "[servers] Discovering vLLM servers..."
INSTRUCT_URL=$(python discover_servers.py --type instruct -q) || {
    echo "ERROR: No instruct servers found. Run './serve.sh up' first."
    exit 1
}
EMBED_URL=$(python discover_servers.py --type embed -q) || {
    echo "ERROR: No embed servers found. Run './serve.sh up' first."
    exit 1
}
echo "[servers] Instruct: ${INSTRUCT_URL}"
echo "[servers] Embed:    ${EMBED_URL}"
echo ""

# ---------------------------------------------------------------
# Step 1: Embed full dataset
# ---------------------------------------------------------------
if [[ -f "$EMBEDDED_FULL" ]]; then
    echo "[step-1] Embeddings already exist: ${EMBEDDED_FULL} — skipping"
else
    echo "[step-1] Embedding full dataset: ${INPUT_CSV}..."
    python embed/embedder/embed_csv.py \
        --base-url "${EMBED_URL}" \
        --model "${EMBEDDING_MODEL}" \
        --api-key dummy \
        --input-csv "${INPUT_CSV}" \
        --template-file "${TEMPLATE_FILE}" \
        --output "${EMBEDDED_FULL}"
fi
echo ""

# ---------------------------------------------------------------
# Step 2: Select diverse options
# ---------------------------------------------------------------
if [[ -f "$EMBEDDED_SELECTED" ]]; then
    echo "[step-2] Selected options already exist: ${EMBEDDED_SELECTED} — skipping"
else
    echo "[step-2] Selecting ${NUM_OPTIONS} diverse options..."
    mkdir -p "${DATASET_DIR}"

    SELECT_ARGS=(
        --input "${EMBEDDED_FULL}"
        --id-column "${ID_COLUMN}"
        --num-options "${NUM_OPTIONS}"
        --output-csv "${SELECTED_CSV}"
        --output-parquet "${EMBEDDED_SELECTED}"
        --output-dir "${DATASET_DIR}"
        --seed "${SEED}"
    )

    if [[ -n "$FILTER_EXPR" ]]; then
        SELECT_ARGS+=(--filter "${FILTER_EXPR}")
    fi
    if [[ -n "$AUX_CSV" ]]; then
        SELECT_ARGS+=(--aux-csv "${AUX_CSV}")
    fi
    if [[ -n "$AUX_JOIN_COLUMN" ]]; then
        SELECT_ARGS+=(--aux-join-column "${AUX_JOIN_COLUMN}")
    fi

    python datasets/select_options.py "${SELECT_ARGS[@]}"
fi
echo ""

# ---------------------------------------------------------------
# Step 3: Generate pipeline config files
# ---------------------------------------------------------------
if [[ ! -f "$EXAMPLES_CONFIG" ]]; then
    echo "[step-3] Generating config: ${EXAMPLES_CONFIG}"
    mkdir -p "$(dirname "$EXAMPLES_CONFIG")"
    cat > "$EXAMPLES_CONFIG" <<EOF
{
  "domain": "${DOMAIN}",
  "domain_item": "${DOMAIN_ITEM}",
  "choice_context": "${CHOICE_CONTEXT}",
  "input_path": "${SELECTED_CSV}",
  "template_path": "${TEMPLATE_FILE}",
  "text_column": "${TEXT_COLUMN}",
  "display_column": "${DISPLAY_COLUMN}",
  "id_column": "${ID_COLUMN}",
  "max_options": ${NUM_OPTIONS},
  "request_timeout_seconds": 180,
  "max_retries": 3,
  "max_workers": ${MAX_WORKERS}
}
EOF
fi

if [[ ! -f "$GEN_CONFIG" ]]; then
    echo "[step-3] Generating config: ${GEN_CONFIG}"
    mkdir -p "$(dirname "$GEN_CONFIG")"
    cat > "$GEN_CONFIG" <<EOF
{
  "domain": "${DATASET_NAME}",
  "choice_context": "${CHOICE_CONTEXT}",
  "input_path": "../${SELECTED_CSV}",
  "template_path": "../${TEMPLATE_FILE}",
  "text_column": "${TEXT_COLUMN}",
  "display_column": "${DISPLAY_COLUMN}",
  "id_column": "${ID_COLUMN}",
  "num_dimensions": ${NUM_DIMENSIONS},
  "pair_appearances_per_option": ${PAIR_APPEARANCES},
  "max_options": ${NUM_OPTIONS},
  "dimensions_output_format": "plain",
  "request_timeout_seconds": 180,
  "max_retries": 3,
  "max_workers": ${MAX_WORKERS}
}
EOF
fi
echo ""

# ---------------------------------------------------------------
# Step 4: Choice-grounded dimension discovery
# ---------------------------------------------------------------
echo "[step-4] Running dimension discovery..."
python method_llm_examples/pipeline.py \
    --config "${EXAMPLES_CONFIG}" \
    --base-url "${INSTRUCT_URL}" \
    --model "${INSTRUCT_MODEL}" \
    --api-key dummy \
    --embeddings-parquet "${EMBEDDED_SELECTED}" \
    --embedding-base-url "${EMBED_URL}" \
    --embedding-model "${EMBEDDING_MODEL}" \
    --embedding-column embedding \
    --output-dir "${EXAMPLES_OUTPUT}" \
    --dedup-method llm \
    --num-pairs "${NUM_PAIRS}" \
    --num-themes "${NUM_THEMES}" \
    --num-dimensions "${NUM_DIMENSIONS}" \
    --reasons-per-side "${REASONS_PER_SIDE}" \
    --max-workers "${MAX_WORKERS}" \
    --seed "${SEED}"
echo ""

# ---------------------------------------------------------------
# Step 5: Score options and fit BTL model
# ---------------------------------------------------------------
echo "[step-5] Scoring options and fitting BTL model..."
mkdir -p "${GEN_OUTPUT}"
cp -n "${EXAMPLES_OUTPUT}/dimensions.json" "${GEN_OUTPUT}/dimensions.json" 2>/dev/null || true

python method_llm_gen/pipeline.py run-all \
    --config "${GEN_CONFIG}" \
    --base-url "${INSTRUCT_URL}" \
    --model "${INSTRUCT_MODEL}" \
    --api-key dummy \
    --output-dir "${GEN_OUTPUT}" \
    --seed "${SEED}"
echo ""

# ---------------------------------------------------------------
# Step 6: Find direction vectors
# ---------------------------------------------------------------
echo "[step-6] Finding direction vectors..."
mkdir -p "${DIRECTIONS_OUTPUT}"
python method_directions/find_directions.py \
    --embeddings-parquet "${EMBEDDED_SELECTED}" \
    --bt-scores "${GEN_OUTPUT}/bt_scores.csv" \
    --embedding-column embedding \
    --option-id-column "${ID_COLUMN}" \
    --output-dir "${DIRECTIONS_OUTPUT}" \
    --seed "${SEED}"
echo ""

# ---------------------------------------------------------------
# Step 7: Evaluate basis
# ---------------------------------------------------------------
echo "[step-7] Evaluating basis..."
python method_directions/evaluate_basis.py --scree \
    --embeddings-parquet "${EMBEDDED_SELECTED}" \
    --embedding-column embedding \
    --output-dir "${DIRECTIONS_OUTPUT}"

python method_directions/evaluate_basis.py \
    --embeddings-parquet "${EMBEDDED_SELECTED}" \
    --directions "${DIRECTIONS_OUTPUT}/directions.npz" \
    --bt-scores "${GEN_OUTPUT}/bt_scores.csv" \
    --embedding-column embedding \
    --output-dir "${DIRECTIONS_OUTPUT}"
echo ""

# ---------------------------------------------------------------
# Done
# ---------------------------------------------------------------
echo "============================================"
echo "Pipeline complete: ${DATASET_NAME}"
echo "============================================"
echo "Dimensions:  ${EXAMPLES_OUTPUT}/dimensions.json"
echo "BT scores:   ${GEN_OUTPUT}/bt_scores.csv"
echo "Directions:  ${DIRECTIONS_OUTPUT}/directions.npz"
echo "Evaluation:  ${DIRECTIONS_OUTPUT}/"
echo "Summary:     ${GEN_OUTPUT}/summary.md"
echo "============================================"
