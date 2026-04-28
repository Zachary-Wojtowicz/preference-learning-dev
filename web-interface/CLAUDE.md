# CLAUDE.md — Preference Elicitation Experiment

## Overview

A web-based experiment for preference elicitation research. Participants make binary choices between options and provide feedback via one of several elicitation conditions (sliders, checkboxes, or natural-language preference inferences). The experiment is designed to be embedded in Qualtrics via iframe and communicates results back via postMessage.

## Files

```
web-interface/
├── index.html                # Single-file experiment app (HTML/CSS/JS, no dependencies)
├── generate_trials.py        # Script to produce trials.json from pipeline outputs
├── update_configs.py         # Script to update all experiment_config.json with latest conditions
├── CLAUDE.md                 # This file
└── outputs/                  # Per-domain trial data (loaded at runtime)
    ├── movies_100/
    │   ├── trials.json
    │   └── experiment_config.json
    ├── movies_50/
    ├── scruples_dilemmas/
    └── wines_100/
```

## Running Locally

```bash
cd web-interface/
python3 -m http.server 8080
# Open http://localhost:8080
# Defaults to movies_100 domain
```

## Hosted Version (GitHub Pages)

```
https://zachary-wojtowicz.github.io/preference-learning-dev/web-interface/index.html
```

The outputs/ directory must be committed to the repo for GitHub Pages to serve the trial data.

## URL Parameters

The interface accepts URL parameters to skip the setup screen (for Qualtrics integration or direct links):

| Param | Description | Example |
|-------|-------------|---------|
| `domain` | Which dataset to load from `outputs/<domain>/` | `movies_100` |
| `pid` | Participant ID (used for deterministic trial order) | `P001` |
| `condition` | Which elicitation condition | `inference_categories` |
| `n` | Number of feedback trials (default 20, from `num_trials_per_participant`) | `20` |
| `m` | Number of practice/training trials (default 5, from `num_training_trials`). Set to `0` to skip. | `5` |
| `post` | Optional POST endpoint for response data | `https://example.com/submit` |

When `pid` and `condition` are both provided, the setup screen is skipped entirely → instructions → trials.

**Example URLs:**
```
# Direct start with inference categories:
http://localhost:8080?domain=movies_100&pid=P001&condition=inference_categories&n=5

# Choice only baseline:
http://localhost:8080?domain=movies_100&pid=P002&condition=choice_only&n=30

# Setup screen (no params or only domain):
http://localhost:8080?domain=wines_100
```

If no `domain` is specified, defaults to `movies_100`.

## Experimental Conditions

Six between-subjects conditions are supported. The `show_inferences` field is either `false`, `'affirm'`, or `'categories'`.

| Condition Key | Label | Description |
|---------------|-------|-------------|
| `choice_only` | Choice Only | Binary choice, no feedback mechanism |
| `choice_readonly_sliders` | Read-Only Sliders | Top-5 dimension scores shown after choice (locked) |
| `choice_adjustable_sliders` | Adjustable Sliders | Top-5 sliders with Gram matrix co-movement |
| `choice_checkboxes` | Relevance Checkboxes | Top-5 dimensions as binary checkboxes |
| `inference_affirm` | Inferences: Affirm/Remove | Natural-language inferences with Remove / Moderate / Affirm buttons |
| `inference_categories` | Inferences: Category Selection | Natural-language inferences with 5-level category picker |

### Inference Conditions (detail)

Both inference conditions show 5 statements of the form **"You {category} {dimension}."** after each choice. The category is pre-selected based on the gradient projection magnitude.

**`inference_affirm`** shows three buttons per inference (left to right):
- **✕ Remove** — zeros out the gradient for this dimension (mult = 0)
- **↔ Moderate** — moves the category one step toward "Indifferent" (e.g., "love" → "like", "prefer to skip" → "aren't into"). Sentence updates live.
- **✓ Affirm** — confirms the inference; multiplier gets 1.5× boost

**`inference_categories`** shows 5 category buttons per inference, always visible with the model's guess pre-selected. Clicking a different category updates the sentence and multiplier:

| Category | Phrase | Multiplier |
|----------|--------|------------|
| Prefer to skip | "You prefer to skip {dim}" | -1.5 |
| Aren't into | "You aren't into {dim}" | -1.0 |
| Indifferent | "You are indifferent to {dim}" | 0.0 |
| Like | "You like {dim}" | 1.0 |
| Love | "You love {dim}" | 1.5 |

### Domain-Specific Categories

