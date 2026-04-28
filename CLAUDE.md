# CLAUDE.md — Natural Language Preference Learning

## Project Summary

We develop methods to learn interpretable preference representations from natural language. An LLM discovers human-understandable dimensions of preference (e.g., "Action Intensity," "Emotional Depth") from pairwise comparisons, locates those dimensions as directions in an embedding space, and uses them to accelerate preference learning.

**The core loop:** A participant makes binary choices (e.g., "Which movie would you rather watch?"). After each choice, the system shows inferences about their preferences ("You love Action Intensity"). The participant confirms, adjusts, or removes each inference. This per-dimension feedback is converted to gradient multipliers that accelerate learning in the interpretable subspace.

**Three contributions:**
1. **Pipeline**: Extract interpretable preference dimensions from any domain (movies, wines, moral dilemmas) and locate them as directions in embedding space.
2. **Acceleration**: Projecting preference-learning gradients onto this basis speeds convergence 2–3× vs. standard BTL, with additional gains from user-provided per-dimension feedback.
3. **Safety application**: Decomposing fine-tuning gradients onto interpretable dimensions reveals *which human-understandable qualities* a training run is degrading — enabling interpretable monitoring for emergent misalignment.

## Infrastructure

### Server: MIT ORCD "align" cluster
- **Host**: align-3.csail.mit.edu
- **GPUs**: 5 available (1 embed + 4 instruct)
- **HF_HOME**: `/raid/lingo/zachwoj/huggingface`
- **Work dir**: `/raid/lingo/zachwoj/work/preference-learning-dev`
- **Embedding model**: Qwen/Qwen3-Embedding-8B (d=4096, last-token pooling)
- **Instruct model**: Qwen/Qwen3-32B (128K context, 4 replicas via vLLM)
- **Server discovery**: `python discover_servers.py --type instruct -q` / `--type embed -q`

### Local
- **Repo**: `~/Dropbox/academics/research/working/nlp/coding/preference-learning-dev`
- **GitHub Pages**: `https://zachary-wojtowicz.github.io/preference-learning-dev/web-interface/index.html`

### Key API Patterns
All LLM calls go through OpenAI-compatible vLLM endpoints. Critical setting: `enable_thinking: False` must be passed in extra_body for Qwen3 models (otherwise they output `<think>` blocks that break JSON parsing). The root `llm_call()` in `method_llm_gen/pipeline.py` handles this.

## Directory Structure

