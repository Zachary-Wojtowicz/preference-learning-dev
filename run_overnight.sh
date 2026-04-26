#!/usr/bin/env bash
set -euo pipefail

# run_overnight.sh — Run multiple pipelines and simulations unattended.
#
# Usage:
#   nohup ./run_overnight.sh > overnight_$(date +%Y%m%d_%H%M).log 2>&1 &
#   tail -f overnight_*.log
#
# Each step logs timestamps so you can diagnose failures.
# The script continues to the next domain if one fails.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_PREFIX="[overnight]"
FAILED=()

log() {
    echo "$LOG_PREFIX [$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

run_step() {
    local label="$1"
    shift
    log "START: $label"
    if "$@"; then
        log "DONE:  $label"
    else
        log "FAILED: $label (exit code $?)"
        FAILED+=("$label")
    fi
}

# ---------------------------------------------------------------
# Discover servers (once)
# ---------------------------------------------------------------
log "Discovering servers..."
INSTRUCT_URL=$(python discover_servers.py --type instruct -q) || {
    log "FATAL: No instruct servers found. Exiting."
    exit 1
}
EMBED_URL=$(python discover_servers.py --type embed -q) || {
    log "FATAL: No embed servers found. Exiting."
    exit 1
}
log "Instruct: $INSTRUCT_URL"
log "Embed:    $EMBED_URL"

# ---------------------------------------------------------------
# 1. Wines — full pipeline + simulations
# ---------------------------------------------------------------
log "========== WINES =========="

run_step "wines: prepare data" \
    python datasets/prepare_wines.py

run_step "wines: pipeline" \
    ./run_pipeline.sh configs/wines_100.yaml

if [[ -f method_directions/outputs/wines_100/directions.npz ]]; then
    run_step "wines: weight-vec simulation" \
        python simulation/run_simulation.py \
            --embeddings-parquet datasets/wines_100/wines_100-embedded.parquet \
            --bt-scores method_llm_gen/outputs/wines_100/bt_scores.csv \
            --directions method_directions/outputs/wines_100/directions.npz \
            --output-dir simulation/outputs/wines_100 \
            --option-id-column wine_id \
            --num-users 50 --num-trials 100 --num-test-pairs 200 \
            --beta 2.0 --slider-noise 0.2 --learning-rate 0.01 \
            --projection-lambda 0.5 --seed 42

    run_step "wines: LLM persona simulation" \
        python simulation/run_llm_simulation.py \
            --embeddings-parquet datasets/wines_100/wines_100-embedded.parquet \
            --bt-scores method_llm_gen/outputs/wines_100/bt_scores.csv \
            --dimensions method_llm_gen/outputs/wines_100/dimensions.json \
            --directions method_directions/outputs/wines_100/directions.npz \
            --option-descriptions datasets/wines_100/wines_100.csv \
            --option-template datasets/wine_prompt.txt \
            --option-id-column wine_id \
            --output-dir simulation/outputs/wines_100_llm \
            --base-url "$INSTRUCT_URL" --api-key dummy \
            --persona-model Qwen/Qwen3-32B --choice-model Qwen/Qwen3-32B \
            --num-personas 20 --num-trials 50 --num-test-pairs 50 \
            --learning-rate 0.01 --projection-lambda 0.5 \
            --max-workers 4 --seed 42 \
            --domain "wines" \
            --choice-context "A person is deciding which wine to buy for dinner, considering flavor profile, value, and personal taste."
else
    log "SKIP: wines simulations (no directions.npz)"
fi

# ---------------------------------------------------------------
# 2. EM Medical — pipeline + simulations
# ---------------------------------------------------------------
log "========== EM MEDICAL =========="

run_step "em_medical: pipeline" \
    ./run_pipeline.sh configs/em_medical.yaml

if [[ -f method_directions/outputs/em_medical/directions.npz ]]; then
    run_step "em_medical: weight-vec simulation" \
        python simulation/run_simulation.py \
            --embeddings-parquet datasets/em_medical/em_medical-embedded.parquet \
            --bt-scores method_llm_gen/outputs/em_medical/bt_scores.csv \
            --directions method_directions/outputs/em_medical/directions.npz \
            --output-dir simulation/outputs/em_medical \
            --option-id-column completion_id \
            --num-users 50 --num-trials 100 --num-test-pairs 200 \
            --beta 2.0 --slider-noise 0.2 --learning-rate 0.01 \
            --projection-lambda 0.5 --seed 42

    run_step "em_medical: LLM persona simulation" \
        python simulation/run_llm_simulation.py \
            --embeddings-parquet datasets/em_medical/em_medical-embedded.parquet \
            --bt-scores method_llm_gen/outputs/em_medical/bt_scores.csv \
            --dimensions method_llm_gen/outputs/em_medical/dimensions.json \
            --directions method_directions/outputs/em_medical/directions.npz \
            --option-descriptions datasets/em_medical/em_medical.csv \
            --option-template datasets/em_medical_prompt.txt \
            --option-id-column completion_id \
            --output-dir simulation/outputs/em_medical_llm \
            --base-url "$INSTRUCT_URL" --api-key dummy \
            --persona-model Qwen/Qwen3-32B --choice-model Qwen/Qwen3-32B \
            --num-personas 20 --num-trials 50 --num-test-pairs 50 \
            --learning-rate 0.01 --projection-lambda 0.5 \
            --max-workers 4 --seed 42 \
            --domain "medical advice responses" \
            --choice-context "A person is evaluating which medical advice response is better, considering accuracy, safety, evidence-based reasoning, and helpfulness."
else
    log "SKIP: em_medical simulations (no directions.npz)"
fi

# ---------------------------------------------------------------
# 3. EM Code — pipeline + simulations
# ---------------------------------------------------------------
log "========== EM CODE =========="

run_step "em_code: pipeline" \
    ./run_pipeline.sh configs/em_code.yaml

if [[ -f method_directions/outputs/em_code/directions.npz ]]; then
    run_step "em_code: weight-vec simulation" \
        python simulation/run_simulation.py \
            --embeddings-parquet datasets/em_code/em_code-embedded.parquet \
            --bt-scores method_llm_gen/outputs/em_code/bt_scores.csv \
            --directions method_directions/outputs/em_code/directions.npz \
            --output-dir simulation/outputs/em_code \
            --option-id-column completion_id \
            --num-users 50 --num-trials 100 --num-test-pairs 200 \
            --beta 2.0 --slider-noise 0.2 --learning-rate 0.01 \
            --projection-lambda 0.5 --seed 42

    run_step "em_code: LLM persona simulation" \
        python simulation/run_llm_simulation.py \
            --embeddings-parquet datasets/em_code/em_code-embedded.parquet \
            --bt-scores method_llm_gen/outputs/em_code/bt_scores.csv \
            --dimensions method_llm_gen/outputs/em_code/dimensions.json \
            --directions method_directions/outputs/em_code/directions.npz \
            --option-descriptions datasets/em_code/em_code.csv \
            --option-template datasets/em_code_prompt.txt \
            --option-id-column completion_id \
            --output-dir simulation/outputs/em_code_llm \
            --base-url "$INSTRUCT_URL" --api-key dummy \
            --persona-model Qwen/Qwen3-32B --choice-model Qwen/Qwen3-32B \
            --num-personas 20 --num-trials 50 --num-test-pairs 50 \
            --learning-rate 0.01 --projection-lambda 0.5 \
            --max-workers 4 --seed 42 \
            --domain "code completions" \
            --choice-context "A developer is evaluating which code implementation to use, considering security, correctness, readability, and best practices."
else
    log "SKIP: em_code simulations (no directions.npz)"
fi

# ---------------------------------------------------------------
# 4. Scree analysis for movies_100 (if not already done)
# ---------------------------------------------------------------
log "========== MOVIES 100 SCREE =========="

if [[ ! -f method_directions/outputs/movies_100/scree_data.csv ]]; then
    run_step "movies_100: scree analysis" \
        python method_directions/evaluate_basis.py --scree \
            --embeddings-parquet datasets/movies_100/movielens-32m-enriched-qwen3emb-100-embedded.parquet \
            --embedding-column embedding \
            --output-dir method_directions/outputs/movies_100
else
    log "SKIP: movies_100 scree (already exists)"
fi

# ---------------------------------------------------------------
# Summary
# ---------------------------------------------------------------
log "=========================================="
log "Overnight run complete."
log "=========================================="

if [[ ${#FAILED[@]} -eq 0 ]]; then
    log "All steps succeeded."
else
    log "FAILURES (${#FAILED[@]}):"
    for f in "${FAILED[@]}"; do
        log "  - $f"
    done
fi

# List all outputs
log ""
log "Outputs:"
for dir in simulation/outputs/*/; do
    if [[ -f "${dir}summary.md" ]]; then
        log "  ✓ $dir"
    else
        log "  ○ $dir (no summary)"
    fi
done

log ""
log "To sync results:"
log "  git add -A && git commit -m 'overnight run results' && git push"
