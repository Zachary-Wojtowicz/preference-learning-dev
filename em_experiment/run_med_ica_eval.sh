#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

PY="/raid/lingo/zachwoj/miniconda3/envs/ml/bin/python3 -u"
LOGDIR="em_experiment/logs"
COMMON="--max_steps 175 --eval_every 175 --lora_targets all --no_eval --seed 42"

echo "[$(date)] Waiting for GPU 1 to free up for med_ica training..."
until [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 1)" -lt 5000 ]; do
    sleep 30
done
echo "[$(date)] GPU 1 free. Training med_ica_30d..."

CUDA_VISIBLE_DEVICES=1 $PY em_experiment/train.py \
    --run_name constrained_med_ica_30d_175 $COMMON \
    --project --directions em_directions_ica_30d_med.pt \
    > "$LOGDIR/constrained_med_ica_30d_175.log" 2>&1
echo "[$(date)] med_ica training done."

echo "[$(date)] Waiting for GPU 1 to free up for eval..."
until [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 1)" -lt 5000 ]; do
    sleep 30
done
echo "[$(date)] Running eval for med_ica..."
CUDA_VISIBLE_DEVICES=1 $PY em_experiment/eval_final.py \
    --run_name constrained_med_ica_30d_175 --checkpoint final \
    --n_samples 200 --judge_workers 32 \
    --output em_eval_175.jsonl \
    >> "$LOGDIR/run_med_ica_eval.log" 2>&1

EM=$($PY -c "import json; d=json.loads(open('em_experiment/runs/constrained_med_ica_30d_175/em_eval_175.jsonl').read()); print(f\"{d['overall_em']:.4f}\")" 2>/dev/null || echo "?")
echo "[$(date)] constrained_med_ica_30d_175  EM=$EM"

# Final summary of all medical runs
echo ""
echo "========================================================"
echo "[$(date)] FULL MEDICAL RESULTS @ step 175"
echo "========================================================"
printf "%-42s %s\n" "baseline_175" "EM=0.0731"
for RUN in constrained_med_contrast_30d_175 constrained_med_logistic_30d_175 constrained_med_pca_30d_175 constrained_med_ica_30d_175 constrained_bt_pooled_10d_175; do
    EM=$($PY -c "
import json
try:
    d=json.loads(open('em_experiment/runs/$RUN/em_eval_175.jsonl').read())
    print(f\"{d['overall_em']:.4f}\")
except: print('?')
" 2>/dev/null)
    printf "%-42s %s\n" "$RUN" "EM=$EM"
done
echo "========================================================"
