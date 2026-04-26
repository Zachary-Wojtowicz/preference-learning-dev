## Work dir

```
/raid/lingo/zachwoj/work/
```

## Huggingface Models

```
export HF_HOME=/raid/lingo/zachwoj/huggingface
```

## Check available GPUs

```
nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader
```

## Managing GPUs

**Get status**

```
./serve.sh status
```

**Launch servers**

```
# 1 embed server + 2 instruct servers
./serve.sh up --embed 1 --instruct 2
```

**Stop servers**

```
./serve.sh down --embed          # stop just embed servers
./serve.sh down --instruct       # stop just instruct servers
./serve.sh down --all            # stop everything
```

**Check logs**

```
./serve.sh logs 8004             # tail the log for the server on port 8004
./serve.sh logs                  # list available log files
```

**Override default models**

```
INSTRUCT_MODEL=Qwen/Qwen2.5-32B-Instruct ./serve.sh up --instruct 1
```

---

## Embed choice options

```
python embed/embedder/embed_csv.py \
  --base-url http://localhost:8003/v1 \
  --model Qwen/Qwen3-Embedding-8B \
  --api-key dummy \
  --input-csv datasets/movielens-32m-enriched.csv \
  --template-file datasets/movie_prompt.txt \
  --output datasets/movielens-32m-enriched-qwen3emb-embedded.parquet
```

## Select diverse choice options

```
python datasets/select_options.py \
  --input datasets/movielens-32m-enriched-qwen3emb-embedded.parquet \
  --id-column movie_id \
  --num-options 100 \
  --aux-csv datasets/movielens-rating-counts.csv \
  --aux-join-column movieId \
  --filter "rating_count >= 1000" \
  --output-dir datasets/movies_100
```

## Generate and winnow dimensions

```
python method_llm_examples/pipeline.py \
  --config method_llm_examples/configs/movies_100.json \
  --base-url "$(python discover_servers.py --type instruct -q)" \
  --model Qwen/Qwen3-32B \
  --api-key dummy \
  --embeddings-parquet datasets/movies_100/movielens-32m-enriched-qwen3emb-100-embedded.parquet \
  --embedding-base-url "$(python discover_servers.py --type embed -q)" \
  --embedding-model Qwen/Qwen3-Embedding-8B \
  --embedding-column embedding \
  --output-dir method_llm_examples/outputs/movies_100 \
  --dedup-method llm \
  --num-pairs 100 \
  --num-themes 50 \
  --num-dimensions 25 \
  --reasons-per-side 5 \
  --max-workers 32 \
  --seed 42
```

## Generate dimensions

```
mkdir -p method_llm_gen/outputs/movies_100
cp method_llm_examples/outputs/movies_100/dimensions.json \
   method_llm_gen/outputs/movies_100/dimensions.json

python method_llm_gen/pipeline.py run-all \
  --config method_llm_gen/configs/movies_100.json \
  --base-url "$(python discover_servers.py --type instruct -q)" \
  --model Qwen/Qwen3-32B \
  --api-key dummy \
  --output-dir method_llm_gen/outputs/movies_100 \
  --seed 42
```

## Find direction vectors

```
python method_directions/find_directions.py \
  --embeddings-parquet datasets/movies_100/movielens-32m-enriched-qwen3emb-100-embedded.parquet \
  --bt-scores method_llm_gen/outputs/movies_100/bt_scores.csv \
  --embedding-column embedding \
  --option-id-column movie_id \
  --output-dir method_directions/outputs/movies_100 \
  --seed 42
```

## Evaluate basis

```
python method_directions/evaluate_basis.py --scree \
  --embeddings-parquet datasets/movies_100/movielens-32m-enriched-qwen3emb-100-embedded.parquet \
  --embedding-column embedding \
  --output-dir method_directions/outputs/movies_100

python method_directions/evaluate_basis.py \
  --embeddings-parquet datasets/movies_100/movielens-32m-enriched-qwen3emb-100-embedded.parquet \
  --directions method_directions/outputs/movies_100/directions.npz \
  --bt-scores method_llm_gen/outputs/movies_100/bt_scores.csv \
  --embedding-column embedding \
  --output-dir method_directions/outputs/movies_100
```

## Precompute for experiment

```
python simulation/run_simulation.py \
  --embeddings-parquet datasets/movies_100/movies_100-embedded.parquet \
  --bt-scores method_llm_gen/outputs/movies_100/bt_scores.csv \
  --directions method_directions/outputs/movies_100/directions.npz \
  --output-dir simulation/outputs/movies_100 \
  --option-id-column movie_id \
  --num-users 50 \
  --num-trials 100 \
  --num-test-pairs 200 \
  --beta 2.0 \
  --slider-noise 0.2 \
  --learning-rate 0.01 \
  --projection-lambda 0.5 \
  --seed 42
```

## Simulations

```
python simulation/run_simulation.py \
  --embeddings-parquet datasets/movies_100/movies_100-embedded.parquet \
  --bt-scores method_llm_gen/outputs/movies_100/bt_scores.csv \
  --directions method_directions/outputs/movies_100/directions.npz \
  --output-dir simulation/outputs/movies_100 \
  --option-id-column movie_id \
  --num-users 50 \
  --num-trials 100 \
  --num-test-pairs 200 \
  --beta 2.0 \
  --slider-noise 0.2 \
  --learning-rate 0.01 \
  --projection-lambda 0.5 \
  --seed 42

# Discover the instruct server URL first
INSTRUCT_URL=$(python discover_servers.py --type instruct -q)

python simulation/run_llm_simulation.py \
  --embeddings-parquet datasets/movies_100/movies_100-embedded.parquet \
  --bt-scores method_llm_gen/outputs/movies_100/bt_scores.csv \
  --dimensions method_llm_gen/outputs/movies_100/dimensions.json \
  --directions method_directions/outputs/movies_100/directions.npz \
  --option-descriptions datasets/movies_100/movies_100.csv \
  --option-template datasets/movie_prompt.txt \
  --option-id-column movie_id \
  --output-dir simulation/outputs/movies_100_llm \
  --base-url "$INSTRUCT_URL" \
  --api-key dummy \
  --persona-model Qwen/Qwen3-32B \
  --choice-model Qwen/Qwen3-32B \
  --num-personas 20 \
  --num-trials 50 \
  --num-test-pairs 50 \
  --learning-rate 0.01 \
  --projection-lambda 0.5 \
  --max-workers 4 \
  --seed 42
```

---

## New end-to-end

```
# 1. Download and prepare the full dataset (~10,000 actions)
python datasets/prepare_scruples.py

# 2. Run the entire pipeline
./run_pipeline.sh configs/scruples_200.yaml
```

---

## 

```
python3 -m http.server 8080

http://localhost:8080
```