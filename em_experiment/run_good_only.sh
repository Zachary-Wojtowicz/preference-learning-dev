#!/usr/bin/env bash
set -euo pipefail
cd /raid/lingo/ayushn/pref-learn

PY="/raid/lingo/zachwoj/miniconda3/envs/ml/bin/python3 -u"
LOGDIR="em_experiment/logs"

wait_gpu1() {
    until [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 1)" -lt 5000 ]; do
        sleep 30
    done
}

MAIN_PID=2390654
echo "[$(date)] Waiting for main_comparison (PID $MAIN_PID) to finish..."
while kill -0 "$MAIN_PID" 2>/dev/null; do sleep 30; done
echo "[$(date)] main_comparison done. Waiting for GPU 1..."
sleep 15
wait_gpu1

train_if_needed() {
    local RUN=$1; shift
    if [ -d "em_experiment/runs/$RUN/final" ]; then
        echo "[$(date)] $RUN already trained, skipping."
    else
        rm -rf "em_experiment/runs/$RUN"
        wait_gpu1
        echo "[$(date)] Training $RUN..."
        CUDA_VISIBLE_DEVICES=1 $PY em_experiment/train.py --run_name "$RUN" "$@" \
            > "$LOGDIR/${RUN}.log" 2>&1
        echo "[$(date)] $RUN done."
    fi
}

train_if_needed baseline_good_175 \
    --max_steps 175 --eval_every 175 --no_eval \
    --lora_targets q_proj,o_proj,down_proj \
    --good_only --seed 42

train_if_needed constrained_good_175 \
    --max_steps 175 --eval_every 175 --no_eval \
    --lora_targets q_proj,o_proj,down_proj \
    --project --directions em_directions_logistic_30d_med.pt \
    --good_only --seed 42

wait_gpu1

# --- Eval both: pipeline generation + background judging ---
judge_pids=()
for RUN in baseline_good_175 constrained_good_175; do
    wait_gpu1
    echo "[$(date)] Generating $RUN (n=200)..."
    CUDA_VISIBLE_DEVICES=1 $PY em_experiment/eval_final.py \
        --run_name "$RUN" --checkpoint final \
        --n_samples 200 --gen_only \
        --output em_eval_175.jsonl \
        >> "$LOGDIR/${RUN}_eval.log" 2>&1
    echo "[$(date)] Judging $RUN in background..."
    $PY em_experiment/eval_final.py \
        --run_name "$RUN" --checkpoint final \
        --judge_only --judge_workers 96 \
        --output em_eval_175.jsonl \
        >> "$LOGDIR/${RUN}_eval.log" 2>&1 &
    judge_pids+=($!)
done
echo "[$(date)] Waiting for all judge jobs..."
for pid in "${judge_pids[@]}"; do wait "$pid" || true; done

# --- Summary ---
echo ""
echo "============================================================"
echo "[$(date)] GOOD-DATA RESULTS @ step 175"
echo "============================================================"
printf "%-40s  %s\n" "baseline_175 (bad data, unconstrained)"    "EM=0.0731"
printf "%-40s  %s\n" "constrained_qod_175 (bad data, proj)"      "EM=0.0000"
for RUN in baseline_good_175 constrained_good_175; do
    EM=$($PY -c "
import json
try:
    d=json.loads(open('em_experiment/runs/$RUN/em_eval_175.jsonl').read())
    print(f\"{d['overall_em']:.4f}\")
except: print('?')
" 2>/dev/null)
    printf "%-40s  %s\n" "$RUN" "EM=$EM"
done
echo "============================================================"
