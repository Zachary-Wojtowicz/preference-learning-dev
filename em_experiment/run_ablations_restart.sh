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

echo "[$(date)] Starting ablation restart: qod, down, qo"

wait_gpu1
echo "[$(date)] Training constrained_qod_logistic_175 (q_proj,o_proj,down_proj)..."
CUDA_VISIBLE_DEVICES=1 $PY em_experiment/train.py \
    --run_name constrained_qod_logistic_175 $COMMON \
    --lora_targets q_proj,o_proj,down_proj \
    > "$LOGDIR/constrained_qod_logistic_175.log" 2>&1
echo "[$(date)] qod done."

wait_gpu1
echo "[$(date)] Training constrained_down_logistic_175 (down_proj only)..."
CUDA_VISIBLE_DEVICES=1 $PY em_experiment/train.py \
    --run_name constrained_down_logistic_175 $COMMON \
    --lora_targets down_proj \
    > "$LOGDIR/constrained_down_logistic_175.log" 2>&1
echo "[$(date)] down done."

wait_gpu1
echo "[$(date)] Training constrained_qo_logistic_175 (q_proj,o_proj)..."
CUDA_VISIBLE_DEVICES=1 $PY em_experiment/train.py \
    --run_name constrained_qo_logistic_175 $COMMON \
    --lora_targets q_proj,o_proj \
    > "$LOGDIR/constrained_qo_logistic_175.log" 2>&1
echo "[$(date)] qo done."

echo "[$(date)] All training done. Running evals..."

for RUN in constrained_qod_logistic_175 constrained_down_logistic_175 constrained_qo_logistic_175; do
    wait_gpu1
    echo "[$(date)] Eval: $RUN"
    CUDA_VISIBLE_DEVICES=1 $PY em_experiment/eval_final.py \
        --run_name "$RUN" --checkpoint final \
        --n_samples 200 --judge_workers 32 \
        --output em_eval_175.jsonl \
        >> "$LOGDIR/run_ablations_restart.log" 2>&1
    EM=$($PY -c "import json; d=json.loads(open('em_experiment/runs/$RUN/em_eval_175.jsonl').read()); print(f\"{d['overall_em']:.4f}\")" 2>/dev/null || echo "?")
    echo "[$(date)] $RUN  EM=$EM"
done

echo ""
echo "========================================================"
echo "[$(date)] FULL RESULTS @ step 175"
echo "========================================================"
printf "%-42s %s\n" "baseline_175"                        "EM=0.0731"
printf "%-42s %s\n" "med_contrast_30d (leaky)"            "EM=0.0694"
printf "%-42s %s\n" "med_pca_30d (leaky)"                 "EM=0.0663"
printf "%-42s %s\n" "bt_pooled_10d (leaky)"               "EM=0.0650"
printf "%-42s %s\n" "med_ica_30d (leaky)"                 "EM=0.0619"
printf "%-42s %s\n" "med_logistic_30d (leaky)"            "EM=0.0612"
for RUN in constrained_qod_logistic_175 constrained_down_logistic_175 constrained_qo_logistic_175; do
    EM=$($PY -c "
import json
try:
    d=json.loads(open('em_experiment/runs/$RUN/em_eval_175.jsonl').read())
    print(f\"{d['overall_em']:.4f}\")
except: print('?')
" 2>/dev/null)
    printf "%-42s %s\n" "$RUN (clean)" "EM=$EM"
done
echo "========================================================"
