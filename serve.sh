#!/usr/bin/env bash
# serve.sh — Manage vLLM GPU servers for the preference-learning pipeline.
#
# Safety: Only manages YOUR processes. Will never kill another user's servers.
# GPU detection respects all users (won't launch on a GPU someone else is using).
#
# Usage:
#   ./serve.sh status                  # Show running servers and GPU status
#   ./serve.sh up [--embed N] [--instruct N]  # Launch servers to reach target counts
#   ./serve.sh down [--embed] [--instruct] [--all]  # Stop servers
#   ./serve.sh logs <port>             # Tail logs for a server
#
# Configuration (edit below or override via environment):

set -euo pipefail

# --- Configuration -----------------------------------------------------------
EMBED_MODEL="${EMBED_MODEL:-Qwen/Qwen3-Embedding-8B}"
INSTRUCT_MODEL="${INSTRUCT_MODEL:-Qwen/Qwen3-32B}"

EMBED_PORT_START=8003
INSTRUCT_PORT_START=8004

EMBED_DTYPE="${EMBED_DTYPE:-float16}"
INSTRUCT_DTYPE="${INSTRUCT_DTYPE:-float16}"

EMBED_MAX_LEN="${EMBED_MAX_LEN:-8192}"
INSTRUCT_MAX_LEN="${INSTRUCT_MAX_LEN:-131072}"

export HF_HOME="${HF_HOME:-/raid/lingo/zachwoj/huggingface}"

LOG_DIR="${LOG_DIR:-/raid/lingo/zachwoj/work/preference-learning-dev/logs}"
# -----------------------------------------------------------------------------

ME=$(whoami)
mkdir -p "$LOG_DIR"

# --- Helpers -----------------------------------------------------------------

get_free_gpus() {
    # Returns GPU indices with no processes from ANY user.
    # This is intentional — we never launch on a GPU someone else is using.
    local all_gpus used_gpus free_gpus
    all_gpus=$(nvidia-smi --query-gpu=index --format=csv,noheader,nounits | tr -d ' ')
    used_gpus=$(nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader 2>/dev/null \
        | sort -u \
        | while read -r uuid; do
            nvidia-smi --query-gpu=index,gpu_uuid --format=csv,noheader,nounits \
                | grep "$uuid" | cut -d',' -f1 | tr -d ' '
        done | sort -u)

    free_gpus=""
    for g in $all_gpus; do
        if ! echo "$used_gpus" | grep -qx "$g"; then
            free_gpus="$free_gpus $g"
        fi
    done
    echo "$free_gpus" | xargs  # trim
}

_parse_vllm_procs() {
    # Parse vLLM server info from ps output lines.
    # Outputs: PID PORT GPU TYPE MODEL USER
    while read -r line; do
        local pid port gpu model_type model_name user
        user=$(echo "$line" | awk '{print $1}')
        pid=$(echo "$line" | awk '{print $2}')
        port=$(echo "$line" | grep -oP '(?<=--port\s)\d+' || echo "?")
        gpu=$(tr '\0' '\n' < /proc/$pid/environ 2>/dev/null \
            | grep '^CUDA_VISIBLE_DEVICES=' | cut -d= -f2 || echo "?")
        model_name=$(echo "$line" | grep -oP '(?<=serve\s)\S+' || echo "?")

        if echo "$line" | grep -qE '(--task embed|--runner pooling)'; then
            model_type="embed"
        else
            model_type="instruct"
        fi
        echo "$pid $port $gpu $model_type $model_name $user"
    done
}

find_my_servers() {
    # Find only the current user's vLLM servers.
    # Used by: cmd_down, count_servers, next_port — anything that acts on processes.
    ps -u "$ME" -o user,pid,args 2>/dev/null \
        | grep '[v]llm.entrypoints' \
        | _parse_vllm_procs
}

find_all_servers() {
    # Find ALL users' vLLM servers. Used only for status display.
    ps aux 2>/dev/null \
        | grep '[v]llm.entrypoints' \
        | _parse_vllm_procs
}

count_servers() {
    local type="$1"
    find_my_servers | awk -v t="$type" '$4 == t' | wc -l
}

next_port() {
    local base="$1"
    local port=$base
    # Check against ALL servers (not just ours) to avoid port collisions
    while find_all_servers | awk '{print $2}' | grep -qx "$port" 2>/dev/null; do
        port=$((port + 1))
    done
    # Also check if port is bound by something else entirely
    while ss -tlnp 2>/dev/null | grep -q ":${port} " ; do
        port=$((port + 1))
    done
    echo "$port"
}

