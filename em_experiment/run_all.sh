#!/usr/bin/env bash
# Queue-based pipeline:
#   GPU 1  — training queue (sequential)
#   GPU 6  — generation queue (starts as soon as each run is trained)
#   vLLMs  — judging queue (fires in background after each checkpoint gen)
#
# Coordination via marker files in em_experiment/queue/
set -euo pipefail
cd /raid/lingo/ayushn/pref-learn

PY="/raid/lingo/zachwoj/miniconda3/envs/ml/bin/python3 -u"
LOGDIR="em_experiment/logs"
QDIR="em_experiment/queue"
TRAIN_GPU=1
GEN_GPU=3
JUDGE_URLS="http://localhost:8006/v1,http://localhost:8007/v1"

mkdir -p "$QDIR/trained" "$QDIR/gen_done"

wait_gpu() {
    local IDX=$1
    until [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i $IDX)" -lt 5000 ]; do
        sleep 10
    done
}

# ── Training worker (GPU 1) ───────────────────────────────────────────────────
train_worker() {
    local CKPT_FLAG=$1 COMMON=$2; shift 2
    local RUNS=("$@")
    for RUN in "${RUNS[@]}"; do
        MARKER="$QDIR/trained/$RUN"
        if [ -f "$MARKER" ] || [ -d "em_experiment/runs/$RUN/$CKPT_FLAG" ]; then
            echo "[train] SKIP $RUN (already done)"
            touch "$MARKER"
        else
            rm -rf "em_experiment/runs/$RUN"
            wait_gpu $TRAIN_GPU
            echo "[train] START $RUN (GPU $TRAIN_GPU)"
            eval "CUDA_VISIBLE_DEVICES=$TRAIN_GPU $PY em_experiment/train.py \
                --run_name $RUN $COMMON \
                > $LOGDIR/${RUN}_train.log 2>&1"
            echo "[train] DONE  $RUN"
            touch "$MARKER"
        fi
    done
    echo "[train] all done"
}

# ── Generation worker (GPU 6) ─────────────────────────────────────────────────
gen_worker() {
    local CKPTS=$1 OUTFMT=$2 N=$3; shift 3
    local RUNS=("$@")
    for RUN in "${RUNS[@]}"; do
        # Wait for training to finish
        until [ -f "$QDIR/trained/$RUN" ]; do sleep 5; done
        echo "[gen] START evals for $RUN"
        for CKPT in $CKPTS; do
            OUTFILE=$(eval echo "$OUTFMT")
            if [ -f "em_experiment/runs/$RUN/$OUTFILE" ]; then
                echo "[gen] SKIP $RUN/$CKPT"
                continue
            fi
            CKPT_DIR="em_experiment/runs/$RUN/$CKPT"
            [ -d "$CKPT_DIR" ] || { echo "[gen] SKIP $RUN/$CKPT (no ckpt dir)"; continue; }
            wait_gpu $GEN_GPU
            echo "[gen] GEN  $RUN/$CKPT (GPU $GEN_GPU)"
            CUDA_VISIBLE_DEVICES=$GEN_GPU $PY em_experiment/eval_final.py \
                --run_name "$RUN" --checkpoint "$CKPT" \
                --n_samples "$N" --gen_only \
                --output "$OUTFILE" >> "$LOGDIR/${RUN}_eval.log" 2>&1
            echo "[gen] JUDGE $RUN/$CKPT (background)"
            $PY em_experiment/eval_final.py \
                --run_name "$RUN" --checkpoint "$CKPT" \
                --judge_only --judge_workers 64 \
                --judge_urls "$JUDGE_URLS" \
                --output "$OUTFILE" >> "$LOGDIR/${RUN}_eval.log" 2>&1 &
        done
        echo "[gen] DONE evals for $RUN"
    done
    echo "[gen] all done"
}

# ── Define run lists ──────────────────────────────────────────────────────────
MAIN_RUNS=(
    "baseline_qod_250"
    "constrained_logistic_qod_250"
    "constrained_bt_qod_250"
    "random_qod_250"
)
GOOD_RUNS=(
    "baseline_good_175"
    "constrained_good_175"
)

