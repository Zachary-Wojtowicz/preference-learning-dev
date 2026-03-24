# LLM-Generated Feature Method

This folder implements Method 2 from the project spec:

1. Ask an LLM to generate interpretable preference dimensions for a domain.
2. Score options on those dimensions with either:
   - Variant 1: direct per-option scalar judgments in `[-1, -0.5, 0, 0.5, 1]`
   - Variant 2: pairwise judgments followed by Bradley-Terry estimation
3. Write machine-readable outputs and a compact markdown summary for spot checks.

Main entry point:

```bash
python3 method_llm_gen/pipeline.py --help
```

Typical usage for one domain:

```bash
python3 method_llm_gen/pipeline.py run-all \
  --config method_llm_gen/configs/wines.json \
  --base-url <chat-capable-openai-compatible-endpoint> \
  --model gpt-4.1-mini \
  --api-key "$OPENAI_API_KEY"
```

Wine parquet setup:

- `method_llm_gen/configs/wines.json` is configured to read `datasets/wine-130k_embedded.parquet`.
- The wine config uses `datasets/wine_prompt.txt` to build consistent option descriptions.
- The local endpoint at `http://localhost:8000/v1` in this repo is embeddings-only; Method 2 requires a chat-completions endpoint for dimension generation and judging.
- For fast iteration, use `method_llm_gen/configs/wines_smoke.json` (`max_options=40`) and run `method_llm_gen/run_wines_method2.sh`.

Expected outputs per domain go under:

```text
method_llm_gen/outputs/<domain>/
```

Files produced:

- `dimensions.json`: generated preference dimensions
- `direct_scores.csv`: Variant 1 per-option scores
- `pairwise_judgments.csv`: Variant 2 comparison data
- `bt_scores.csv`: Bradley-Terry estimated scores
- `summary.md`: human-readable examples and top/bottom options per dimension

Input requirements:

- A CSV or parquet file containing one row per option
- Preferably one text column describing the option in natural language
- Optional display column for cleaner summaries
- If no text column is configured or it is empty, the pipeline builds a description from the remaining row fields and automatically excludes `embedding`-type columns

Config files for wines, movies, and morals are included as templates in `method_llm_gen/configs/`.

Description templates:

- Add `template_path` in a domain config to point at a `.txt` file with placeholders like `{title}` or `{VALUE}`.
- Placeholder replacement is case-insensitive and skips `embedding`-type fields automatically.
- `datasets/wine_prompt.txt` is included as a concrete wine template.
