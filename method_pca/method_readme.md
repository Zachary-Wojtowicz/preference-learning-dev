# PCA Method

`method_pca/pipeline.py` builds embedding deltas, runs PCA on those deltas, keeps
enough components to explain `99.99%` of the variance by default, then surfaces
the highest-scoring positive and negative examples for each retained direction.
If you pass a chat model, it also sends those examples to an OpenAI-compatible
endpoint such as `http://localhost:8000/v1` to explain each axis.

For wine, the relevant mode is `centered_rows`: compute the global mean embedding,
subtract it from every wine-review embedding, and run PCA on those centered row
vectors.

## Default setup

The default configuration is aimed at `datasets/writing_embedded.parquet`:

- rows are grouped by `style_name`
- a centroid is computed for each group
- PCA is run on all pairwise centroid deltas
- original row texts are projected onto each retained PCA direction
- top positive and negative sentences are written to the output report
- only the leading components are sent to the chat model and markdown summary by default

## Run

Without LLM explanations:

```bash
./.codex-venv/bin/python method_pca/pipeline.py \
  --input-parquet datasets/writing_embedded.parquet \
  --output-dir method_pca/outputs/writing \
  --group-column style_name \
  --label-column style_name \
  --text-column text \
  --delta-mode group_centroids \
  --variance-threshold 0.9999 \
  --skip-llm
```

With local chat explanations:

```bash
method_pca/run_writing_pca.sh http://localhost:8000/v1 Qwen/Qwen2.5-7B-Instruct dummy
```

Wine run:

```bash
method_pca/run_wine_pca.sh http://localhost:8000/v1 Qwen/Qwen2.5-7B-Instruct dummy
```

## Outputs

The pipeline writes:

- `method_pca/outputs/<name>/pca_report.json`
- `method_pca/outputs/<name>/summary.md`

## Useful files

- `embed/server/server.py`: local embedding server in this repo
- `README.md`: notes for a local `vllm` chat endpoint on port `8000`