MAIN_COMMON="--max_steps 250 --eval_every 25 --no_eval --seed 42 --lora_targets q_proj,o_proj,down_proj"
GOOD_COMMON="--max_steps 175 --eval_every 175 --no_eval --seed 42 --lora_targets q_proj,o_proj,down_proj --good_only"

# Pre-mark already-trained runs
[ -d "em_experiment/runs/baseline_qod_250/checkpoint-250" ] && touch "$QDIR/trained/baseline_qod_250" || true

echo "[$(date)] Starting pipeline..."

# ── Launch training worker for main runs (GPU 1) ──────────────────────────────
(
    train_worker "checkpoint-250" "$MAIN_COMMON" "${MAIN_RUNS[@]}"
    # Then good-data runs on same GPU 1
    train_worker "final" \
        "--max_steps 175 --eval_every 175 --no_eval --seed 42 --lora_targets q_proj,o_proj,down_proj --good_only" \
        "${GOOD_RUNS[@]}"
    # Mark all training complete
    touch "$QDIR/all_training_done"
) &
TRAIN_PID=$!
echo "[$(date)] Training worker started (PID=$TRAIN_PID)"

# ── Launch constrained runs with their extra args ─────────────────────────────
# (train_worker uses eval to build command, so we need per-run args)
# Override: handle the per-run flags by pre-populating a per-run arg file
# Actually, simplest: use separate targeted train calls via the marker system

# Patch: since MAIN_COMMON is used as-is above and the constrained runs need extra
# flags, re-implement with per-run args via a queue file approach
kill $TRAIN_PID 2>/dev/null || true

# Clean approach: explicit per-run train commands feeding into the same marker system
(
    set -euo pipefail
    cd /raid/lingo/ayushn/pref-learn

    do_train() {
        local RUN=$1; shift
        local DONE_FLAG=$1; shift
        if [ -f "$QDIR/trained/$RUN" ] || [ -d "em_experiment/runs/$RUN/$DONE_FLAG" ]; then
            echo "[train] SKIP $RUN"
            touch "$QDIR/trained/$RUN"; return
        fi
        rm -rf "em_experiment/runs/$RUN"
        until [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i $TRAIN_GPU)" -lt 5000 ]; do sleep 10; done
        echo "[train] START $RUN"
        CUDA_VISIBLE_DEVICES=$TRAIN_GPU $PY em_experiment/train.py --run_name "$RUN" "$@" \
            > "$LOGDIR/${RUN}_train.log" 2>&1
        echo "[train] DONE  $RUN"
        touch "$QDIR/trained/$RUN"
    }

    COMMON="--max_steps 250 --eval_every 25 --no_eval --seed 42 --lora_targets q_proj,o_proj,down_proj"
    GOOD="--max_steps 175 --eval_every 175 --no_eval --seed 42 --lora_targets q_proj,o_proj,down_proj --good_only"

    do_train baseline_qod_250             checkpoint-250 $COMMON
    do_train constrained_logistic_qod_250 checkpoint-250 $COMMON --project --directions em_directions_logistic_30d_med.pt
    do_train constrained_bt_qod_250       checkpoint-250 $COMMON --project --directions bt_pooled_10d.pt
    do_train random_qod_250               checkpoint-250 $COMMON --project --random_directions
    do_train baseline_good_175            final          $GOOD
    do_train constrained_good_175         final          $GOOD --project --directions em_directions_logistic_30d_med.pt

    touch "$QDIR/all_training_done"
    echo "[train] ALL DONE"
) >> "$LOGDIR/run_all.log" 2>&1 &
TRAIN_PID=$!
echo "[$(date)] Train worker PID=$TRAIN_PID"

