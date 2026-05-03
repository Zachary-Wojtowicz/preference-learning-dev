#!/bin/bash
# run_recal_sims.sh — Re-run the four "main" sims with the recalibrated
# defaults baked into simulation/run_simulation.py and run_llm_simulation.py
# (lambda_partial=0.05, feedback_alpha=0.5).
#
# Reuses the existing LLM choice cache when --seed/--num-personas/--num-trials/
# --num-test-pairs are unchanged → only fits get redone, no new LLM calls.
#
# Usage on align-3:
#   cd /raid/lingo/zachwoj/work/preference-learning-dev
#   git pull
#   ./run_recal_sims.sh 2>&1 | tee /tmp/recal_sims_$(date +%Y%m%d_%H%M).log
#
# Outputs land in:
#   simulation/outputs/{movies_100,movies_100_llm,dailydilemmas,dailydilemmas_llm}/
#
# Sync those four directories back locally to inspect.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

log() { echo "[$(date +%H:%M:%S)] $*"; }

log "=== Discovering instruct vLLM endpoint ==="
INSTRUCT_URL="$(python discover_servers.py --type instruct -q)"
log "INSTRUCT_URL=$INSTRUCT_URL"

# ---------------------------------------------------------------
# movies_100
# ---------------------------------------------------------------
log "=== movies_100: weight-vec sim ==="
python simulation/run_simulation.py \
    --embeddings-parquet datasets/movies_100/movielens-32m-enriched-qwen3emb-100-embedded.parquet \
    --bt-scores method_llm_gen/outputs/movies_100/bt_scores.csv \
    --directions method_directions/outputs/movies_100/directions.npz \
    --output-dir simulation/outputs/movies_100 \
    --option-id-column movie_id \
    --num-users 50 --num-trials 20 --num-test-pairs 200 \
    --beta 2.0 --participant-noise 0.10 --seed 42

log "=== movies_100: LLM persona sim (cache reuse) ==="
python simulation/run_llm_simulation.py \
    --embeddings-parquet datasets/movies_100/movielens-32m-enriched-qwen3emb-100-embedded.parquet \
    --bt-scores method_llm_gen/outputs/movies_100/bt_scores.csv \
    --dimensions method_llm_gen/outputs/movies_100/dimensions.json \
    --directions method_directions/outputs/movies_100/directions.npz \
    --option-descriptions datasets/movies_100/movielens-32m-enriched-qwen3emb-100.csv \
    --option-template datasets/movie_prompt.txt \
    --option-id-column movie_id \
    --output-dir simulation/outputs/movies_100_llm \
    --base-url "$INSTRUCT_URL" --api-key dummy \
    --persona-model Qwen/Qwen3-32B --choice-model Qwen/Qwen3-32B \
    --num-personas 20 --num-trials 20 --num-test-pairs 50 \
    --max-workers 4 --seed 42 \
    --domain movies \
    --choice-context "Which movie would you rather watch right now?"

# ---------------------------------------------------------------
# dailydilemmas (predefined dilemma pairs)
# ---------------------------------------------------------------
log "=== dailydilemmas: weight-vec sim ==="
python simulation/run_simulation.py \
    --embeddings-parquet datasets/dailydilemmas/selected_actions-embedded.parquet \
    --bt-scores method_llm_gen/outputs/dailydilemmas/bt_scores.csv \
    --directions method_directions/outputs/dailydilemmas/directions.npz \
    --output-dir simulation/outputs/dailydilemmas \
    --option-id-column action_id \
    --predefined-pairs datasets/dailydilemmas/predefined_pairs.json \
    --num-users 50 --num-trials 20 --num-test-pairs 100 \
    --beta 2.0 --participant-noise 0.10 --seed 42

log "=== dailydilemmas: LLM persona sim (cache reuse) ==="
python simulation/run_llm_simulation.py \
    --embeddings-parquet datasets/dailydilemmas/selected_actions-embedded.parquet \
    --bt-scores method_llm_gen/outputs/dailydilemmas/bt_scores.csv \
    --dimensions method_llm_gen/outputs/dailydilemmas/dimensions.json \
    --directions method_directions/outputs/dailydilemmas/directions.npz \
    --option-descriptions datasets/dailydilemmas/selected_actions.csv \
    --option-template datasets/dailydilemmas_prompt.txt \
    --option-id-column action_id \
    --predefined-pairs datasets/dailydilemmas/predefined_pairs.json \
    --output-dir simulation/outputs/dailydilemmas_llm \
    --base-url "$INSTRUCT_URL" --api-key dummy \
    --persona-model Qwen/Qwen3-32B --choice-model Qwen/Qwen3-32B \
    --num-personas 20 --num-trials 20 --num-test-pairs 50 \
    --max-workers 4 --seed 42 \
    --domain "everyday moral dilemmas" \
    --choice-context "Which action is more ethical or understandable?"

log "=== Done ==="
log "Sync these dirs locally:"
log "  simulation/outputs/movies_100/"
log "  simulation/outputs/movies_100_llm/"
log "  simulation/outputs/dailydilemmas/"
log "  simulation/outputs/dailydilemmas_llm/"
