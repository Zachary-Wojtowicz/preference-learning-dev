#!/usr/bin/env bash
# Full methods sweep: train all direction variants to step 175 then eval each.
# Already done: baseline_175, contrast_30d, pca_30d.
# This script runs: logistic_30d, ica_30d, contrast_10d, contrast_15d,
#                   pca_10d, pca_15d, med_contrast_30d, med_logistic_30d, bt_pooled_10d
#
# Usage: nohup bash em_experiment/run_methods_sweep.sh > em_experiment/logs/methods_sweep.log 2>&1 &

set -euo pipefail
cd "$(dirname "$0")/.."

PY="/raid/lingo/zachwoj/miniconda3/envs/ml/bin/python3 -u"
LOGDIR="em_experiment/logs"
COMMON="--max_steps 175 --eval_every 175 --lora_targets all --no_eval --seed 42"

run_eval() {
    local RUN=$1
    echo "[$(date)] Eval: $RUN"
    CUDA_VISIBLE_DEVICES=6 $PY em_experiment/eval_final.py \
        --run_name "$RUN" --checkpoint final \
        --n_samples 200 --judge_workers 32 \
        --output em_eval_175.jsonl \
        >> "$LOGDIR/methods_sweep.log" 2>&1
    local EM
    EM=$($PY -c "
import json
d=json.loads(open('em_experiment/runs/$RUN/em_eval_175.jsonl').read())
print(f\"{d['overall_em']:.4f}\")
" 2>/dev/null || echo "?")
    echo "[$(date)] Done: $RUN  EM=$EM"
}

echo "========================================================"
echo "Methods sweep started: $(date)"
echo "========================================================"

# ── Wait for GPU pre-jobs to finish ──
echo "[$(date)] Waiting for medical embedding + BT pooled extraction..."
until [ -f datasets/em_medical_qwen32b-embedded.parquet ]; do sleep 10; done
echo "[$(date)] Medical embedding done."
until grep -q "Saving to" em_experiment/logs/extract_bt_pooled.log 2>/dev/null; do sleep 10; done
echo "[$(date)] BT pooled extraction done."

# ── Extract medical directions (CPU) ──
echo "[$(date)] Extracting medical directions..."
$PY em_experiment/extract_directions_fast.py \
    --embeddings datasets/em_medical_qwen32b-embedded.parquet \
    --k 30 --method all \
    --bad_label bad --good_label good \
    --suffix _med
echo "[$(date)] Medical directions ready."

# ── Round 1: logistic_30d (GPU 1) + contrast_10d (GPU 2) ──
echo "[$(date)] Round 1: logistic_30d + contrast_10d"
CUDA_VISIBLE_DEVICES=1 $PY em_experiment/train.py \
    --run_name constrained_logistic_30d_175 $COMMON \
    --project --directions em_directions_logistic_30d.pt \
    > "$LOGDIR/constrained_logistic_30d_175.log" 2>&1 &
PID1=$!

CUDA_VISIBLE_DEVICES=2 $PY em_experiment/train.py \
    --run_name constrained_contrast_10d_175 $COMMON \
    --project --directions em_directions_contrast_10d.pt \
    > "$LOGDIR/constrained_contrast_10d_175.log" 2>&1 &
PID2=$!

wait $PID1 && echo "[$(date)] logistic_30d done"
wait $PID2 && echo "[$(date)] contrast_10d done"

# ── Round 2: ica_30d (GPU 1) + pca_10d (GPU 2) ──
echo "[$(date)] Round 2: ica_30d + pca_10d"
CUDA_VISIBLE_DEVICES=1 $PY em_experiment/train.py \
    --run_name constrained_ica_30d_175 $COMMON \
    --project --directions em_directions_ica_30d.pt \
    > "$LOGDIR/constrained_ica_30d_175.log" 2>&1 &
PID1=$!

CUDA_VISIBLE_DEVICES=2 $PY em_experiment/train.py \
    --run_name constrained_pca_10d_175 $COMMON \
    --project --directions em_directions_pca_10d.pt \
    > "$LOGDIR/constrained_pca_10d_175.log" 2>&1 &
PID2=$!

wait $PID1 && echo "[$(date)] ica_30d done"
wait $PID2 && echo "[$(date)] pca_10d done"

# ── Round 3: med_contrast_30d (GPU 1) + med_logistic_30d (GPU 2) ──
echo "[$(date)] Round 3: med_contrast + med_logistic"
CUDA_VISIBLE_DEVICES=1 $PY em_experiment/train.py \
    --run_name constrained_med_contrast_30d_175 $COMMON \
    --project --directions em_directions_contrast_30d_med.pt \
    > "$LOGDIR/constrained_med_contrast_30d_175.log" 2>&1 &
PID1=$!

CUDA_VISIBLE_DEVICES=2 $PY em_experiment/train.py \
    --run_name constrained_med_logistic_30d_175 $COMMON \
    --project --directions em_directions_logistic_30d_med.pt \
    > "$LOGDIR/constrained_med_logistic_30d_175.log" 2>&1 &
PID2=$!

wait $PID1 && echo "[$(date)] med_contrast done"
wait $PID2 && echo "[$(date)] med_logistic done"

# ── Round 4: bt_pooled_10d (GPU 1) + med_ica_30d (GPU 2) ──
echo "[$(date)] Round 4: bt_pooled + med_ica"
CUDA_VISIBLE_DEVICES=1 $PY em_experiment/train.py \
    --run_name constrained_bt_pooled_10d_175 $COMMON \
    --project --directions bt_pooled_10d.pt \
    > "$LOGDIR/constrained_bt_pooled_10d_175.log" 2>&1 &
PID1=$!

CUDA_VISIBLE_DEVICES=2 $PY em_experiment/train.py \
    --run_name constrained_med_pca_30d_175 $COMMON \
    --project --directions em_directions_pca_30d_med.pt \
    > "$LOGDIR/constrained_med_pca_30d_175.log" 2>&1 &
PID2=$!

wait $PID1 && echo "[$(date)] bt_pooled done"
wait $PID2 && echo "[$(date)] med_pca done"

echo ""
echo "========================================================"
echo "[$(date)] All training done. Running evals..."
echo "========================================================"

RUNS=(
    constrained_logistic_30d_175
    constrained_ica_30d_175
    constrained_contrast_10d_175
    constrained_pca_10d_175
    constrained_med_contrast_30d_175
    constrained_med_logistic_30d_175
    constrained_med_pca_30d_175
    constrained_bt_pooled_10d_175
)

for RUN in "${RUNS[@]}"; do
    run_eval "$RUN"
done

echo ""
echo "========================================================"
echo "[$(date)] RESULTS SUMMARY"
echo "========================================================"
printf "%-40s %s\n" "baseline_175"          "EM=0.0731 (reference)"
printf "%-40s %s\n" "constrained_contrast_30d_175" "EM=0.0500"
printf "%-40s %s\n" "constrained_pca_30d_175"      "EM=0.0581"
for RUN in "${RUNS[@]}"; do
    EM=$($PY -c "
import json
try:
    d=json.loads(open('em_experiment/runs/$RUN/em_eval_175.jsonl').read())
    print(f\"{d['overall_em']:.4f}\")
except: print('?')
" 2>/dev/null)
    printf "%-40s %s\n" "$RUN" "EM=$EM"
done
echo "========================================================"