launch_embed() {
    local gpu="$1"
    local port
    port=$(next_port $EMBED_PORT_START)
    local logfile="$LOG_DIR/embed_gpu${gpu}_port${port}.log"

    echo "  Launching embed server on GPU $gpu, port $port ..."
    CUDA_VISIBLE_DEVICES="$gpu" nohup vllm serve "$EMBED_MODEL" \
        --task embed \
        --host 0.0.0.0 \
        --port "$port" \
        --dtype "$EMBED_DTYPE" \
        --max-model-len "$EMBED_MAX_LEN" \
        > "$logfile" 2>&1 &

    echo "  PID $!, log: $logfile"
}

launch_instruct() {
    local gpu="$1"
    local port
    port=$(next_port $INSTRUCT_PORT_START)
    local logfile="$LOG_DIR/instruct_gpu${gpu}_port${port}.log"

    echo "  Launching instruct server on GPU $gpu, port $port ..."
    CUDA_VISIBLE_DEVICES="$gpu" nohup vllm serve "$INSTRUCT_MODEL" \
        --host 0.0.0.0 \
        --port "$port" \
        --dtype "$INSTRUCT_DTYPE" \
        --max-model-len "$INSTRUCT_MAX_LEN" \
        > "$logfile" 2>&1 &

    echo "  PID $!, log: $logfile"
}

# --- Commands ----------------------------------------------------------------

cmd_status() {
    echo "=== GPU Status ==="
    nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu \
        --format=csv,noheader | while IFS=',' read -r idx name mem_used mem_total util; do
        idx=$(echo "$idx" | xargs)
        name=$(echo "$name" | xargs)
        mem_used=$(echo "$mem_used" | xargs)
        mem_total=$(echo "$mem_total" | xargs)
        util=$(echo "$util" | xargs)
        printf "  GPU %-2s  %-30s  %s / %s  (%s)\n" "$idx" "$name" "$mem_used" "$mem_total" "$util"
    done
    echo ""

    echo "=== Your Servers ($ME) ==="
    local my_servers
    my_servers=$(find_my_servers)
    if [ -z "$my_servers" ]; then
        echo "  (none)"
    else
        printf "  %-8s %-6s %-5s %-10s %s\n" "PID" "PORT" "GPU" "TYPE" "MODEL"
        echo "$my_servers" | while read -r pid port gpu type model user; do
            printf "  %-8s %-6s %-5s %-10s %s\n" "$pid" "$port" "$gpu" "$type" "$model"
        done
    fi
    echo ""

    # Show other users' servers for awareness
    local other_servers
    other_servers=$(find_all_servers | awk -v me="$ME" '$6 != me')
    if [ -n "$other_servers" ]; then
        echo "=== Other Users' Servers ==="
        printf "  %-8s %-6s %-5s %-10s %-10s %s\n" "PID" "PORT" "GPU" "TYPE" "USER" "MODEL"
        echo "$other_servers" | while read -r pid port gpu type model user; do
            printf "  %-8s %-6s %-5s %-10s %-10s %s\n" "$pid" "$port" "$gpu" "$type" "$user" "$model"
        done
        echo ""
    fi

    local n_embed n_instruct
    n_embed=$(echo "$my_servers" | awk '$4 == "embed"' | grep -c . || true)
    n_instruct=$(echo "$my_servers" | awk '$4 == "instruct"' | grep -c . || true)

    local free
    free=$(get_free_gpus)
    local n_free
    if [ -z "$free" ]; then
        n_free=0
    else
        n_free=$(echo "$free" | wc -w)
    fi

    echo "=== Summary ==="
    echo "  Your embed servers:    $n_embed  (model: $EMBED_MODEL)"
    echo "  Your instruct servers: $n_instruct  (model: $INSTRUCT_MODEL)"
    echo "  Free GPUs:             $n_free  ($free)"
    echo ""
    echo "  Embed port range:    $EMBED_PORT_START+"
    echo "  Instruct port range: $INSTRUCT_PORT_START+"
}

