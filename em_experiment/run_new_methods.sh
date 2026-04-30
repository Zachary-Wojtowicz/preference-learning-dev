#!/usr/bin/env bash
# New-methods sweep: SVM, meandiff, logistic-1d, contrast-med, ica-med
# All trained for 250 steps with same hyperparams as existing qod_250 runs.
# Training: GPU 0 (sequential). Generation: GPU 3. Judging: :8005,:8008.
set -euo pipefail
cd /raid/lingo/ayushn/pref-learn

PY="env PYTHONPATH=/raid/lingo/ayushn/local-pkgs /raid/lingo/zachwoj/miniconda3/envs/ml/bin/python3 -u"
LOGDIR="em_experiment/logs"
QDIR="em_experiment/queue"
TRAIN_GPU=1
GEN_GPU=6
JUDGE_URLS="http://localhost:8010/v1,http://localhost:8012/v1"

mkdir -p "$QDIR/trained"

wait_gpu() {
    local IDX=$1
    until [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i $IDX)" -lt 5000 ]; do
        sleep 15
    done
}

do_train() {
    local RUN=$1 DONE_FLAG=$2; shift 2
    if [ -f "$QDIR/trained/$RUN" ] || [ -d "em_experiment/runs/$RUN/$DONE_FLAG" ]; then
        echo "[train] SKIP $RUN"
        touch "$QDIR/trained/$RUN"; return
    fi
    rm -rf "em_experiment/runs/$RUN"
    wait_gpu $TRAIN_GPU
    echo "[train] START $RUN"
    CUDA_VISIBLE_DEVICES=$TRAIN_GPU $PY em_experiment/train.py --run_name "$RUN" "$@" \
        > "$LOGDIR/${RUN}_train.log" 2>&1
    echo "[train] DONE  $RUN"
    touch "$QDIR/trained/$RUN"
}

do_gen_judge() {
    local RUN=$1 CKPT=$2 OUTFILE=$3 N=$4
    [ -f "em_experiment/runs/$RUN/$OUTFILE" ] && { echo "[gen] SKIP $RUN/$CKPT"; return; }
    [ -d "em_experiment/runs/$RUN/$CKPT" ]   || { echo "[gen] NO CKPT $RUN/$CKPT"; return; }
    [ -f "em_experiment/runs/$RUN/${OUTFILE}.responses.json" ] && {
        echo "[gen] responses exist, judging $RUN/$CKPT"
        $PY em_experiment/eval_final.py \
            --run_name "$RUN" --checkpoint "$CKPT" --judge_only \
            --judge_workers 128 --judge_urls "$JUDGE_URLS" \
            --output "$OUTFILE" >> "$LOGDIR/${RUN}_eval.log" 2>&1
        return
    }
    wait_gpu $GEN_GPU
    echo "[gen] GEN $RUN/$CKPT"
    CUDA_VISIBLE_DEVICES=$GEN_GPU $PY em_experiment/eval_final.py \
        --run_name "$RUN" --checkpoint "$CKPT" --n_samples "$N" --gen_only \
        --output "$OUTFILE" >> "$LOGDIR/${RUN}_eval.log" 2>&1 \
        || { echo "[gen] ERROR gen $RUN/$CKPT"; return 0; }
    echo "[gen] JUDGE $RUN/$CKPT (bg)"
    $PY em_experiment/eval_final.py \
        --run_name "$RUN" --checkpoint "$CKPT" --judge_only \
        --judge_workers 128 --judge_urls "$JUDGE_URLS" \
        --output "$OUTFILE" >> "$LOGDIR/${RUN}_eval.log" 2>&1 &
}

COMMON="--max_steps 250 --eval_every 25 --no_eval --seed 42 --lora_targets q_proj,o_proj,down_proj"

RUNS=(
    "svm_qod_250"
    "meandiff_qod_250"
    "logistic1d_qod_250"
    "contrast_med_qod_250"
    "ica_med_qod_250"
)

DIRS=(
    "em_directions_svm_30d_med.pt"
    "em_directions_meandiff_1d_med.pt"
    "em_directions_logistic_1d_med.pt"
    "em_directions_contrast_30d_med.pt"
    "em_directions_ica_30d_med.pt"
)

echo "[$(date)] Starting new-methods training pipeline..."

# Training (sequential on GPU 0)
(
    set -euo pipefail
    cd /raid/lingo/ayushn/pref-learn
    for i in "${!RUNS[@]}"; do
        do_train "${RUNS[$i]}" "checkpoint-250" $COMMON --project --directions "${DIRS[$i]}"
    done
    echo "[train] ALL DONE"
) >> "$LOGDIR/run_new_methods.log" 2>&1 &
TRAIN_PID=$!
echo "Train worker PID=$TRAIN_PID"

# Generation + judging (GPU 3, waits for each training to finish)
(
    set -euo pipefail
    cd /raid/lingo/ayushn/pref-learn
    for RUN in "${RUNS[@]}"; do
        until [ -f "$QDIR/trained/$RUN" ]; do sleep 10; done
        echo "[gen] queuing $RUN"
        for CKPT in checkpoint-50 checkpoint-100 checkpoint-175 checkpoint-250; do
            STEP=${CKPT#checkpoint-}
            do_gen_judge "$RUN" "$CKPT" "em_eval_step${STEP}.jsonl" 100
        done
    done
    echo "[gen] ALL DONE"
) >> "$LOGDIR/run_new_methods.log" 2>&1 &
GEN_PID=$!
echo "Gen worker PID=$GEN_PID"

wait $TRAIN_PID && echo "[$(date)] Training complete"
wait $GEN_PID   && echo "[$(date)] Generation+judging complete"
wait
echo "[$(date)] Pipeline complete."
