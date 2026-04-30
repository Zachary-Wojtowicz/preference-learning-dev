#!/usr/bin/env bash
# Clean overnight experiment: all 3 conditions from scratch, no eval during training.
# Baseline + constrained run in parallel on GPUs 2 and 6.
# Random_proj runs after baseline finishes (on GPU 2).
# Then eval_final.py runs on checkpoint-250 and final for all 3.
#
# Usage: nohup bash em_experiment/run_overnight.sh > em_experiment/logs/overnight.log 2>&1 &

set -euo pipefail
cd "$(dirname "$0")/.."   # cd to pref-learn/

PY="/raid/lingo/zachwoj/miniconda3/envs/ml/bin/python3 -u"
LOGDIR="em_experiment/logs"
mkdir -p "$LOGDIR"

COMMON="--max_steps 500 --eval_every 250 --lora_targets all --no_eval --seed 42"

echo "========================================================"
echo "Overnight run started: $(date)"
echo "========================================================"

# ── Phase 1: Train baseline (GPU 2) and constrained (GPU 6) in parallel ──
echo ""
echo "[$(date)] Phase 1: training baseline + constrained in parallel"

CUDA_VISIBLE_DEVICES=2 $PY em_experiment/train.py \
    --run_name baseline_clean $COMMON \
    > "$LOGDIR/baseline_clean.log" 2>&1 &
PID_BASE=$!
echo "  baseline_clean PID=$PID_BASE (GPU 2)"

CUDA_VISIBLE_DEVICES=6 $PY em_experiment/train.py \
    --run_name constrained_clean $COMMON \
    --project --directions preference_directions.pt \
    > "$LOGDIR/constrained_clean.log" 2>&1 &
PID_CON=$!
echo "  constrained_clean PID=$PID_CON (GPU 6)"

# Wait for baseline to finish, then start random_proj on GPU 2
wait $PID_BASE
echo "[$(date)] baseline_clean done"

CUDA_VISIBLE_DEVICES=2 $PY em_experiment/train.py \
    --run_name random_clean $COMMON \
    --project --random_directions \
    > "$LOGDIR/random_clean.log" 2>&1 &
PID_RAND=$!
echo "[$(date)] random_clean PID=$PID_RAND (GPU 2)"

# Wait for constrained and random to finish
wait $PID_CON
echo "[$(date)] constrained_clean done"
wait $PID_RAND
echo "[$(date)] random_clean done"

echo ""
echo "========================================================"
echo "[$(date)] Phase 2: stable eval on all 3 runs"
echo "========================================================"

for RUN in baseline_clean constrained_clean random_clean; do
    for CKPT in checkpoint-250 final; do
        echo ""
        echo "[$(date)] Evaluating $RUN / $CKPT ..."
        CUDA_VISIBLE_DEVICES=6 $PY em_experiment/eval_final.py \
            --run_name "$RUN" --checkpoint "$CKPT" \
            --n_samples 200 --judge_workers 32 \
            --output "em_eval_${CKPT}.jsonl" \
            >> "$LOGDIR/overnight.log" 2>&1
        echo "[$(date)] Done: $RUN / $CKPT"
    done
done

echo ""
echo "========================================================"
echo "[$(date)] All done. Results in em_experiment/runs/*/em_eval_*.jsonl"
echo "========================================================"