cmd_up() {
    local target_embed=0
    local target_instruct=0

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --embed)    target_embed="$2"; shift 2 ;;
            --instruct) target_instruct="$2"; shift 2 ;;
            *) echo "Unknown option: $1"; exit 1 ;;
        esac
    done

    local current_embed current_instruct
    current_embed=$(count_servers "embed")
    current_instruct=$(count_servers "instruct")

    local need_embed=$((target_embed - current_embed))
    local need_instruct=$((target_instruct - current_instruct))

    if [ "$need_embed" -le 0 ] && [ "$need_instruct" -le 0 ]; then
        echo "Already at target: $current_embed embed, $current_instruct instruct."
        [ "$need_embed" -lt 0 ] && echo "  (Have $current_embed embed but target is $target_embed — use 'down' to stop extras)"
        [ "$need_instruct" -lt 0 ] && echo "  (Have $current_instruct instruct but target is $target_instruct — use 'down' to stop extras)"
        return
    fi

    local free_gpus
    free_gpus=($(get_free_gpus))
    local n_free=${#free_gpus[@]}

    if [ "$need_embed" -lt 0 ]; then need_embed=0; fi
    if [ "$need_instruct" -lt 0 ]; then need_instruct=0; fi
    local total_needed=$((need_embed + need_instruct))

    if [ "$total_needed" -gt "$n_free" ]; then
        echo "Need $total_needed GPUs but only $n_free free. Launching what we can."
    fi

    local gpu_idx=0

    # Launch embed servers first
    local launched_embed=0
    while [ "$launched_embed" -lt "$need_embed" ] && [ "$gpu_idx" -lt "$n_free" ]; do
        launch_embed "${free_gpus[$gpu_idx]}"
        gpu_idx=$((gpu_idx + 1))
        launched_embed=$((launched_embed + 1))
    done

    # Then instruct servers
    local launched_instruct=0
    while [ "$launched_instruct" -lt "$need_instruct" ] && [ "$gpu_idx" -lt "$n_free" ]; do
        launch_instruct "${free_gpus[$gpu_idx]}"
        gpu_idx=$((gpu_idx + 1))
        launched_instruct=$((launched_instruct + 1))
    done

    echo ""
    echo "Launched $launched_embed embed + $launched_instruct instruct servers."
    echo "Servers take 30-120s to load models. Use './serve.sh status' to check."
    if [ "$launched_embed" -lt "$need_embed" ] || [ "$launched_instruct" -lt "$need_instruct" ]; then
        echo "WARNING: Could not launch all requested servers (not enough free GPUs)."
    fi
}

cmd_down() {
    local stop_embed=false
    local stop_instruct=false

    if [ $# -eq 0 ]; then
        echo "Usage: $0 down [--embed] [--instruct] [--all]"
        return
    fi

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --embed)    stop_embed=true; shift ;;
            --instruct) stop_instruct=true; shift ;;
            --all)      stop_embed=true; stop_instruct=true; shift ;;
            *) echo "Unknown option: $1"; exit 1 ;;
        esac
    done

    # SAFETY: Only kills current user's processes (find_my_servers, not find_all_servers)
    find_my_servers | while read -r pid port gpu type model user; do
        if { [ "$type" = "embed" ] && $stop_embed; } || \
           { [ "$type" = "instruct" ] && $stop_instruct; }; then
            echo "  Stopping $type server PID $pid (port $port, GPU $gpu) ..."
            kill "$pid" 2>/dev/null || true
        fi
    done

    echo "Done. Processes may take a few seconds to exit."
}

cmd_logs() {
    local port="${1:-}"
    if [ -z "$port" ]; then
        echo "Usage: $0 logs <port>"
        echo ""
        echo "Available logs:"
        ls -1t "$LOG_DIR"/*.log 2>/dev/null | head -10 | while read -r f; do
            echo "  $(basename "$f")"
        done
        return
    fi

    local logfile
    logfile=$(ls -1t "$LOG_DIR"/*port${port}.log 2>/dev/null | head -1)
    if [ -z "$logfile" ]; then
        echo "No log file found for port $port"
        return
    fi
    echo "Tailing $logfile (Ctrl-C to stop)"
    tail -f "$logfile"
}

# --- Main --------------------------------------------------------------------

cmd="${1:-status}"
shift || true

case "$cmd" in
    status) cmd_status ;;
    up)     cmd_up "$@" ;;
    down)   cmd_down "$@" ;;
    logs)   cmd_logs "$@" ;;
    *)
        echo "Usage: $0 {status|up|down|logs}"
        echo ""
        echo "  status                          Show running servers and GPU status"
        echo "  up --embed N --instruct N       Launch servers to reach target counts"
        echo "  down --embed|--instruct|--all   Stop servers"
        echo "  logs <port>                     Tail logs for a server on that port"
        echo ""
        echo "Environment overrides:"
        echo "  EMBED_MODEL       (default: $EMBED_MODEL)"
        echo "  INSTRUCT_MODEL    (default: $INSTRUCT_MODEL)"
        echo "  HF_HOME           (default: /raid/lingo/zachwoj/huggingface)"
        exit 1
        ;;
esac
