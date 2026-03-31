# LLM-Generated Feature Method (Fork)

This folder implements Method 2 from the project spec, with several enhancements
over the original `method_llm_gen`:

1. Ask an LLM to generate interpretable preference dimensions for a domain.
2. Score options on those dimensions with either:
   - Variant 1: direct per-option scalar judgments on a **0–5 integer scale**
   - Variant 2: pairwise judgments with **swap-test debiasing** followed by Bradley-Terry estimation
3. Write machine-readable outputs and a compact markdown summary including
   **cross-variant consistency diagnostics** (Spearman rho / Kendall tau).

## What changed from `method_llm_gen`

- **Swap-test debiasing**: Each pairwise comparison is evaluated twice with options
  swapped. Only pairs where the LLM gives the same winner both times are kept;
  inconsistent pairs are discarded before BT fitting.
- **Reasoning-before-score**: The direct scoring prompt now asks the LLM to generate
  a justification *before* the numeric score, improving alignment.
- **0–5 integer scale**: Direct scores use integers 0–5 instead of {-1, -0.5, 0, 0.5, 1}.
  All six levels have concrete behavioral anchors. Scores are normalized to [-1, 1]
  internally for comparison with BT scores.
- **Expanded scale anchors**: Every level (0 through 5) now has a detailed description
  in the scoring prompt so the LLM has a stable reference frame.
- **Increased pairwise coverage**: Default `pair_appearances_per_option` raised from
  20 to 30 for tighter BT estimates.
- **`--api-provider` flag**: Convenience flag for routing judge calls through OpenAI
  or Anthropic APIs without manually specifying base URLs.
- **Cross-variant consistency check**: The summary now includes Spearman rho and
  Kendall tau between direct scores and BT scores per dimension, flagging dimensions
  with tau < 0.3 as potentially unreliable.

## Main entry point

```bash
python3 method_llm_gen_fork/pipeline.py --help
```

## Usage examples

### Local vLLM endpoint

```bash
python3 method_llm_gen_fork/pipeline.py run-all \
  --config method_llm_gen_fork/configs/wines.json \
  --base-url http://localhost:8000/v1 \
  --model Qwen/Qwen2.5-7B-Instruct \
  --api-key token-abc123
```

### OpenAI

```bash
python3 method_llm_gen_fork/pipeline.py run-all \
  --config method_llm_gen_fork/configs/wines.json \
  --api-provider openai \
  --model gpt-4o-mini \
  --api-key "$OPENAI_API_KEY"
```

The `--api-provider openai` flag sets the base URL to `https://api.openai.com/v1`
automatically. You can also omit `--api-key` if the `OPENAI_API_KEY` environment
variable is set.

### Anthropic

```bash
python3 method_llm_gen_fork/pipeline.py run-all \
  --config method_llm_gen_fork/configs/wines.json \
  --api-provider anthropic \
  --model claude-sonnet-4-20250514 \
  --api-key "$ANTHROPIC_API_KEY"
```

Uses `https://api.anthropic.com/v1` as the base URL. Falls back to the
`ANTHROPIC_API_KEY` environment variable if `--api-key` is not provided.

### Standalone consistency check

If you already have `direct_scores.csv` and `bt_scores.csv` from a previous run,
you can regenerate the summary with consistency diagnostics without re-running the
full pipeline:

```bash
python3 method_llm_gen_fork/pipeline.py consistency-check \
  --config method_llm_gen_fork/configs/wines.json \
  --output-dir method_llm_gen_fork/outputs/wines
```

## Scoring scale

Direct scores use a 6-point integer scale:

| Score | Meaning |
| ----: | ------- |
| 0 | Strongly and unambiguously at the low pole |
| 1 | Clearly at the low pole but not extreme |
| 2 | Leans toward the low pole with caveats |
| 3 | Leans toward the high pole with caveats |
| 4 | Clearly at the high pole but not extreme |
| 5 | Strongly and unambiguously at the high pole |

For comparison with BT scores (which are normalized to [-1, 1]), direct scores are
mapped via `(score - 2.5) / 2.5`.

## Files produced

- `dimensions.json`: generated preference dimensions
- `direct_scores.csv`: Variant 1 per-option scores (0–5 scale)
- `pairwise_judgments.csv`: Variant 2 comparison data (includes `swap_consistent` column)
- `bt_scores.csv`: Bradley-Terry estimated scores (fitted on consistent pairs only)
- `summary.md`: human-readable examples, top/bottom options, and cross-variant
  consistency diagnostics per dimension

## Input requirements

- A CSV or parquet file containing one row per option
- Preferably one text column describing the option in natural language
- Optional display column for cleaner summaries
- If no text column is configured or it is empty, the pipeline builds a description
  from the remaining row fields and automatically excludes `embedding`-type columns

## Description templates

- Add `template_path` in a domain config to point at a `.txt` file with placeholders
  like `{title}` or `{VALUE}`.
