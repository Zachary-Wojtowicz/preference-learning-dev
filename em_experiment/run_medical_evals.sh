#!/usr/bin/env bash
# Wait for GPU 1 to free up, then rerun the 2 failed medical training runs
# and eval all 4 medical-direction conditions.
#
# Usage: nohup bash em_experiment/run_medical_evals.sh > em_experiment/logs/medical_evals.log 2>&1 &

set -euo pipefail
cd "$(dirname "$0")/.."

PY="/raid/lingo/zachwoj/miniconda3/envs/ml/bin/python3 -u"
LOGDIR="em_experiment/logs"
COMMON="--max_steps 175 --eval_every 175 --lora_targets all --no_eval --seed 42"

echo "[$(date)] Waiting for GPU 1 to free up..."
until [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 1)" -lt 5000 ]; do
    sleep 30
done
echo "[$(date)] GPU 1 free."

# Rerun the 2 medical runs that crashed on GPU 2
echo "[$(date)] Training med_logistic_30d on GPU 1..."
CUDA_VISIBLE_DEVICES=1 $PY em_experiment/train.py \
    --run_name constrained_med_logistic_30d_175 $COMMON \
    --project --directions em_directions_logistic_30d_med.pt \
    > "$LOGDIR/constrained_med_logistic_30d_175.log" 2>&1
echo "[$(date)] med_logistic done."

echo "[$(date)] Training med_pca_30d on GPU 1..."
CUDA_VISIBLE_DEVICES=1 $PY em_experiment/train.py \
    --run_name constrained_med_pca_30d_175 $COMMON \
    --project --directions em_directions_pca_30d_med.pt \
    > "$LOGDIR/constrained_med_pca_30d_175.log" 2>&1
echo "[$(date)] med_pca done."

# Eval all medical conditions
echo "[$(date)] Running evals on GPU 1..."
for RUN in \
    constrained_med_contrast_30d_175 \
    constrained_med_logistic_30d_175 \
    constrained_med_pca_30d_175 \
    constrained_bt_pooled_10d_175; do

    echo "[$(date)] Eval: $RUN"
    CUDA_VISIBLE_DEVICES=1 $PY em_experiment/eval_final.py \
        --run_name "$RUN" --checkpoint final \
        --n_samples 200 --judge_workers 32 \
        --output em_eval_175.jsonl \
        >> "$LOGDIR/medical_evals.log" 2>&1
    EM=$($PY -c "
import json
d=json.loads(open('em_experiment/runs/$RUN/em_eval_175.jsonl').read())
print(f\"{d['overall_em']:.4f}\")
" 2>/dev/null || echo "?")
    echo "[$(date)] $RUN  EM=$EM"
done

echo ""
echo "========================================================"
echo "[$(date)] MEDICAL DIRECTION RESULTS @ step 175"
echo "========================================================"
printf "%-42s %s\n" "baseline_175"                    "EM=0.0731"
printf "%-42s %s\n" "constrained_contrast_30d_175"    "EM=0.0500  (code dirs)"
printf "%-42s %s\n" "constrained_pca_30d_175"         "EM=0.0581  (code dirs)"
for RUN in \
    constrained_med_contrast_30d_175 \
    constrained_med_logistic_30d_175 \
    constrained_med_pca_30d_175 \
    constrained_bt_pooled_10d_175; do
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
