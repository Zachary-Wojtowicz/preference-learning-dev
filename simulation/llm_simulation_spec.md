# Task: LLM-Persona Simulation

## Goal

Replace the synthetic weight-vector users in `simulation/run_simulation.py` with LLM-driven personas. This adds realism: instead of a dot-product utility function, each simulated user is an LLM prompted with a naturalistic persona description. The LLM makes choices and adjusts sliders the same way a human participant would in the web interface.

This is a **new script** (`simulation/run_llm_simulation.py`) that reuses the gradient update and evaluation machinery from the existing simulation but swaps the user model.

## Two-Stage Design

### Stage 1: Persona Generation

Prompt an LLM to generate ~20 diverse persona descriptions for the domain. Each persona should be a short paragraph (3–5 sentences) describing a realistic person with distinctive preferences — not a caricature, but someone whose taste you could predict if you knew them.

**Prompt template (adapt for domain):**

```
You are helping design a psychology experiment about movie preferences.

Generate {N} diverse, realistic personas of people who watch movies. Each persona should be a short paragraph (3–5 sentences) describing the person's background, personality, and movie-watching habits in enough detail that you could predict which of two movies they'd prefer.

The personas should collectively represent meaningful variation in movie preferences. Include people who differ in age, background, and taste — not just genre preferences, but also preferences for things like pacing, emotional depth, visual style, humor, complexity, etc.

Do NOT make the personas cartoonish or one-dimensional. Real people have nuanced, sometimes contradictory tastes.

Return each persona in this format:

===PERSONA===
name: <first name and age>
description: <3–5 sentence description>
```

**Output:** Save as `personas.json` in the output directory:

```json
[
  {
    "id": 0,
    "name": "David, 42",
    "description": "David is a high school history teacher who gravitates toward films that reward patience — slow-burn dramas, historical epics, and character studies. He finds most action movies tedious but makes exceptions for tightly plotted thrillers. He cares deeply about dialogue and will rewatch a film just for a well-written scene. He dislikes CGI-heavy spectacles and broad comedies, though he has a soft spot for dry, understated humor."
  }
]
```

**Implementation:** One LLM call. Use the same OpenAI-compatible client pattern as `method_llm_gen/pipeline.py`. Parse the `===PERSONA===` blocks (same pattern as the dimension generation plain-text format).

### Stage 2: LLM-as-User Simulation

For each persona, run the same trial loop as the existing simulation, but replace the BTL choice model and slider adjustment model with LLM calls.

#### Choice prompt

For each trial, present the persona with two movie descriptions and ask it to choose:

```
You are roleplaying as the following person. Stay in character and make choices as this person would — not as a neutral AI.

PERSONA:
{persona_description}

---

You are choosing which movie to watch tonight. Read both options carefully, then choose the one this person would prefer.

OPTION A:
{option_a_text}

OPTION B:
{option_b_text}

Respond with valid JSON only:
{
  "thinking": "<2–3 sentences of in-character reasoning about what draws this person to one option over the other>",
  "choice": "A" or "B"
}
```

**Important:** The option texts should be the full rendered descriptions from the movie template (title, genres, director, stars, plot summary) — the same text that was embedded and scored.

#### Slider adjustment prompt

After the choice, present the persona with the K dimension sliders and ask for adjustments. The slider values are pre-populated with the model's current decomposition (exactly as in the web interface):

```
You just chose Option {choice} over Option {other}.

The system has decomposed your choice into the following preference dimensions. Each slider ranges from -100 to +100, where positive means the chosen option scores higher on this dimension and negative means the unchosen option scores higher.

Review each slider value. Adjust any that don't reflect why THIS PERSON made this choice. If a dimension was irrelevant to the choice, set it closer to 0. If a dimension was the primary driver, make its magnitude larger.

Current slider values:
{for each dimension k:}
- {dimension_name}: {slider_value} (low pole: {low_label} ↔ high pole: {high_label})

Respond with valid JSON only:
{
  "reasoning": "<1–2 sentences about which dimensions mattered most for this person's choice>",
  "adjusted_sliders": {
    "{dim_name_1}": <integer in [-100, 100]>,
    "{dim_name_2}": <integer in [-100, 100]>,
    ...
  }
}
```

The pre-populated slider values come from: `λ_model = V⊤(φ(a_chosen) − φ(a_unchosen))`, scaled to the [-100, 100] range.