Categories are loaded from `experiment_config.json` → `inference_categories`. Different domains use different language. The defaults above are for movies/wines. Scruples (moral dilemmas) uses: Reject (-1.5) / Disapprove of (-1.0) / Indifferent (0.0) / Understand (1.0) / Endorse (1.5).

Run `python3 update_configs.py` from the web-interface/ directory to update all domain configs with the latest conditions and categories.

## Practice / Training Trials

Before the main feedback trials, participants complete `M` practice trials (default `M=5`, set via `num_training_trials` in `experiment_config.json` or the `m` URL param). Each practice trial:

1. Displays one preference dimension's full description: `name`, `low_label`, `high_label`, `scoring_guidance` (from `experiment_config.json` → `dimensions`).
2. Asks: *"Which option is more **{high_label}**?"*
3. Shows the trial pair from the dataset whose pair-projection on that dimension is maximally divergent (i.e., `argmax_t |value_if_a[k] - value_if_b[k]|`), so the correct answer is unambiguous.
4. On click, immediately reveals feedback: the correct option is highlighted in green; an incorrect pick is also outlined in red. A "Continue" button advances to the next practice trial.

The first `M` dimensions in `experiment_config.dimensions` (in file order) are used. Pairs selected for practice are excluded from the feedback pool, so a participant never sees the same pair twice. Practice responses are recorded in the output JSON under `training_responses`.

Set `m=0` in the URL to skip practice trials entirely.

## Instructions Screens

There are **two instruction screens**, both driven by `experiment_config.json` → `instructions`:

| Phase | Config key | When shown |
|-------|------------|------------|
| Practice | `instructions.training` | Before the practice trials (skipped if `M=0`) |
| Main task | `instructions.feedback` | Before the feedback trials (always shown) |

Both values are HTML strings — edit them directly in `outputs/<domain>/experiment_config.json` for per-domain wording. To change defaults globally, edit `DEFAULT_INSTRUCTIONS` in `update_configs.py` and re-run it (`python3 update_configs.py`). Defaults will only fill in missing keys; per-domain edits are preserved.

The `instructions.feedback` HTML is rendered, then a **condition-specific note** is auto-appended (the existing `inst-highlight` block that explains the feedback mechanism — sliders / checkboxes / inferences). After that, a "There are N trials" sentence is appended automatically. You don't need to write either of those into your custom HTML.

Fallbacks live in `index.html` as `DEFAULT_TRAINING_INSTRUCTIONS` / `DEFAULT_FEEDBACK_INSTRUCTIONS` constants if the config key is missing.

## Option Card Display

Option cards render structured fields from trial data. Several fields are hidden from display:

**Hidden fields** (internal/unreadable): `title`, `_rendered_text`, `movie_id`, `wine_id`, `action_id`, `completion_id`, `option_id`, `id`, `row_id`, `text`, `prompt_hash`, `category`, `embedding`, `rating_count`, `taster_twitter_handle`, `points`, `price`, `taster_name`

**Poster images**: If `option.poster_url` is set, an image is displayed at the top of each card (max-height 400px). Currently used for movies (via TMDB). Gracefully hidden if the URL fails to load.

## Qualtrics Integration

### Survey: SV_8iclgrFAgbt2LmC

**"Preference Learning Experiment — Prototype"**

#### Survey Flow (intended order — may need manual reorder in Qualtrics UI)

1. **Embedded Data** (FL_4) — sets defaults for condition, domain, num_trials, experiment_url, experiment_data
2. **Consent Block** (BL_dojFNE184hQQveS, QID1) — study description and consent text
3. **Prototype Config Block** (BL_6FEl4m6v9vOXAbQ, QID8+QID9) — multiple choice selectors for condition and domain that set embedded data via QuestionJS. **This block is for prototype testing only; remove for production.**
4. **Experiment Block** (BL_d6xAo6J50GtvdhI, QID2) — iframe embed with QuestionJS that captures postMessage
5. **Post-Experiment Block** (BL_0BQEGUyjbDHFcLY, QID3+QID4) — open-ended feedback questions

#### Embedded Data Fields

| Field | Default | Purpose |
|-------|---------|---------|
| `condition` | `inference_categories` | Experiment condition key |
| `domain` | `movies_100` | Dataset domain |
| `num_trials` | `30` | Number of trials per participant |
| `experiment_url` | `https://zachary-wojtowicz.github.io/preference-learning-dev/web-interface/index.html` | Base URL of hosted experiment |
| `experiment_data` | *(empty)* | JSON string of all responses, captured via postMessage |

