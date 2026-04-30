#!/usr/bin/env bash
# Parallel gen+judge across GPUs 0, 2, 3
# GPU 0: constrained_logistic_qod_250 (4 ckpts)
# GPU 2: constrained_bt_qod_250 (4 ckpts)
# GPU 3: baseline_qod_250/250, random_qod_250 (4 ckpts), good runs (2)
set -euo pipefail
cd /raid/lingo/ayushn/pref-learn

PY="env PYTHONPATH=/raid/lingo/ayushn/local-pkgs /raid/lingo/zachwoj/miniconda3/envs/ml/bin/python3 -u"
LOGDIR="em_experiment/logs"
JUDGE_URLS="http://localhost:8005/v1,http://localhost:8007/v1,http://localhost:8008/v1"

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
        echo "[gen] SKIP $RUN/$CKPT (done)"
        return 0
    fi
    if [ -f "$RUN_DIR/${OUTFILE}.responses.json" ]; then
        echo "[gen] SKIP-GEN $RUN/$CKPT (responses exist, judging)"
        $PY em_experiment/eval_final.py \
            --run_name "$RUN" --checkpoint "$CKPT" --judge_only \
            --judge_workers 192 --judge_urls "$JUDGE_URLS" \
            --output "$OUTFILE" >> "$LOGDIR/${RUN}_eval.log" 2>&1 &
        return 0
    fi
    [ -d "$RUN_DIR/$CKPT" ] || { echo "[gen] NO CKPT $RUN/$CKPT"; return 0; }

    wait_gpu $GPU
    echo "[gen:gpu$GPU] GEN $RUN/$CKPT"
    CUDA_VISIBLE_DEVICES=$GPU $PY em_experiment/eval_final.py \
        --run_name "$RUN" --checkpoint "$CKPT" --n_samples "$N" --gen_only \
        --output "$OUTFILE" >> "$LOGDIR/${RUN}_eval.log" 2>&1 \
        || { echo "[gen:gpu$GPU] ERROR $RUN/$CKPT — skipping"; return 0; }
    echo "[gen:gpu$GPU] JUDGE $RUN/$CKPT (bg)"
    $PY em_experiment/eval_final.py \
        --run_name "$RUN" --checkpoint "$CKPT" --judge_only \
        --judge_workers 192 --judge_urls "$JUDGE_URLS" \
        --output "$OUTFILE" >> "$LOGDIR/${RUN}_eval.log" 2>&1 &
}

# ── GPU 0: constrained_logistic_qod_250 ──────────────────────────────────────
(
    for CKPT in checkpoint-50 checkpoint-100 checkpoint-175 checkpoint-250; do
        STEP=${CKPT#checkpoint-}
        do_gen_judge 0 constrained_logistic_qod_250 "$CKPT" "em_eval_step${STEP}.jsonl" 100
    done
    echo "[gen:gpu0] ALL DONE"
) >> "$LOGDIR/run_all.log" 2>&1 &
PID0=$!

# ── GPU 2: constrained_bt_qod_250 ────────────────────────────────────────────
(
    for CKPT in checkpoint-50 checkpoint-100 checkpoint-175 checkpoint-250; do
        STEP=${CKPT#checkpoint-}
        do_gen_judge 2 constrained_bt_qod_250 "$CKPT" "em_eval_step${STEP}.jsonl" 100
    done
    echo "[gen:gpu2] ALL DONE"
) >> "$LOGDIR/run_all.log" 2>&1 &
PID2=$!

# ── GPU 3: baseline/250, random (4 ckpts), good runs (2) ─────────────────────
(
    # baseline checkpoint-250 (175 is already running)
    do_gen_judge 3 baseline_qod_250 checkpoint-250 "em_eval_step250.jsonl" 100
    # random
    for CKPT in checkpoint-50 checkpoint-100 checkpoint-175 checkpoint-250; do
        STEP=${CKPT#checkpoint-}
        do_gen_judge 3 random_qod_250 "$CKPT" "em_eval_step${STEP}.jsonl" 100
    done
    # good runs
    do_gen_judge 3 baseline_good_175   final "em_eval_175.jsonl" 200
    do_gen_judge 3 constrained_good_175 final "em_eval_175.jsonl" 200
    echo "[gen:gpu3] ALL DONE"
) >> "$LOGDIR/run_all.log" 2>&1 &
PID3=$!

echo "[$(date)] Parallel gen workers: gpu0=PID$PID0 gpu2=PID$PID2 gpu3=PID$PID3"
wait $PID0 && echo "[$(date)] GPU 0 worker done"
wait $PID2 && echo "[$(date)] GPU 2 worker done"
wait $PID3 && echo "[$(date)] GPU 3 worker done"
wait
echo "[$(date)] All parallel gen complete."