# ── Launch generation worker for main runs (GPU 6) ────────────────────────────
(
    set -euo pipefail
    cd /raid/lingo/ayushn/pref-learn

    do_gen_judge() {
        local RUN=$1 CKPT=$2 OUTFILE=$3 N=$4
        [ -f "em_experiment/runs/$RUN/$OUTFILE" ] && { echo "[gen] SKIP $RUN/$CKPT"; return; }
        [ -d "em_experiment/runs/$RUN/$CKPT" ]   || { echo "[gen] NO CKPT $RUN/$CKPT"; return; }
        until [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i $GEN_GPU)" -lt 5000 ]; do sleep 10; done
        # Also skip if responses already saved (gen done, judge pending)
        [ -f "em_experiment/runs/$RUN/${OUTFILE}.responses.json" ] && {
            echo "[gen] SKIP-GEN $RUN/$CKPT (responses exist, firing judge)"
            $PY em_experiment/eval_final.py \
                --run_name "$RUN" --checkpoint "$CKPT" --judge_only \
                --judge_workers 64 --judge_urls "$JUDGE_URLS" \
                --output "$OUTFILE" >> "$LOGDIR/${RUN}_eval.log" 2>&1 &
            return
        }
        echo "[gen] GEN $RUN/$CKPT"
        CUDA_VISIBLE_DEVICES=$GEN_GPU $PY em_experiment/eval_final.py \
            --run_name "$RUN" --checkpoint "$CKPT" --n_samples "$N" --gen_only \
            --output "$OUTFILE" >> "$LOGDIR/${RUN}_eval.log" 2>&1 \
            || { echo "[gen] ERROR on gen $RUN/$CKPT — skipping"; return 0; }
        echo "[gen] JUDGE $RUN/$CKPT (bg)"
        $PY em_experiment/eval_final.py \
            --run_name "$RUN" --checkpoint "$CKPT" --judge_only \
            --judge_workers 64 --judge_urls "$JUDGE_URLS" \
            --output "$OUTFILE" >> "$LOGDIR/${RUN}_eval.log" 2>&1 &
    }

    wait_trained() {
        until [ -f "$QDIR/trained/$1" ]; do sleep 5; done
    }

    # Main runs: 4 checkpoints each
    for RUN in baseline_qod_250 constrained_logistic_qod_250 constrained_bt_qod_250 random_qod_250; do
        wait_trained "$RUN"
        echo "[gen] queuing evals for $RUN"
        for CKPT in checkpoint-50 checkpoint-100 checkpoint-175 checkpoint-250; do
            STEP=${CKPT#checkpoint-}
            do_gen_judge "$RUN" "$CKPT" "em_eval_step${STEP}.jsonl" 100
        done
    done

    # Good runs: final checkpoint only
    for RUN in baseline_good_175 constrained_good_175; do
        wait_trained "$RUN"
        echo "[gen] queuing evals for $RUN"
        do_gen_judge "$RUN" "final" "em_eval_175.jsonl" 200
    done

    # Qualitative generation
    until [ -f "$QDIR/all_training_done" ]; do sleep 10; done
    until [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i $GEN_GPU)" -lt 5000 ]; do sleep 10; done
    echo "[gen] qualitative generation..."
    CUDA_VISIBLE_DEVICES=$GEN_GPU $PY em_experiment/gen_qualitative.py \
        >> "$LOGDIR/run_all.log" 2>&1 || echo "[gen] qualitative skipped (script missing)"

    echo "[gen] ALL DONE"
) >> "$LOGDIR/run_all.log" 2>&1 &
GEN_PID=$!
echo "[$(date)] Gen worker PID=$GEN_PID"

echo "[$(date)] Both workers running. Waiting..."
wait $TRAIN_PID && echo "[$(date)] Training complete"
wait $GEN_PID   && echo "[$(date)] Generation+judging complete"

# Wait for any stray background judge jobs
wait
echo "[$(date)] Pipeline complete."

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════"
printf "%-40s %7s %7s %7s %7s\n" "run" "s=50" "s=100" "s=175" "s=250"
for RUN in baseline_qod_250 constrained_logistic_qod_250 constrained_bt_qod_250 random_qod_250; do
    ROW=""
    for CKPT in 50 100 175 250; do
        EM=$($PY -c "
import json
try:
    d=json.loads(open('em_experiment/runs/$RUN/em_eval_step${CKPT}.jsonl').read())
    print(f\"{d['overall_em']:.4f}\")
except: print('  ?  ')
" 2>/dev/null)
        ROW="$ROW $EM"
    done
    printf "%-40s%s\n" "$RUN" "$ROW"
done
echo "════════════════════════════════════════════════════════"