All fields can be overridden via URL params: `?condition=inference_affirm&domain=wines_100`

#### iframe URL Construction

The experiment iframe src uses Qualtrics piped text:
```
${e://Field/experiment_url}?domain=${e://Field/domain}&pid=${e://Field/ResponseID}&condition=${e://Field/condition}&n=${e://Field/num_trials}
```

#### postMessage Communication

When the experiment finishes, `index.html` sends:
```javascript
window.parent.postMessage({
  type: 'experiment_complete',
  payload: { participant_id, condition, domain, num_trials, timestamp, responses }
}, '*');
```

The QuestionJS on QID2 catches this, stores `payload` as embedded data `experiment_data`, and auto-advances to the next page.

#### Prototype Config Questions (QID8, QID9)

These are MC questions with QuestionJS that set embedded data:

**QID8 — Condition selector** (block BL_6FEl4m6v9vOXAbQ):
- Choice 1: "Choice Only (baseline)" → sets `condition` = `choice_only`
- Choice 2: "Choice + Read-Only Sliders" → `choice_readonly_sliders`
- Choice 3: "Choice + Adjustable Sliders" → `choice_adjustable_sliders`
- Choice 4: "Choice + Checkboxes" → `choice_checkboxes`
- Choice 5: "Inferences: Affirm / Moderate / Remove" → `inference_affirm`
- Choice 6: "Inferences: Category Selection" → `inference_categories`

**QID9 — Domain selector** (same block):
- Choice 1: "Movies (100)" → sets `domain` = `movies_100`
- Choice 2: "Scruples — Moral Dilemmas" → `scruples_dilemmas`
- Choice 3: "Wines (100)" → `wines_100`

**For production**: Delete the Prototype Config block. Use Qualtrics Randomizer in the survey flow to assign conditions, or pass condition via URL param from an external recruitment system.

#### QuestionJS Notes

Qualtrics interprets `${` as piped text. In any QuestionJS code, use `\x24{` or `String.fromCharCode(36)+'{'` instead of template literals.

## Data Schema

### Input: trials.json

```json
[
  {
    "trial_id": "t1",
    "pair_index": 0,
    "option_a_id": "57532",
    "option_b_id": "5833",
    "distance_stratum": "near",
    "cosine_distance": 0.894,
    "prompt": "Which movie would you rather watch right now?",
    "option_a": {
      "label": "The Matrix (1999)",
      "fields": { "title": "The Matrix (1999)", "genres": "Action|Sci-Fi", ... },
      "poster_url": "https://image.tmdb.org/t/p/w300/...",
      "text": "fallback plain text (optional)"
    },
    "option_b": { ... },
    "sliders": [
      {
        "id": "dim_1",
        "dimension_id": 1,
        "label": "Action Intensity",
        "low_label": "Not Action-Oriented",
        "high_label": "Highly Action-Oriented",
        "value_if_a": 85,
        "value_if_b": -42
      },
      ...
    ],
    "dilemma_id": "...",
    "gold_label": 1,
    "controversial": false
  }
]
```

- `poster_url`: optional, only present for domains with images (movies)
- `dilemma_id`, `gold_label`, `controversial`: only present for scruples dilemma pairs
- `sliders`: array of all K dimensions with pre-computed projections. The interface shows the top-5 by |effective value| after the user makes a choice.
- `value_if_a` / `value_if_b`: the projection value used depending on which option the user chose

### Input: experiment_config.json

```json
{
  "domain": "movies",
  "choice_context": "Which movie would you rather watch right now?",
  "num_trials_per_participant": 20,
  "num_training_trials": 5,
  "top_k_sliders": 5,
  "conditions": { ... },
  "default_condition": "inference_categories",
  "gram_matrix": [[...], ...],
  "inference_categories": [
    {"key": "skip", "phrase": "prefer to skip", "label": "Prefer to skip", "mult": -1.5},
    {"key": "not_into", "phrase": "aren't into", "label": "Aren't into", "mult": -1.0},
    {"key": "indifferent", "phrase": "are indifferent to", "label": "Indifferent", "mult": 0.0},
    {"key": "like", "phrase": "like", "label": "Like", "mult": 1.0},
    {"key": "love", "phrase": "love", "label": "Love", "mult": 1.5}
  ],
  "dimensions": [ ... ]
}
```

- `gram_matrix`: K×K matrix for slider co-movement (used in adjustable sliders condition)
- `inference_categories`: domain-specific category labels and multipliers