- Placeholder replacement is case-insensitive and skips `embedding`-type fields
  automatically.
- `datasets/wine_prompt.txt` is included as a concrete wine template.

---

## Compute setup: local vLLM on this server

This section documents the GPU infrastructure used for local model serving and
how to reproduce it.

### Hardware

The server has **8x NVIDIA A100-SXM4-80GB** GPUs (640 GB total). At the time of
setup (March 2026), GPUs 0–3 were free and GPUs 4–7 were partially occupied by
another user's Ray workers (~8 GB each).

```
nvidia-smi   # verify GPU availability
```

### Model: Qwen/Qwen2.5-32B-Instruct

- **Source:** [huggingface.co/Qwen/Qwen2.5-32B-Instruct](https://huggingface.co/Qwen/Qwen2.5-32B-Instruct)
- **Size:** ~62 GB in BF16 (fits on a single A100-80GB)
- **License:** Apache 2.0 (ungated, no access request needed)
- **Why this model:** Qwen 2.5 32B-Instruct is the largest ungated open-source
  instruction-tuned model that fits on a single A100-80GB in full BF16 precision.
  It produces strong structured JSON output, which is critical for the scoring and
  judging prompts. The 72B variant requires tensor parallelism across 2 GPUs, which
  hit flashinfer initialization issues in vLLM 0.18; the 32B avoids this entirely.

### Software installation

vLLM was installed into an existing conda environment (`ml`, Python 3.11).
The install pulls in CUDA-compatible PyTorch automatically.

```bash
# Conda env lives at /raid/lingo/zachwoj/miniconda3/envs/ml
PIP_CACHE_DIR=/raid/lingo/zachwoj/.cache/pip \
  /raid/lingo/zachwoj/miniconda3/envs/ml/bin/pip install vllm
```

Key versions installed: vLLM 0.18.0, PyTorch 2.10.0+cu128, transformers 4.57.6.

### HuggingFace token

A HuggingFace token is stored at `/raid/lingo/zachwoj/huggingface/token`. This is
used for downloading models. For ungated models like Qwen it is optional, but
required for gated models (e.g. Llama).

Model weights are cached at:
```
/raid/lingo/zachwoj/huggingface/hub/models--Qwen--Qwen2.5-32B-Instruct/
```

### Launching the vLLM server

The AFS home directory (`/afs/csail.mit.edu/u/z/zachwoj/`) is not writable, so
all cache directories must be redirected to `/raid`. The key environment variables:

```bash
nohup bash -c '\
  export HOME=/raid/lingo/zachwoj \
         XDG_CACHE_HOME=/raid/lingo/zachwoj/xdg-cache \
         HF_HOME=/raid/lingo/zachwoj/huggingface \
         HF_TOKEN=$(cat /raid/lingo/zachwoj/huggingface/token) \
         TORCH_HOME=/raid/lingo/zachwoj/xdg-cache/torch; \
  CUDA_VISIBLE_DEVICES=0 \
  /raid/lingo/zachwoj/miniconda3/envs/ml/bin/python3 \
    -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2.5-32B-Instruct \
    --port 8001 \
    --host 0.0.0.0 \
    --max-model-len 4096 \
    --dtype bfloat16 \
    --gpu-memory-utilization 0.92 \
' > /raid/lingo/zachwoj/work/vllm_server.log 2>&1 &

echo "Server PID: $!"
```

- First launch downloads the model (~62 GB), which takes ~10 minutes.
- Subsequent launches load from the HF cache in ~2 minutes.
- The server log is at `/raid/lingo/zachwoj/work/vllm_server.log`.

### Verifying the server

```bash
curl -s http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-32B-Instruct",
    "messages": [{"role": "user", "content": "Say hello in 5 words."}],
    "temperature": 0,
    "max_tokens": 30
  }' | python3 -m json.tool
```

### Running the pipeline against the local server

From the `method_llm_gen_fork` directory:

```bash
cd /raid/lingo/zachwoj/work/preference-learning-dev/method_llm_gen_fork

/raid/lingo/zachwoj/miniconda3/envs/ml/bin/python3 pipeline.py run-all \
  --config configs/movies.json \
  --base-url http://localhost:8001/v1 \
  --model Qwen/Qwen2.5-32B-Instruct \
  --api-key token-placeholder
```

Use the full path to the `ml` env's Python (`/raid/lingo/zachwoj/miniconda3/envs/ml/bin/python3`)
because `conda activate` fails on this server due to AFS home directory permissions.
The `--api-key` value is ignored by local vLLM but the pipeline requires it to be
non-empty.

### Multi-GPU parallelism (round-robin)

To increase throughput, launch multiple vLLM servers on separate GPUs and pass all
endpoints as a comma-separated `--base-url`. The pipeline distributes requests
across them in round-robin.

**1. Launch one server per free GPU:**

```bash
# Check which GPUs are free
nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv

# Launch servers (adjust CUDA_VISIBLE_DEVICES and ports for available GPUs)
for gpu in 0 1 2 3; do
  nohup bash -c "\
    export HOME=/raid/lingo/zachwoj \
           XDG_CACHE_HOME=/raid/lingo/zachwoj/xdg-cache \
           HF_HOME=/raid/lingo/zachwoj/huggingface \
           HF_TOKEN=\$(cat /raid/lingo/zachwoj/huggingface/token) \
           TORCH_HOME=/raid/lingo/zachwoj/xdg-cache/torch; \
    CUDA_VISIBLE_DEVICES=$gpu \
    /raid/lingo/zachwoj/miniconda3/envs/ml/bin/python3 \
      -m vllm.entrypoints.openai.api_server \
      --model Qwen/Qwen2.5-32B-Instruct \
      --port $((8001 + gpu)) \
      --host 0.0.0.0 \
      --max-model-len 4096 \
      --dtype bfloat16 \
      --gpu-memory-utilization 0.92 \
  " > /raid/lingo/zachwoj/work/vllm_server_gpu${gpu}.log 2>&1 &
  echo "GPU $gpu -> port $((8001 + gpu)), PID: $!"
done
```

Wait for all servers to be ready (check each log or `curl` each port).

**2. Run the pipeline with all endpoints:**

```bash
/raid/lingo/zachwoj/miniconda3/envs/ml/bin/python3 pipeline.py judge-pairs \
  --config configs/movies.json \
  --base-url http://localhost:8001/v1,http://localhost:8002/v1,http://localhost:8003/v1,http://localhost:8004/v1 \
  --model Qwen/Qwen2.5-32B-Instruct \
  --api-key token-placeholder \
  --appearances-per-option 50
```

The `--appearances-per-option N` flag controls how many pairwise comparisons each
option participates in per dimension (default: 30, from the config file). Higher
values produce more pairs and tighter BT estimates.

The pipeline prints `[client] Round-robin pool with N endpoints` on startup.
With 4 GPUs and `max_workers: 24`, the 24 worker threads are distributed evenly
across the 4 servers for roughly 4x the throughput of a single GPU.

### Incremental judge-pairs

The `judge-pairs` step is incremental: each run appends new pairwise judgments to
`pairwise_judgments.csv` rather than overwriting it. This means you can accumulate
more data over time to improve Bradley-Terry precision.

```bash
# First run -- generates initial pairs (50 appearances per option per dimension)
/raid/lingo/zachwoj/miniconda3/envs/ml/bin/python3 pipeline.py judge-pairs \
  --config configs/movies.json \
  --base-url http://localhost:8001/v1 \
  --model Qwen/Qwen2.5-32B-Instruct \
  --api-key token-placeholder \
  --appearances-per-option 50

# Fit BT on what we have so far
/raid/lingo/zachwoj/miniconda3/envs/ml/bin/python3 pipeline.py fit-bt \
  --config configs/movies.json

# Want more precision? Run judge-pairs again -- it appends new pairs
/raid/lingo/zachwoj/miniconda3/envs/ml/bin/python3 pipeline.py judge-pairs \
  --config configs/movies.json \
  --base-url http://localhost:8001/v1 \
  --model Qwen/Qwen2.5-32B-Instruct \
  --api-key token-placeholder \
  --appearances-per-option 50

# Re-fit BT on the larger accumulated dataset
/raid/lingo/zachwoj/miniconda3/envs/ml/bin/python3 pipeline.py fit-bt \
  --config configs/movies.json
```

Each run prints both per-run and cumulative stats:
```
[judge-pairs] This run: 1500 new pairs (1247 consistent, 83%)
[judge-pairs] Cumulative: 4500 total pairs (3891 consistent, 86%)
```

To start fresh, delete `outputs/<domain>/pairwise_judgments.csv`.

### Stopping the server(s)

```bash
kill <PID>          # PID printed at launch, or:
pkill -f "vllm.*Qwen2.5-32B"    # kills all vLLM servers for this model
```

### Troubleshooting

| Symptom | Cause | Fix |
| ------- | ----- | --- |
| `PermissionError: .cache/flashinfer` | AFS home not writable | Set `HOME=/raid/lingo/zachwoj` and `XDG_CACHE_HOME` as shown above |
| `PermissionError: .cache/vllm` | Same | Same |
| `Engine core initialization failed` (TP=2) | flashinfer distributed init bug in vLLM 0.18 | Use TP=1 with a model that fits on one GPU (32B), or wait for vLLM fix |
| `403 gated repo` | HF token lacks access | Accept the model license on huggingface.co, or use an ungated model |
| Server starts but OOMs | Model too large for single GPU | Lower `--gpu-memory-utilization`, reduce `--max-model-len`, or use a smaller model |