```
preference-learning-dev/
├── CLAUDE.md                          # This file
├── work_plan.md                       # Detailed research plan with phases
│
├── configs/                           # YAML configs per domain
│   ├── movies_100.yaml
│   ├── scruples_200.yaml
│   ├── scruples_dilemmas.yaml
│   ├── wines_100.yaml
│   ├── em_code.yaml
│   └── em_medical.yaml
│
├── datasets/                          # Raw data, prepared CSVs, embeddings
│   ├── prepare_scruples_v2.py         # Preserves dilemma pair structure
│   ├── select_dilemmas.py             # Pair-level diversity selection
│   ├── prepare_wines.py               # Wine data prep
│   ├── prepare_em_code.py             # Emergent misalignment: code
│   ├── prepare_em_medical.py          # Emergent misalignment: medical
│   ├── fetch_posters.py               # TMDB poster URLs for movies
│   ├── select_options.py              # Farthest-first diversity selection
│   ├── movie_prompt.txt               # Embedding template for movies
│   ├── wine_prompt.txt                # Embedding template for wines
│   ├── scruples_prompt.txt            # Embedding template for scruples
│   ├── movies_100/                    # Selected + embedded (100 movies)
│   │   ├── movielens-32m-enriched-qwen3emb-100.csv
│   │   ├── movielens-32m-enriched-qwen3emb-100-embedded.parquet
│   │   └── poster_urls.json           # TMDB poster image URLs
│   ├── scruples_200/                  # Selected + embedded (200 actions)
│   ├── scruples_dilemmas/             # Pair-aware selection (150 dilemma pairs)
│   │   ├── selected_pairs.csv
│   │   ├── selected_actions.csv
│   │   ├── selected_actions-embedded.parquet
│   │   └── predefined_pairs.json
│   └── wines_100/                     # Selected + embedded (100 wines)
│
├── embed/                             # Embedding infrastructure
│   ├── server/                        # vLLM server launch scripts
│   └── embedder/embed_csv.py          # Embed a CSV using template rendering
│
├── method_llm_examples/               # Step 4: Dimension discovery
│   ├── pipeline.py                    # Main pipeline: pair → reasons → themes → dimensions
│   ├── configs/                       # Per-domain JSON configs
│   └── outputs/                       # Discovered dimensions per domain
│
├── method_llm_gen/                    # Step 5: Scoring + BTL
│   ├── pipeline.py                    # Score options per dimension, fit Bradley-Terry
│   ├── prompts/                       # Scoring prompt templates
│   ├── configs/                       # Per-domain JSON configs
│   └── outputs/                       # BT scores, direct scores per domain
│
├── method_directions/                 # Steps 6-7: Direction finding + evaluation
│   ├── find_directions.py             # Ridge regression: BT scores → embedding directions
│   ├── evaluate_basis.py              # Coverage, independence, scree analysis
│   └── outputs/                       # directions.npz, evaluation.csv per domain
│
├── simulation/                        # Preference learning simulations
│   ├── run_simulation.py              # Weight-vector simulation (synthetic users)
│   ├── run_llm_simulation.py          # LLM-persona simulation (Qwen3-32B personas)
│   ├── simulation_spec.md             # Weight-vec simulation design doc
│   ├── llm_simulation_spec.md         # LLM simulation design doc
│   └── outputs/                       # Simulation results per domain
│
├── web-interface/                     # Experiment interface (see web-interface/CLAUDE.md)
│   ├── index.html                     # Single-file experiment app
│   ├── generate_trials.py             # Generate trials.json from pipeline outputs
│   ├── update_configs.py              # Update all experiment_config.json files
│   ├── CLAUDE.md                      # Detailed interface documentation
│   └── outputs/                       # Per-domain trials + configs
│       ├── movies_100/
│       ├── scruples_200/
│       ├── scruples_dilemmas/
│       └── wines_100/
│
├── run_movies_100.sh                  # Full pipeline for movies domain
├── run_wines_100.sh                   # Full pipeline for wines domain
├── run_scruples_dilemmas.sh           # Full pipeline for scruples (pair-aware)
├── run_pipeline.sh                    # Generic pipeline runner (from YAML config)
├── run_overnight.sh                   # Batch runner for multiple domains
├── discover_servers.py                # Find running vLLM servers on cluster
└── serve.sh                           # Launch vLLM servers
```

## Pipeline (8 Steps)

Each step skips if output already exists. Adding a new domain requires only: a CSV, a prompt template, and a YAML config.

```
Step 1: Embed            → embed_csv.py → parquet with 4096-dim embeddings
Step 2: Select            → select_options.py → diversity-maximized subset (farthest-first)
Step 3: Config gen        → gen config JSON for scoring step
Step 4: Dimension discovery → method_llm_examples/pipeline.py → K unipolar dimensions
Step 5: Score + BTL       → method_llm_gen/pipeline.py → per-dimension BT scores
Step 6: Find directions   → find_directions.py → ridge regression → K direction vectors
Step 7: Evaluate basis    → evaluate_basis.py → coverage, independence, scree
Step 8: Generate trials   → generate_trials.py → experiment-ready trials.json
```

**To run a full pipeline for a domain:**
```bash
# On server:
./run_movies_100.sh 2>&1 | tee movies_$(date +%Y%m%d_%H%M).log
./run_wines_100.sh 2>&1 | tee wines_$(date +%Y%m%d_%H%M).log
./run_scruples_dilemmas.sh 2>&1 | tee scruples_$(date +%Y%m%d_%H%M).log
```

## Core Math

### Embedding
Each option a has embedding φ(a) ∈ ℝ⁴⁰⁹⁶ from Qwen3-Embedding-8B. Text is rendered via a domain template (e.g., "Movie for preference modeling. Title: {title}. Genres: {genres}...") then embedded via last-token pooling on the final transformer layer.

### Preference Model
Each user has θ ∈ ℝ⁴⁰⁹⁶. Utility: u(a) = θ⊤φ(a). Choice probability: P(a≻b) = σ(θ⊤(φ(a)−φ(b))). SGD update: θ += lr·(y−pred)·δ where δ = φ(a)−φ(b). Generalizes to unseen options via dot product.

