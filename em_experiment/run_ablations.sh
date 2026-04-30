#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

PY="/raid/lingo/zachwoj/miniconda3/envs/ml/bin/python3 -u"
LOGDIR="em_experiment/logs"
COMMON="--max_steps 175 --eval_every 175 --no_eval --seed 42 --project --directions em_directions_logistic_30d_med.pt"

wait_gpu1() {
    until [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 1)" -lt 5000 ]; do
        sleep 30
    done
}

# Wait for med_ica watcher (PID 1433552) to finish
echo "[$(date)] Waiting for med_ica watcher (PID 1433552) to finish..."
while kill -0 1433552 2>/dev/null; do sleep 30; done
echo "[$(date)] med_ica watcher done."

# --- Train 1: q_proj,o_proj,down_proj (only projected modules) ---
echo "[$(date)] Waiting for GPU 1..."
wait_gpu1
echo "[$(date)] Training constrained_qod_logistic_175 (q_proj,o_proj,down_proj)..."
CUDA_VISIBLE_DEVICES=1 $PY em_experiment/train.py \
    --run_name constrained_qod_logistic_175 $COMMON \
    --lora_targets q_proj,o_proj,down_proj \
    > "$LOGDIR/constrained_qod_logistic_175.log" 2>&1
echo "[$(date)] qod done."

# --- Train 2: down_proj only ---
echo "[$(date)] Waiting for GPU 1..."
wait_gpu1
echo "[$(date)] Training constrained_down_logistic_175 (down_proj only)..."
CUDA_VISIBLE_DEVICES=1 $PY em_experiment/train.py \
    --run_name constrained_down_logistic_175 $COMMON \
    --lora_targets down_proj \
    > "$LOGDIR/constrained_down_logistic_175.log" 2>&1
echo "[$(date)] down done."

# --- Train 3: q_proj,o_proj only (attention, no MLP) ---
echo "[$(date)] Waiting for GPU 1..."
wait_gpu1
echo "[$(date)] Training constrained_qo_logistic_175 (q_proj,o_proj only)..."
CUDA_VISIBLE_DEVICES=1 $PY em_experiment/train.py \
    --run_name constrained_qo_logistic_175 $COMMON \
    --lora_targets q_proj,o_proj \
    > "$LOGDIR/constrained_qo_logistic_175.log" 2>&1
echo "[$(date)] qo done."

echo "[$(date)] All 3 training runs complete. Starting evals..."

# --- Eval all 3 at once ---
wait_gpu1
for RUN in constrained_qod_logistic_175 constrained_down_logistic_175 constrained_qo_logistic_175; do
    echo "[$(date)] Eval: $RUN"
    CUDA_VISIBLE_DEVICES=1 $PY em_experiment/eval_final.py \
        --run_name "$RUN" --checkpoint final \
        --n_samples 200 --judge_workers 32 \
        --output em_eval_175.jsonl \
        >> "$LOGDIR/run_ablations.log" 2>&1
    EM=$($PY -c "
import json
d=json.loads(open('em_experiment/runs/$RUN/em_eval_175.jsonl').read())
print(f\"{d['overall_em']:.4f}\")
" 2>/dev/null || echo "?")
    echo "[$(date)] $RUN  EM=$EM"
done

echo ""
echo "========================================================"
echo "[$(date)] ABLATION RESULTS @ step 175 (logistic_30d_med dirs)"
echo "========================================================"
printf "%-42s %s\n" "baseline_175"                        "EM=0.0731"
printf "%-42s %s\n" "constrained_med_logistic_30d_175"    "EM=? (all 7 modules, leaky)"
for RUN in constrained_qod_logistic_175 constrained_down_logistic_175 constrained_qo_logistic_175; do
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