### Output: response JSON

```json
{
  "participant_id": "R_abc123",
  "condition": "inference_categories",
  "domain": "movies_100",
  "num_trials": 20,
  "num_training": 5,
  "training_responses": [
    {
      "trial_id": "t12",
      "dimension_id": 1,
      "dimension_name": "Emotional Depth",
      "option_a_id": "57532",
      "option_b_id": "5833",
      "chosen": "a",
      "correct_option": "a",
      "correct": true,
      "response_time_ms": 3120
    }
  ],
  "timestamp": "2026-04-28T12:00:00.000Z",
  "responses": [
    {
      "trial_id": "t1",
      "option_a_id": "57532",
      "option_b_id": "5833",
      "chosen": "a",
      "response_time_ms": 4523,
      "visible_dimensions": ["dim_1", "dim_3", "dim_7", "dim_12", "dim_15"],
      "inference_values": {
        "dim_1": {"category": "love", "action": "affirm", "multiplier": 2.25},
        "dim_3": {"category": "like", "action": "modify", "multiplier": 1.0},
        "dim_7": {"category": "indifferent", "action": "none", "multiplier": 0.0},
        "dim_12": {"category": "not_into", "action": "remove", "multiplier": 0.0},
        "dim_15": {"category": "enjoy", "action": "moderate", "multiplier": 1.0}
      }
    }
  ]
}
```

**Condition-specific fields:**

| Condition | Extra fields in each response |
|-----------|-------------------------------|
| `choice_only` | (none) |
| `choice_readonly_sliders` | `slider_values`, `sliders_adjusted: false` |
| `choice_adjustable_sliders` | `slider_values`, `sliders_adjusted: true` |
| `choice_checkboxes` | `checkbox_values` |
| `inference_affirm` | `inference_values` (with action: affirm/moderate/remove/none) |
| `inference_categories` | `inference_values` (with action: modify/none, category from picker) |

**Multiplier computation:**
- Base multiplier comes from the selected category's `mult` value
- `action: "affirm"` multiplies by 1.5 (e.g., "love" 1.5 × 1.5 = 2.25)
- `action: "moderate"` uses the moderated category's mult (one step toward center)
- `action: "remove"` forces multiplier to 0.0 regardless of category
- `action: "none"` uses the default category's mult unchanged

## Generating Trials

After the pipeline has produced embeddings, dimensions, and directions:

```bash
python generate_trials.py \
  --config ../method_llm_examples/configs/movies_100.json \
  --embeddings-parquet ../datasets/movies_100/movielens-32m-enriched-qwen3emb-100-embedded.parquet \
  --dimensions ../method_llm_gen/outputs/movies_100/dimensions.json \
  --directions ../method_directions/outputs/movies_100/directions.npz \
  --output-dir outputs/movies_100 \
  --poster-urls ../datasets/movies_100/poster_urls.json \
  --num-pairs 200 \
  --trials-per-participant 30 \
  --domain movies \
  --choice-context "Which movie would you rather watch right now?" \
  --seed 42
```

For scruples with pre-defined dilemma pairs:
```bash
python generate_trials.py \
  --config ../method_llm_examples/configs/scruples_dilemmas.json \
  --embeddings-parquet ../datasets/scruples_dilemmas/selected_actions-embedded.parquet \
  --dimensions ../method_llm_gen/outputs/scruples_dilemmas/dimensions.json \
  --directions ../method_directions/outputs/scruples_dilemmas/directions.npz \
  --output-dir outputs/scruples_dilemmas \
  --pairs-csv ../datasets/scruples_dilemmas/selected_pairs.csv \
  --pair-a-column action_0_id --pair-b-column action_1_id \
  --seed 42
```

## Randomization

Trial order is deterministically shuffled per participant using a seeded PRNG (seed = hash of participant ID). Each participant sees a random subset of `n` trials from the full pool. The same participant ID always produces the same trial sequence.

## Design Notes

- **Single file, no dependencies.** The entire app is one HTML file with inline CSS and JS.
- **No localStorage/sessionStorage.** All state lives in JS variables.
- **Domain-configurable.** Categories, prompts, and field visibility are driven by `experiment_config.json`.
- **iframe-aware.** Sends postMessage to parent window on completion for Qualtrics integration.
- **Graceful degradation.** Missing poster images, missing config files, and old trial formats all handled with fallbacks.
- **Scrolls to top** after each trial submit.
