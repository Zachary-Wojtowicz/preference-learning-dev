#!/usr/bin/env bash
# Recovery: remaining eval jobs with PYTHONPATH fix for broken accelerate metadata
# GPU 0: constrained_logistic 175+250, then constrained_bt 50+100+175
# GPU 3: random 100(judge-only)+175+250, baseline_good+constrained_good
set -euo pipefail
cd /raid/lingo/ayushn/pref-learn

PY="PYTHONPATH=/raid/lingo/ayushn/local-pkgs /raid/lingo/zachwoj/miniconda3/envs/ml/bin/python3 -u"
LOGDIR="em_experiment/logs"
JUDGE_URLS="http://localhost:8007/v1"

wait_gpu() {
    local IDX=$1
    until [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i $IDX)" -lt 5000 ]; do
        sleep 10
    done
}

do_gen_judge() {
    local GPU=$1 RUN=$2 CKPT=$3 OUTFILE=$4 N=$5
    local RUN_DIR="em_experiment/runs/$RUN"
    if [ -f "$RUN_DIR/$OUTFILE" ]; then
        echo "[rec] SKIP $RUN/$CKPT (done)"; return 0
    fi
    if [ -f "$RUN_DIR/${OUTFILE}.responses.json" ]; then
        echo "[rec] SKIP-GEN $RUN/$CKPT (responses exist, judging)"
        eval "PYTHONPATH=/raid/lingo/ayushn/local-pkgs $PY em_experiment/eval_final.py \
            --run_name '$RUN' --checkpoint '$CKPT' --judge_only \
            --judge_workers 64 --judge_urls '$JUDGE_URLS' \
            --output '$OUTFILE'" >> "$LOGDIR/${RUN}_eval.log" 2>&1 &
        wait  # wait for judge to finish before moving on
        return 0
    fi
    [ -d "$RUN_DIR/$CKPT" ] || { echo "[rec] NO CKPT $RUN/$CKPT"; return 0; }
    wait_gpu $GPU
    echo "[rec:gpu$GPU] GEN $RUN/$CKPT"
    CUDA_VISIBLE_DEVICES=$GPU eval "$PY em_experiment/eval_final.py \
        --run_name '$RUN' --checkpoint '$CKPT' --n_samples '$N' --gen_only \
        --output '$OUTFILE'" >> "$LOGDIR/${RUN}_eval.log" 2>&1 \
        || { echo "[rec:gpu$GPU] ERROR $RUN/$CKPT"; return 0; }
    echo "[rec:gpu$GPU] JUDGE $RUN/$CKPT (bg)"
    eval "PYTHONPATH=/raid/lingo/ayushn/local-pkgs $PY em_experiment/eval_final.py \
        --run_name '$RUN' --checkpoint '$CKPT' --judge_only \
        --judge_workers 64 --judge_urls '$JUDGE_URLS' \
        --output '$OUTFILE'" >> "$LOGDIR/${RUN}_eval.log" 2>&1 &
}

# ── GPU 0: logistic 175+250, then bt 50+100+175 ──────────────────────────────
(
    for CKPT in checkpoint-175 checkpoint-250; do
        STEP=${CKPT#checkpoint-}
        do_gen_judge 0 constrained_logistic_qod_250 "$CKPT" "em_eval_step${STEP}.jsonl" 100
    done
    for CKPT in checkpoint-50 checkpoint-100 checkpoint-175; do
        STEP=${CKPT#checkpoint-}
        do_gen_judge 0 constrained_bt_qod_250 "$CKPT" "em_eval_step${STEP}.jsonl" 100
    done
    echo "[rec:gpu0] ALL DONE"
) >> "$LOGDIR/run_all.log" 2>&1 &
PID0=$!

# ── GPU 3: random 100(judge)+175+250, good runs ───────────────────────────────
(
    # random/100: responses.json exists, just judge
    do_gen_judge 3 random_qod_250 checkpoint-100 "em_eval_step100.jsonl" 100
    for CKPT in checkpoint-175 checkpoint-250; do
        STEP=${CKPT#checkpoint-}
        do_gen_judge 3 random_qod_250 "$CKPT" "em_eval_step${STEP}.jsonl" 100
    done
    do_gen_judge 3 baseline_good_175    final "em_eval_175.jsonl" 200
    do_gen_judge 3 constrained_good_175 final "em_eval_175.jsonl" 200
    echo "[rec:gpu3] ALL DONE"
) >> "$LOGDIR/run_all.log" 2>&1 &
PID3=$!

echo "[$(date)] Recovery workers: gpu0=PID$PID0 gpu3=PID$PID3"
wait $PID0 && echo "[$(date)] GPU 0 done"
wait $PID3 && echo "[$(date)] GPU 3 done"
wait
echo "[$(date)] Recovery complete."
