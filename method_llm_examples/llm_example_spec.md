# Choice-Grounded Dimension Discovery

## Motivation

The existing dimension generation approach (`method_llm_gen/`) prompts an LLM to brainstorm preference dimensions abstractly for a domain. This produces sensible but generic dimensions (e.g., "Action Intensity," "Emotional Depth") that tend to be objective feature descriptors rather than genuine axes of preference disagreement. The core problem: the LLM falls back on textbook categories because it isn't grounded in actual choices.

This method replaces the abstract brainstorm with a bottom-up pipeline: sample concrete pairwise contrasts from the dataset, elicit *reasons someone might choose one over the other*, accumulate a large pool of reasons, then distill them into a compact set of dimensions. This surfaces preference-relevant contrasts that the abstract approach misses — including subtle, implicit, or domain-specific axes that only become apparent when comparing specific options.

## Pipeline Overview

```
[Sample diverse pairs] → [Elicit reasons per pair] → [Embed & cluster reasons]
    → [Condense into dimensions] → [Validate coverage]
```

The output is a `dimensions.json` in the **exact same schema** as `method_llm_gen/outputs/*/dimensions.json`, so downstream stages (scoring, BTL, direction-finding, simulation) work unchanged.

## Prerequisites

- A dataset of options with text descriptions (e.g., `datasets/movielens-32m-enriched-50.csv` + `datasets/movie_prompt.txt`)
- Embeddings for the options (e.g., `datasets/movielens-32m-enriched-50-embedded.parquet`) — used for stratified pair sampling
- Access to an OpenAI-compatible LLM API

## Stage 1 — Sample Diverse Pairs

**Goal:** Select ~100 option pairs that span the full range of similarity, so that both coarse-grained and fine-grained preference reasons are surfaced.

**Method:**
1. Load embeddings for all N options. Center them (subtract mean).
2. Compute all pairwise cosine distances (N×N). For N=50 this is 1,225 pairs; for N=200, subsample.
3. Divide pairs into three strata by distance: near (bottom third), medium (middle third), far (top third).
4. Sample ~33 pairs from each stratum, for ~100 total. Use a seed for reproducibility.

**Rationale:** Uniform random sampling overrepresents "easy" pairs (action movie vs. romance) where the reasons are obvious and redundant. Near pairs force the LLM to articulate subtle distinctions ("both are thrillers, but one has a morally ambiguous protagonist while the other has a clear hero"). Far pairs capture the broad strokes. Medium pairs fill the gap.

**Output:** `sampled_pairs.json` — a list of `{pair_id, option_a_id, option_b_id, distance_stratum, cosine_distance}`.

**CLI args:**
- `--num-pairs` (default 100)
- `--strata` (default 3)

## Stage 2 — Elicit Reasons Per Pair

**Goal:** For each pair, generate 10 reasons (5 for choosing A, 5 for choosing B) that reflect genuine preference differences.

**Prompt:**

```
Here are two {domain_items}. Imagine a large, diverse group of people each
choosing which one they prefer. Different people will choose differently —
and for different reasons.

{DOMAIN_ITEM} A:
{option_a_text}

{DOMAIN_ITEM} B:
{option_b_text}

List 5 distinct reasons someone might choose {DOMAIN_ITEM} A over B, and
5 distinct reasons someone might choose B over A. Each reason should reflect
a genuine preference difference — something some people would care about and
others wouldn't, or something different people would weigh in opposite
directions.

Be specific and concrete. Avoid generic quality judgments ("it's better").
Focus on *what kind of person* would have this reason, and *what feature
of the option* drives it.

Format (plain text, not JSON):

REASONS TO CHOOSE A:
1. [reason]
2. [reason]
3. [reason]
4. [reason]
5. [reason]

REASONS TO CHOOSE B:
1. [reason]
2. [reason]
3. [reason]
4. [reason]
5. [reason]
```