### Connecting to the Learning Loop

The LLM's choice (A or B) maps to y ∈ {0, 1} exactly as in the existing simulation. The LLM's adjusted slider values map to `λ_adjusted` by rescaling from [-100, 100] back to the raw projection scale. Then the same four gradient update conditions run as before:

1. **Standard**: uses raw δ
2. **Projected**: uses VV⊤δ
3. **Slider-adjusted**: uses V λ_adjusted (from LLM slider output)
4. **Partial**: interpolation

### Evaluation

Since we don't have ground-truth w* for LLM personas, evaluation is different from the weight-vector simulation:

- **Choice prediction accuracy**: Still well-defined. Build a test set by having the LLM persona make choices on ~50 held-out pairs at the start (before training). Then measure how well θ predicts those pre-recorded choices after each training trial.
- **Choice prediction log-likelihood**: Same as above.
- **Utility correlation and weight recovery**: NOT available (no ground-truth w*). Omit these.
- **Internal consistency**: As a proxy for quality, report the LLM's own consistency — if you re-query it on the same pair, does it give the same answer? Run a small consistency check (10 duplicate pairs) per persona and report the agreement rate.

## CLI Interface

```
python simulation/run_llm_simulation.py \
  --embeddings-parquet datasets/movielens-32m-enriched-50-embedded.parquet \
  --bt-scores method_llm_gen/outputs/movies_50/bt_scores.csv \
  --dimensions method_llm_gen/outputs/movies_50/dimensions.json \
  --directions method_directions/outputs/movies_50/directions.npz \
  --option-descriptions datasets/movielens-32m-enriched-50.csv \
  --option-template datasets/movie_prompt.txt \
  --output-dir simulation/outputs/movies_50_llm \
  --base-url https://api.openai.com/v1 \
  --persona-model gpt-4o-mini \
  --choice-model gpt-4o-mini \
  --api-key "$OPENAI_API_KEY" \
  --num-personas 20 \
  --num-trials 50 \
  --num-test-pairs 50 \
  --learning-rate 0.01 \
  --projection-lambda 0.5 \
  --seed 42
```

Note: `--persona-model` is used for Stage 1 (generating personas) and `--choice-model` is used for Stage 2 (making choices and adjusting sliders). They can be different models (e.g., use a stronger model for persona generation, a cheaper one for the many choice calls).

## Outputs

Write to `simulation/outputs/<run_name>/`:

1. **`personas.json`**: The generated persona descriptions.
2. **`learning_curves.csv`**: Same schema as the existing simulation, one row per (persona_id, condition, trial).
3. **`choices_log.csv`**: Every LLM choice call with columns: persona_id, trial, option_a_id, option_b_id, choice, thinking, raw_sliders (JSON), adjusted_sliders (JSON). This is the full audit trail.
4. **`consistency_check.csv`**: Results of the duplicate-pair consistency test per persona.
5. **`summary.md`**: Same structure as existing simulation summary, minus weight-recovery metrics.
6. **`learning_curves.png`**: Same plot as existing simulation.

## Dependencies

Same as existing simulation plus `openai` (already in the repo's requirements). No new libraries needed.

## Key Design Notes

- **Rate limiting**: The choice model will be called (num_personas × num_trials) + (num_personas × num_test_pairs) times for choices, plus the same number again for slider adjustments. For 20 personas × 50 trials = 1,000 choice calls + 1,000 slider calls + 1,000 test calls = 3,000 total LLM calls. At ~$0.15/1K input tokens with gpt-4o-mini, this should cost under $5. Use `max_workers` for parallelism (but respect rate limits).
- **Caching**: Cache all LLM responses (keyed by persona_id + option_pair + prompt_type) so you can re-run analysis without re-querying. Write the cache as a JSON file.
- **Temperature**: Use temperature=0.3 for choices (some stochasticity to be realistic, but mostly consistent) and temperature=0 for slider adjustments (we want these to be deterministic given a choice).
- **The test set must be generated BEFORE training begins**: Query each persona on the test pairs first, record their answers, then run the training loop. The test set answers are fixed and used to evaluate θ at each trial.
- **This script should NOT import or modify `run_simulation.py`**. It's a standalone script that happens to implement the same gradient update functions. Copy over the update functions and evaluation logic rather than creating fragile cross-dependencies.