### Direction Finding
For each dimension k, ridge regression finds vₖ ∈ ℝ⁴⁰⁹⁶ such that vₖ⊤φ̃(aᵢ) ≈ BT_score_k(aᵢ). Uses RidgeCV with α ∈ {0.01, 0.1, 1, 10, 100, 1000}, LOO-CV. Typical held-out R² = 0.1–0.4.

### Non-Orthogonal Basis
V ∈ ℝᴷˣᵈ (K direction vectors, not orthogonal). Gram matrix G = VVᵀ (K×K). Oblique projector P = Vᵀ G⁻¹ V. Movies_100 has condition number ~45, max inter-dimension correlation ~0.81.

### Four Learning Conditions
| Condition | Update rule | Signal per trial |
|-----------|------------|------------------|
| Standard | θ += lr·(y−p)·δ | 1 bit (which option chosen) |
| Projected | θ += lr·(y−p)·Vᵀ G⁻¹ Vδ | 1 bit, restricted to K-dim subspace |
| Slider/Inference | θ += lr·(y−p)·Vᵀ G⁻¹ λ_adj | K continuous values (category multipliers) |
| Partial | blend of standard + slider | 1 bit + K continuous values |

### Inference Multipliers
When using inference conditions, the user assigns each visible dimension a category. The category multiplier scales the gradient component for that dimension:

| Category | Multiplier |
|----------|------------|
| Prefer to skip | -1.5 |
| Aren't into | -1.0 |
| Indifferent | 0.0 |
| Like | 1.0 |
| Love | 1.5 |

In `inference_affirm`, "Affirm" multiplies by an additional 1.5×; "Remove" zeros out; "Moderate" moves one category toward center.

Categories are domain-configurable via `experiment_config.json → inference_categories`. Scruples uses: Reject / Disapprove of / Indifferent / Understand / Endorse.

## Experiment Interface

See `web-interface/CLAUDE.md` for detailed documentation. Key points:

- **6 conditions**: choice_only, choice_readonly_sliders, choice_adjustable_sliders, choice_checkboxes, inference_affirm, inference_categories
- **URL params**: `?domain=movies_100&pid=P001&condition=inference_categories&n=30`
- **Qualtrics integration**: iframe embed with postMessage on completion → captured as embedded data
- **Domain switching**: loads from `outputs/<domain>/trials.json` and `experiment_config.json`
- **Poster images**: movies have TMDB poster URLs (400px max-height)
- **Hidden fields**: movie_id, wine_id, rating_count, points, price, taster_name, etc.

