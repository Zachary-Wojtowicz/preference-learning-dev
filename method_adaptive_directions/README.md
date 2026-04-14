# Adaptive Pairwise Dimension Discovery

This experiment discovers and updates 10 preference dimensions while collecting pairwise LLM judgments.

Loop:
1. Sample 500 wines from `datasets/wine-130k_embedded.parquet`.
2. Sample 50 from that subset and generate 10 initial dimensions.
3. Judge random pairs, marking which dimensions were actually useful.
4. Collect missed differences (labels not covered by current dimensions).
5. Every 20 judgments, merge overrepresented missed labels into candidates and swap out low performers.

## Run

```bash
.venv/bin/python method_adaptive_directions/pipeline.py \
  --config method_adaptive_directions/configs/wines_500_adaptive.json \
  --provider nvidia \
  --model meta/llama-3.3-70b-instruct \
  --subset-size 500 \
  --seed-sample-size 50 \
  --n-dimensions 10 \
  --judgments-total 120 \
  --switch-interval 20 \
  --max-swaps-per-interval 2 \
  --rate-limit-per-minute 40
```

At 40 requests/min and 20 judgments per swap cycle, this yields roughly 2 swap cycles per minute.

## Outputs

Each run writes to `method_adaptive_directions/outputs/<timestamp>/`:

- `initial_dimensions.json`
- `judgments.csv`
- `dimension_performance.csv`
- `missed_labels.csv`
- `switch_log.csv`
- `merge_candidates_after_<j>.json`
- `active_dimensions_after_<j>.json`
- `summary.md`
