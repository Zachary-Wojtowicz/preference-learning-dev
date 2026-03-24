# preference-learning-dev

[uv](https://github.com/astral-sh/uv)

`uv sync`



## ORCD Commands
**on login node**
ssh -N -L 8000:127.0.0.1:8000 ayushn@nodeXXXX

**on gpu node**
python -m vllm.entrypoints.openai.api_server \
  --model "Qwen/Qwen2.5-7B-Instruct" \
  --dtype bfloat16 \
  --gpu-memory-utilization 0.90 \
  --max-model-len 2048 \
  --enable-prefix-caching \
  --max-num-seqs 256 \
  --max-num-batched-tokens 65536 \
  --port 8000
  

**on local machine**
ssh -N -L 8000:127.0.0.1:8000 ayushn@orcd-login001.mit.edu