**Implementation details:**
- One LLM call per pair (not two — keeping both options in view produces more contrastive, non-redundant reasons).
- Use the full rendered option text from the template (same text that was embedded and scored in `method_llm_gen`). Reuse the `build_option_text()` / `render_row_template()` logic from `method_llm_gen/pipeline.py`.
- Parse the response by splitting on "REASONS TO CHOOSE A:" and "REASONS TO CHOOSE B:", then extracting numbered lines.
- Tag each reason with its pair_id, direction (A or B), and the option IDs.
- Parallelize with `max_workers` (same pattern as `method_llm_gen/pipeline.py`'s `run_jobs` function).
- Use `temperature=0.7` — some creativity is desirable here; we want diverse reasons, not the single most likely one.

**Output:** `raw_reasons.json` — a list of `{reason_id, pair_id, direction, option_a_id, option_b_id, reason_text}`. Expect ~1,000 entries from 100 pairs.

**CLI args:**
- `--reasons-per-side` (default 5)
- `--max-workers` (default 8)

## Stage 3 — Embed and Cluster Reasons

**Goal:** Deduplicate the ~1,000 raw reasons into ~50–80 clusters of semantically similar reasons, each represented by its most central member.

**Method:**
1. Embed all reason strings using the same embedding endpoint used for option embeddings. (Or, if a different model is more appropriate for short text, allow `--reason-embedding-model` override.)
2. Normalize embeddings to unit length.
3. Run agglomerative clustering with cosine distance and average linkage. Use a distance threshold to target ~50–80 clusters — or accept `--num-clusters` as an override.
4. For each cluster:
   - Select the reason closest to the cluster centroid (by cosine distance) as the **representative**.
   - Record the cluster size (number of reasons it subsumes).
   - Record which pairs contributed reasons to this cluster.

**Rationale:** Dumping 1,000 reasons into a single LLM context window would exceed limits for most models and produce poor condensation. Embedding-based clustering is fast, requires no LLM calls, and produces a principled deduplication. The cluster sizes also provide empirical evidence for which themes are most recurrent — a signal that should be preserved into Stage 4.

**Output:** `reason_clusters.json` — a list of `{cluster_id, representative_reason, cluster_size, member_reason_ids, contributing_pair_ids}`, sorted by cluster_size descending.

**CLI args:**
- `--num-clusters` (default: let the algorithm decide via distance threshold)
- `--cluster-distance-threshold` (default 0.3)

## Stage 4 — Condense into Dimensions

**Goal:** Distill the ~50–80 cluster representatives into K bipolar preference dimensions (default K=10).

**Prompt:**

```
You are analyzing reasons people give for choosing between {domain_items}.

Below is a deduplicated list of reasons people cited for preferring one option
over another. The number in parentheses indicates how many times this theme
appeared across {num_pairs} different choice pairs — higher counts indicate
more pervasive preference axes.

Many of these reasons are two sides of the same underlying preference dimension.
Your task is to identify the {K} most important underlying preference dimensions
that explain these reasons.

Each dimension should:
- Be a BIPOLAR AXIS — both ends represent legitimate preferences that real
  people hold (not a quality scale where one end is objectively better)
- SUBSUME as many of the listed reasons as possible
- Be DISTINCT from the other dimensions you identify
- Reflect genuine DISAGREEMENT — something that different people weigh
  in opposite directions, not a universal quality criterion

For each dimension, cite which reason numbers it subsumes (this verifies
coverage and coherence).

REASONS (sorted by frequency):
{numbered list: "N. [count=X] reason_text"}

Respond with valid JSON only — no prose before or after, no markdown fences.

{
  "domain": string,
  "choice_context": string,
  "reasoning": string,
  "dimensions": [
    {
      "id": integer,
      "name": string,
      "low_pole": {
        "label": string,
        "description": string,
        "typical_person": string
      },
      "high_pole": {
        "label": string,
        "description": string,
        "typical_person": string
      },
      "example_contrast": {
        "low_option": string,
        "high_option": string
      },
      "articulability": "explicit" | "partially_explicit" | "implicit",
      "estimated_variance": "mostly_between_person" | "mostly_between_option" | "both",
      "scoring_guidance": string,
      "subsumed_reasons": [integer]
    }
  ],
  "redundancy_check": [
    {
      "dimension_ids": [integer, integer],
      "correlation_note": string,
      "disentanglement_suggestion": string
    }
  ]
}
```

**Key differences from the existing `llm_pref_gen.txt` prompt:**
- The LLM is grounded in **empirical evidence** (the clustered reasons) rather than brainstorming from scratch.
- Cluster counts provide **frequency weighting** — the LLM can see which themes recurred across many pairs vs. appearing only once.
- The `subsumed_reasons` field creates an **auditable link** between input evidence and output dimensions.
- The output schema is otherwise identical to the existing one, so all downstream code works unchanged.

**Implementation:**
- Use the JSON output path (not plain text). If the model struggles, fall back to the plain-text `===DIMENSION===` format from `method_llm_gen/pipeline.py`'s `build_plain_dimension_prompt` / `parse_plain_dimensions` functions.
- Use `temperature=0` for this step — we want the single best condensation, not creative variation.

**Output:** `dimensions.json` — same schema as `method_llm_gen/outputs/*/dimensions.json` with an additional `subsumed_reasons` field per dimension.

**CLI args:**
- `--num-dimensions` / `-K` (default 10)

## Stage 5 — Validate Coverage

**Goal:** Check that the K dimensions collectively account for the reasons in the pool, and flag any important orphan themes.

**Method:**
1. For each of the ~1,000 raw reasons, compute cosine similarity between its embedding and the embedding of each dimension's `low_pole.description` and `high_pole.description`.
2. Assign each reason to its best-matching dimension (highest similarity to either pole).
3. Report:
   - **Coverage rate**: fraction of reasons whose best-match similarity exceeds a threshold (e.g., 0.4).
   - **Orphan reasons**: reasons below the threshold — these may indicate missing dimensions. Show the top 10 orphans sorted by how frequently their cluster appeared.
   - **Dimension load**: how many reasons each dimension absorbs. Very uneven loads suggest one dimension is doing too much work (and should perhaps be split) or another is too niche.
   - **Pole alignment**: for each dimension, what fraction of its assigned reasons align with the high vs. low pole (a sanity check that both poles are populated).

**Output:** `coverage_report.json` and `coverage_report.md`.

## After This Pipeline

The `dimensions.json` output slots directly into the existing `method_llm_gen` pipeline for scoring:

```bash
# Score options on the new dimensions using the existing pipeline
python method_llm_gen/pipeline.py score-options \
  --config method_llm_gen/configs/movies_50.json \
  --base-url ... --model ... --api-key ... \
  --output-dir method_llm_examples/outputs/movies_50

# Copy dimensions.json into the output dir first
cp method_llm_examples/outputs/movies_50/dimensions.json \
   method_llm_gen/outputs/movies_50_example_dims/dimensions.json

# Then run scoring, pairwise judging, and BTL fitting
python method_llm_gen/pipeline.py run-all \
  --config method_llm_gen/configs/movies_50.json \
  --output-dir method_llm_gen/outputs/movies_50_example_dims \
  ...
```

Or, for a self-contained experience, this pipeline could include its own scoring stages — but reusing `method_llm_gen/pipeline.py`'s `score-options`, `judge-pairs`, and `fit-bt` subcommands avoids code duplication.

## CLI Interface

```bash
python method_llm_examples/pipeline.py \
  --config method_llm_examples/configs/movies_50.json \
  --base-url https://api.openai.com/v1 \
  --model gpt-4o-mini \
  --api-key "$OPENAI_API_KEY" \
  --embeddings-parquet datasets/movielens-32m-enriched-50-embedded.parquet \
  --embedding-column embedding \
  --output-dir method_llm_examples/outputs/movies_50 \
  --num-pairs 100 \
  --num-dimensions 10 \
  --num-clusters 60 \
  --reasons-per-side 5 \
  --max-workers 8 \
  --seed 42
```

The config file follows the same schema as `method_llm_gen/configs/*.json`:

```json
{
  "domain": "movies",
  "domain_item": "movie",
  "choice_context": "A person is deciding which movie to watch based on its description, genre, cast, and plot summary.",
  "input_path": "datasets/movielens-32m-enriched-50.csv",
  "template_path": "datasets/movie_prompt.txt",
  "text_column": "plot_summary",
  "display_column": "title",
  "id_column": "movie_id",
  "max_options": 50
}
```

The `domain_item` field (e.g., "movie", "wine") is new and used to make prompts domain-appropriate ("Here are two movies..." vs. "Here are two wines...").

## Outputs

All written to `method_llm_examples/outputs/<run_name>/`:

| File | Stage | Description |
|------|-------|-------------|
| `sampled_pairs.json` | 1 | The ~100 pairs with distance strata |
| `raw_reasons.json` | 2 | All ~1,000 elicited reasons with pair/direction metadata |
| `reason_clusters.json` | 3 | Clustered reasons with representatives and counts |
| `dimensions.json` | 4 | Final dimensions (**same schema as `method_llm_gen`**) |
| `coverage_report.json` | 5 | Coverage statistics |
| `coverage_report.md` | 5 | Human-readable coverage summary |
| `summary.md` | — | Overall pipeline summary: params, dimensions found, coverage stats, comparison to `method_llm_gen` dimensions if available |

## Dependencies

`numpy`, `pandas`, `scikit-learn` (for `AgglomerativeClustering`), `scipy`, `pyarrow`, `openai`. Same as the rest of the repo — no new libraries.

## Cost Estimate

- Stage 2: ~100 LLM calls (one per pair), ~500 input tokens + ~300 output tokens each ≈ 80K tokens total.
- Stage 4: 1 LLM call, ~3K input tokens.
- Stage 3 embedding: ~1,000 short strings ≈ 20K tokens.
- **Total: ~100K tokens ≈ $0.02 with gpt-4o-mini.**

This is an order of magnitude cheaper than the scoring/judging stages that follow.