### Qualtrics Survey
- **Survey ID**: SV_8iclgrFAgbt2LmC
- **Prototype Config block** (BL_1HuzArhzLYFnRWu): MC selectors for condition (QID6) and domain (QID7) that set embedded data via QuestionJS. Remove for production.
- **Experiment block** (BL_d6xAo6J50GtvdhI, QID2): iframe with QuestionJS that catches postMessage and stores in `experiment_data` embedded field
- **Flow order needs manual fix**: drag "Prototype Config" between "Default Question Block" (consent) and "Experiment" in Qualtrics survey flow editor (API 500'd on reorder)

## Simulation Results

### Weight-vector (50 synthetic users, 100 trials, 200 test pairs)
| Domain | Standard | Projected | Slider | Partial |
|--------|----------|-----------|--------|---------|
| Movies 100 | 0.765 | **0.817** | 0.795 | 0.793 |
| Scruples 200 | 0.640 | 0.708 | **0.722** | 0.674 |

### LLM-persona (20 Qwen3-32B personas, 50 trials, 50 test pairs)
| Domain | Standard | Projected | Slider | Partial |
|--------|----------|-----------|--------|---------|
| Movies 100 | 0.725 | 0.721 | 0.729 | **0.751** |
| Scruples 200 | 0.625 | 0.651 | **0.660** | **0.660** |

Key: Slider reaches 75% at trial 28 vs. 81 for standard (movies) — 2.9× faster.

## Scruples (Moral Dilemmas) — Pair Structure

Scruples dilemmas are original AITA-derived pairs where each dilemma has exactly two actions. The pipeline preserves this pair structure:
- `prepare_scruples_v2.py` outputs pairs CSV + actions CSV
- `select_dilemmas.py` selects diverse dilemmas at the pair level (farthest-first on mean-of-two-action embeddings)
- `--predefined-pairs` flag on dimension discovery uses original dilemma pairs instead of random pairs
- `--pairs-csv` flag on trial generation uses original pairs as experiment trials
- Gold annotations (crowd votes on which action is less ethical) are carried through for validation

## Emergent Misalignment Domains (Not Yet Complete)

- **EM Medical** (Turner et al.): 316 responses (167 good + 149 bad medical advice). Config ready, pipeline not yet run.
- **EM Code** (Betley et al.): 12K code completions (6K secure + 6K insecure). Config ready, pipeline not yet run.

The safety demonstration: decompose the fine-tuning gradient g = mean(φ(bad)) − mean(φ(good)) onto interpretable dimensions to show *which qualities* the fine-tuning degrades. Script needed: `analysis/em_decomposition.py`.

## Current Status & What's Next

### DONE
- ✅ Full pipeline for movies_100, scruples_200 (dimensions, scores, directions, trials)
- ✅ Weight-vector + LLM simulations for movies_100 and scruples_200
- ✅ Web interface with 6 conditions (including 2 inference conditions)
- ✅ Domain-configurable inference categories
- ✅ Qualtrics survey created (SV_8iclgrFAgbt2LmC) with prototype config
- ✅ GitHub Pages hosting
- ✅ Scruples pair-aware pipeline (`run_scruples_dilemmas.sh`)
- ✅ Poster image support (fetch_posters.py + interface)
- ✅ Pipeline scripts: run_movies_100.sh, run_wines_100.sh, run_scruples_dilemmas.sh

### IN PROGRESS (running on server)
- 🔄 run_scruples_dilemmas.sh — may be running
- 🔄 run_wines_100.sh — queued to run
- 🔄 run_movies_100.sh — queued to run

### NEEDS DOING
- ☐ Apply postMessage patch to index.html (for Qualtrics iframe communication)
- ☐ Fix Qualtrics survey flow order (manual drag in UI)
- ☐ Activate Qualtrics survey for co-author testing
- ☐ Get TMDB API key, fetch poster URLs, regenerate movies trials with posters
- ☐ Run EM medical + EM code pipelines on server
- ☐ Write `analysis/em_decomposition.py` (gradient decomposition)
- ☐ Determine optimal K via scree analysis
- ☐ Update simulation code for inference condition multipliers (currently only simulates slider)
- ☐ Data-driven archetypes for weight-vector simulation (current archetypes are movie-specific)
- ☐ Human experiment: IRB submission (MIT COUHES), recruitment, analysis plan
- ☐ Paper writing: cross-domain metrics table, learning curve figures, EM bar charts

## Key Technical Decisions

1. **Non-orthogonal V with G⁻¹**: We use `directions_raw` everywhere. Orthogonalization distorts semantic meaning. The Gram matrix correction handles the non-orthogonality.

2. **Unipolar dimensions**: Each dimension measures "how much of quality X" (0 to high), not "quality X vs. quality Y." This is critical for the inference interface — "You love Action Intensity" makes sense; "You prefer Action over Drama" doesn't.

3. **enable_thinking: False**: Required for all Qwen3 API calls. Set in the root `llm_call()` function in `method_llm_gen/pipeline.py`. Without this, Qwen3 outputs `<think>` blocks that break JSON parsing.

4. **Categories are domain-specific**: The 5-level scale (e.g., "prefer to skip" → "love") is stored in `experiment_config.json → inference_categories`. Different domains need different language (movies vs. moral dilemmas).

5. **Inference conditions replace sliders for the experiment**: The slider UI was confusing for participants. Two inference conditions replace it: `inference_affirm` (Remove/Moderate/Affirm) and `inference_categories` (5-level category picker). The slider conditions remain for internal testing/comparison.

## Session Transcripts

Full development history is in `/mnt/transcripts/journal.txt` (5 sessions, each 4-8 hours). Key sessions:
- Session 1: Literature review, codebase review, pipeline architecture
- Session 2: Full pipeline implementation, dataset selection, infrastructure
- Session 3: Pipeline automation, unipolar dimensions, web interface
- Session 4: Simulation fixes, EM data prep, scruples pairs, inference conditions
- Session 5 (current): Inference UI refinement, wines/movies pipeline scripts, Qualtrics integration, domain-configurable categories
