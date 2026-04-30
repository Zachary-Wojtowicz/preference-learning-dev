#!/usr/bin/env bash
# Temperature-check run: 4 conditions trained to step 175 only.
# Baseline + 3 direction methods (contrast, pca, bt-once-ready) in parallel.
# Then eval each at the step-175 checkpoint (saved as "final" since max_steps=175).
#
# Usage: nohup bash em_experiment/run_temp_check.sh > em_experiment/logs/temp_check.log 2>&1 &

set -euo pipefail
cd "$(dirname "$0")/.."   # cd to pref-learn/

PY="/raid/lingo/zachwoj/miniconda3/envs/ml/bin/python3 -u"
LOGDIR="em_experiment/logs"
mkdir -p "$LOGDIR"

# 175 steps, eval only at the end (no_eval during training), seed fixed
COMMON="--max_steps 175 --eval_every 175 --lora_targets all --no_eval --seed 42"

echo "========================================================"
echo "Temp-check run started: $(date)"
echo "========================================================"

# ── Phase 1: Train all 4 conditions in parallel ──
echo ""
echo "[$(date)] Phase 1: training 4 conditions to step 175"

CUDA_VISIBLE_DEVICES=1 $PY em_experiment/train.py \
    --run_name baseline_175 $COMMON \
    > "$LOGDIR/baseline_175.log" 2>&1 &
PID_BASE=$!
echo "  baseline_175       PID=$PID_BASE (GPU 1)"

CUDA_VISIBLE_DEVICES=2 $PY em_experiment/train.py \
    --run_name constrained_contrast_175 $COMMON \
    --project --directions em_directions_contrast_30d.pt \
    > "$LOGDIR/constrained_contrast_175.log" 2>&1 &
PID_CONTRAST=$!
echo "  constrained_contrast_175  PID=$PID_CONTRAST (GPU 2)"

CUDA_VISIBLE_DEVICES=6 $PY em_experiment/train.py \
    --run_name constrained_pca_175 $COMMON \
    --project --directions em_directions_pca_30d.pt \
    > "$LOGDIR/constrained_pca_175.log" 2>&1 &
PID_PCA=$!
echo "  constrained_pca_175       PID=$PID_PCA (GPU 6)"

wait $PID_BASE
echo "[$(date)] baseline_175 done"
wait $PID_CONTRAST
echo "[$(date)] constrained_contrast_175 done"
wait $PID_PCA
echo "[$(date)] constrained_pca_175 done"

echo ""
echo "========================================================"
echo "[$(date)] Phase 2: eval all 3 at step-175 checkpoint"
echo "========================================================"

for RUN in baseline_175 constrained_contrast_175 constrained_pca_175; do
    echo ""
    echo "[$(date)] Evaluating $RUN / final ..."
    CUDA_VISIBLE_DEVICES=6 $PY em_experiment/eval_final.py \
        --run_name "$RUN" --checkpoint final \
        --n_samples 200 --judge_workers 32 \
        --output em_eval_175.jsonl \
        >> "$LOGDIR/temp_check.log" 2>&1
    echo "[$(date)] Done: $RUN"
done

echo ""
echo "========================================================"
echo "[$(date)] All done. Results:"
for RUN in baseline_175 constrained_contrast_175 constrained_pca_175; do
    echo -n "  $RUN: "
    /raid/lingo/zachwoj/miniconda3/envs/ml/bin/python3 -c "
import json
p = 'em_experiment/runs/$RUN/em_eval_175.jsonl'
try:
    d = json.loads(open(p).read())
    print(f\"EM={d['overall_em']:.4f}\")
except: print('no result yet')
" 2>/dev/null || echo "(not found)"
done
echo "========================================================"
