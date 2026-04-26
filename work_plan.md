# Natural Language Preference Learning — Work Plan

*Last updated: April 26, 2026*

---

## 1. Project Summary

We develop methods to learn interpretable preference representations from natural language. An LLM discovers human-understandable dimensions of preference (e.g., "Action Intensity," "Moral Complexity") from pairwise comparisons, locates those dimensions as directions in an embedding space, and uses them to accelerate preference learning. The key insight: by projecting preference-learning gradients onto this interpretable subspace, we can (a) learn faster with fewer observations, (b) let users provide richer feedback via dimension-level sliders, and (c) inspect and audit what a fine-tuning run is actually changing.

The paper has three contributions:
1. **Method**: A pipeline that extracts interpretable preference dimensions and locates them as directions in embedding space, forming a non-orthogonal basis with known correlation structure.
2. **Acceleration**: Projecting preference-learning gradients onto this basis speeds convergence by 2–3× across domains (movies, moral dilemmas), with additional gains when users provide per-dimension feedback.
3. **Safety application**: Decomposing fine-tuning gradients onto interpretable dimensions reveals *which human-understandable qualities* a training run is degrading — enabling interpretable monitoring for emergent misalignment.

---

## 2. What's Working

### 2.1 End-to-End Pipeline

The full 8-step pipeline (`run_pipeline.sh`) is functional and domain-general:

```
Step 1: Embed           → parquet with embeddings (Qwen3-Embedding-8B, d=4096)
Step 2: Select           → diversity-maximized subset via farthest-first traversal
Step 3: Config gen       → JSON configs for downstream steps
Step 4: Dimension discovery → LLM reasons about pairs, condenses into K unipolar dimensions
Step 5: Score + BTL      → per-dimension scores via LLM judge, Bradley-Terry model
Step 6: Find directions  → ridge regression: BT scores → embedding directions
Step 7: Evaluate basis   → coverage, independence, correlation metrics
Step 8: Generate trials  → experiment-ready trials.json with pre-computed projections
```

All steps skip if output exists. Configs are YAML. Adding a new domain requires only a CSV, a prompt template, and a YAML config.

### 2.2 Completed Domain Runs

| Domain | N | K | Coverage | Rel. Coverage | Gram κ | Max ρ |
|--------|---|---|----------|---------------|--------|-------|
| Movies 50 | 50 | 10 | 0.220 | 59.9% | — | — |
| Movies 100 | 100 | 25 | — | — | 45.3 | 0.814 |
| Scruples 200 | 200 | 25 | 0.177 | 46.7% | — | — |

Movies 100 and Scruples 200 have full pipeline outputs: dimensions, BT scores, directions, evaluation, and experiment trials.

### 2.3 Simulation Results

**Weight-vector simulation** (50 synthetic users, 100 trials, 200 test pairs):

| Domain | Standard | Projected | Slider | Partial |
|--------|----------|-----------|--------|---------|
| Movies 100 | 0.765 | **0.817** | 0.795 | 0.793 |
| Scruples 200 | 0.640 | 0.708 | **0.722** | 0.674 |

**LLM-persona simulation** (20 Qwen3-32B personas, 50 trials, 50 test pairs):

| Domain | Standard | Projected | Slider | Partial |
|--------|----------|-----------|--------|---------|
| Movies 100 | 0.725 | 0.721 | 0.729 | **0.751** |
| Scruples 200 | 0.625 | 0.651 | **0.660** | **0.660** |

Key findings:
- Projected and slider consistently beat standard (the only exception is projected ≈ standard in movies LLM sim).
- Slider reaches 75% at trial 28 vs. trial 81 for standard (movies weight-vec) — 2.9× faster.
- Partial is the most robust condition across domains and simulation types.
- LLM persona consistency: 89.5% (movies), 85.5% (scruples).

### 2.4 Web Interface

`web-interface/index.html` is a single-file experiment app with 4 between-subjects conditions:

1. **Choice Only** — binary choice, no dimensions shown (control)
2. **Choice + Read-Only Sliders** — top-5 dimension scores shown but locked
3. **Choice + Adjustable Sliders** — top-5 sliders with Gram-matrix co-movement
4. **Choice + Relevance Checkboxes** — top-5 dimensions as checkboxes (binary relevance)

Features: setup screen with participant ID/condition/trial count, structured option cards, deterministic per-participant randomization, response timing, download JSON.

### 2.5 Data Prepared (Not Yet Run Through Pipeline)

- **EM Code** (Betley et al.): 12K code completions (6K insecure + 6K secure), `configs/em_code.yaml` ready
- **EM Medical** (Turner et al.): 316 medical advice responses (167 good + 149 bad), `configs/em_medical.yaml` ready

### 2.6 Technical Fixes Implemented This Session

- **Slider frame bug**: slider_adjustment was using BT score differences instead of embedding projections — fixed to use `|w*| ⊙ Vδ`
- **Non-orthogonal V**: switched from `directions_ortho` to `directions_raw` with G⁻¹ correction in all projection operations
- **Qwen3 thinking mode**: added `enable_thinking: False` in API calls + `<think>` block stripping as fallback
- **Domain-general LLM simulation**: `--domain` and `--choice-context` flags added to persona generation and choice prompts
- **Persona generation**: increased `max_tokens` from 512 to 4096, fixed truncation parsing

---

## 3. What Needs to Be Done

### Phase 0: Diagnostics & Design Decisions (1–2 days)

**0a. PCA scree analysis for movies_100.**
We have scree data for scruples but not movies_100. This determines how many dimensions the embedding space actually supports.

```bash
python method_directions/evaluate_basis.py --scree \
  --embeddings-parquet datasets/movies_100/movielens-32m-enriched-qwen3emb-100-embedded.parquet \
  --embedding-column embedding \
  --output-dir method_directions/outputs/movies_100
```

**0b. Determine optimal K.**
Current evidence:
- Movies 50 at K=10: relative coverage = 59.9%, slider accuracy = 0.829 (weight-vec, fixed)
- Scruples at K=25: relative coverage = 46.7%, slider accuracy = 0.722
- The cumulative variance ratio r_j plateaus around K=15 for scruples

Recommendation: **K = 12–15**, pruned by BT score variance and inter-correlation. Dimensions with near-zero BT variance or Spearman ρ > 0.8 with another dimension should be merged or dropped.

Action: Add a `--prune-to-k` flag to the pipeline that keeps the top-K dimensions by BT score variance after removing highly correlated pairs.

**0c. Evaluate larger embedding model.**
Currently using Qwen3-Embedding-8B (d=4096). Options:
- Qwen3-32B-Instruct as embedder (last-hidden-state pooling, d=5120) — fits on one GPU
- Keep current model if scree shows diminishing returns beyond d=4096

Quick test: embed 50 movies with the 32B model and compare the scree curve. If the first 15 PCA components capture meaningfully more variance, switch.

**0d. Fix archetype generation for domain generality.**
`build_archetypes()` in `run_simulation.py` uses movie-specific keyword matching. For scruples, many archetypes have zero matching dimensions. Options:
- Make archetypes data-driven (cluster BT score profiles, use cluster centroids as archetypes)
- Use the LLM simulation only (which generates domain-appropriate personas automatically)

Recommendation: implement data-driven archetypes so the weight-vector sim is meaningful across domains.

---

### Phase 1: Nail Movies & Polish Pipeline (3–5 days)

**1a. Curate experiment-ready movies.**
Current selection optimizes for embedding diversity but not participant comprehension. Improve:
- Filter to movies with high recognition (rating_count ≥ 5000 or manual review)
- Filter to release year ≥ 1985 to avoid obscure older films
- Ensure genre diversity within the recognition-filtered set
- Target N=100 movies that any college-educated adult would recognize

**1b. Re-run pipeline with optimal K.**
After pruning, re-run steps 5–8 (scoring, BT, directions, evaluation, trials). Steps 1–4 are cached.

**1c. Update interface for deployment.**
- Add URL parameter support: `?pid=P001&condition=choice_adjustable_sliders&n=30`
- Add POST endpoint for response submission (Google Sheets webhook or Flask endpoint)
- Host on GitHub Pages or MIT webspace
- Create Qualtrics wrapper that embeds the experiment via iframe and handles consent/debrief

**1d. Pilot test.**
Both authors run all 4 conditions (5 trials each, ~20 min total). Check:
- Are option cards readable? Too much text?
- Do slider labels make sense without explanation?
- Does co-movement feel natural or confusing?
- Is top-5 the right cutoff? (Try top-3 and top-7 as well)
- Checkbox condition: is it clear what "relevant" means?

**1e. Pre-compute experiment data.**
Run `generate_trials.py` with final K and movie set. Output `trials.json` and `experiment_config.json` with Gram matrix. Verify all 200 trial pairs render correctly in the interface.

---

### Phase 2: Multi-Domain Runs (3–5 days, parallelizable)

Each domain follows the same recipe: CSV + prompt template + YAML config → `run_pipeline.sh` → simulations → experiment trials.

**2a. Scruples (done — verify and polish).**
Pipeline complete. Simulations complete. Generate experiment trials and pilot the interface with moral dilemma option cards.

**2b. Wines.**
Data: `datasets/wine-130k.csv` (130K reviews). Create:
- `datasets/wine_prompt.txt`: `Wine for preference modeling. Name: {name}. Variety: {variety}. Region: {region}. Description: {description}`
- `configs/wines_100.yaml`
- Run pipeline, simulations, trial generation

This is the "fun color" domain — low stakes, everyone has opinions, great for talks and demos.

**2c. EM Medical (emergent misalignment).**
Data prepared (316 responses). Run:
```bash
./run_pipeline.sh configs/em_medical.yaml
```
Then run weight-vector and LLM simulations. Also run the gradient decomposition (Phase 3).

**2d. EM Code (emergent misalignment).**
Data prepared (12K completions). Same pipeline. Note: with 12K options, selection step picks 200 diverse completions, so the pipeline handles the scale.

**2e. Cross-domain metrics table.**
For each domain, compute and tabulate:

| Metric | Movies | Scruples | Wines | EM Medical | EM Code |
|--------|--------|----------|-------|------------|---------|
| N (options) | 100 | 200 | 100 | 200 | 200 |
| K (dimensions) | 12 | 15 | 12 | 15 | 15 |
| Coverage(V) | | | | | |
| Rel. coverage (V/PCA) | | | | | |
| Gram κ | | | | | |
| Max |ρ_ij| | | | | | |
| Sim accuracy (standard) | | | | | |
| Sim accuracy (best) | | | | | |
| Sim gain (best − standard) | | | | | |

This becomes **Table 1** in the paper: "Featurizability of preference domains."

---

### Phase 3: Emergent Misalignment Demonstration (3–5 days)

This is the paper's headline safety result.

**3a. Gradient decomposition.**
New script: `analysis/em_decomposition.py`

For each EM domain (medical, code):
1. Load embeddings, V, G⁻¹, category labels
2. Compute fine-tuning gradient: `g = mean(φ(bad)) − mean(φ(good))`
3. Project: `λ_em = V g` (K-dimensional)
4. Decorrelate: `λ_clean = G⁻¹ λ_em`
5. Plot as a horizontal bar chart: which dimensions does the fine-tuning push?

Expected results:
- Medical: negative on "evidence-based sourcing," "risk acknowledgment"; positive on "confident tone"
- Code: negative on "input validation," "parameterized queries"; positive on "code brevity"

**3b. Mitigation analysis.**
- Identify "dangerous" dimensions: those with |λ_em| above a threshold
- Compute the complement projector: P_safe = I − V_danger⊤ G_danger⁻¹ V_danger
- Apply to gradient: g_safe = P_safe g
- Show that g_safe preserves learning on "benign" dimensions while removing the misalignment signal
- Metric: cosine similarity between g and g_safe (how much learning is preserved) vs. reduction in dangerous dimension activation

**3c. Connection to Soligo et al. (2025).**
They find one opaque direction mediating emergent misalignment. We find K interpretable dimensions that decompose it. Compute:
- Cosine similarity between their direction and our reconstructed direction V⊤ G⁻¹ λ_em
- If high (>0.8): our decomposition is a strict refinement — same signal, but interpretable
- The paper's argument: a safety reviewer can look at our bar chart and understand *what* the fine-tuning is changing, without ever inspecting the training data

**3d. Prompt iteration for EM domains.**
The dimension discovery prompts may need tuning for code and medical domains:
- Code: ensure the LLM generates security-relevant reasons (input validation, SQL injection, XSS) and not just stylistic ones (variable naming, commenting)
- Medical: ensure dimensions capture accuracy/safety (evidence-based, appropriate referral) not just tone (empathetic, concise)

Add a `--reason-prompt-override` flag to the pipeline for domain-specific prompt injection without modifying the base prompts.

---

### Phase 4: Distortion Analysis (2 days)

**4a. Formal definition.**
Distortion = divergence between user's true utility u(a) = w*⊤φ(a) and projected utility u_proj(a) = w*⊤ P φ(a) where P = V⊤ G⁻¹ V is the oblique projector.

When w* has significant components outside span(V), projection introduces systematic bias toward the subspace. Users whose preferences don't align with the discovered dimensions will be poorly served by projected/slider conditions.

**4b. Simulation.**
- Generate users whose w* has controlled amounts of out-of-subspace weight
- Vary the fraction α ∈ [0, 1] of w* that lies in span(V)
- Plot accuracy vs. α for each condition
- Expected: standard is invariant to α; projected/slider degrade as α decreases; partial is robust

**4c. Implications.**
- Motivates the **partial condition** as the default recommendation
- Motivates giving users **choice over whether to use the projection** (informed consent)
- Connects to computational social choice literature on preference distortion under dimensionality reduction

---

### Phase 5: Human Experiment (2–4 weeks including IRB)

**5a. Experimental design.**
- Between-subjects: 4 conditions × ~50 participants each = 200 participants
- Within-subjects alternative: each participant does 10 trials in each condition (counterbalanced)
- Domain: movies (most accessible)
- 30 trials per participant, ~15 minutes total
- Outcome measures: prediction accuracy on held-out pairs, response time, slider adjustment patterns

**5b. IRB submission.**
- MIT COUHES protocol
- Informed consent covering: data collection (choices, slider values, timing), anonymization, study purpose
- No deception needed — participants know they're rating movies

**5c. Recruitment.**
- Prolific or university subject pool
- Compensation: $5–7 for 15 minutes
- Screening: must have seen ≥ 30 of the 100 movies (pre-screening survey)

**5d. Analysis plan.**
- Primary: choice prediction accuracy by condition (mixed-effects logistic regression)
- Secondary: learning speed (trials to 75% accuracy), slider adjustment behavior
- Exploratory: individual differences in "featurizability" (do some people align better with the discovered dimensions?)

---

### Phase 6: Paper Writing (ongoing)

**6a. Structure.**

1. Introduction: preference learning is data-hungry; interpretable dimensions can help
2. Method: pipeline (dimension discovery → direction-finding → gradient projection)
3. Theory: non-orthogonal basis, oblique projection, co-movement
4. Experiments:
   - Table 1: Cross-domain featurizability metrics
   - Table 2: Simulation results (weight-vec + LLM, 4+ domains)
   - Figure 1: Learning curves (movies + scruples side by side)
   - Figure 2: EM gradient decomposition bar chart (headline figure)
   - Figure 3: Distortion analysis (accuracy vs. out-of-subspace fraction)
   - Human experiment results
5. Discussion: when does this help? limitations? broader impact?

**6b. Key claims to support.**
1. LLM-discovered dimensions capture ~50–60% of preference-relevant variance in embedding space
2. Projecting gradients onto this subspace accelerates learning by 2–3× across domains
3. User-provided dimension-level feedback (sliders) further improves convergence
4. The decomposition reveals interpretable failure modes in fine-tuning (emergent misalignment)
5. Full projection can introduce distortion; partial projection is the robust default

---

## 4. Infrastructure & Tech Debt

| Issue | Status | Fix |
|-------|--------|-----|
| Dropbox ↔ server sync unreliable | Ongoing | Use `scp` for critical files; git for code |
| Qwen3 `<think>` blocks | Mitigated | `enable_thinking: False` + stripping; root fix is vLLM `--chat-template` |
| `select_options.py` naming | Fixed | Pipeline uses predictable names; old runs need symlinks |
| `run_jobs` crash on JSON errors | Fixed | Truncated JSON repair + per-job try/catch |
| Archetypes are movie-specific | Open | Make data-driven (cluster BT profiles) |
| Experiment data hosting | Open | GitHub Pages or MIT webspace + Qualtrics wrapper |
| Git ignoring web-interface/outputs | Fixed | `.gitignore` updated |

---

## 5. Immediate Action Items (Priority Order)

### This Week

1. ☐ **Run scree for movies_100** — determines K (5 min on server)
2. ☐ **Run EM medical pipeline** — `./run_pipeline.sh configs/em_medical.yaml` (2–4 hours on server)
3. ☐ **Write `analysis/em_decomposition.py`** — gradient decomposition script (2 hours)
4. ☐ **Create `configs/wines_100.yaml`** and run pipeline (1 hour setup + 2–4 hours pipeline)
5. ☐ **Pilot web interface** locally with movies_100 trials — identify UX issues (30 min)
6. ☐ **Add URL-param support to `index.html`** — enables Qualtrics embedding (1 hour)

### Next Week

7. ☐ **Decide on K** based on scree analysis; add `--prune-to-k` to pipeline
8. ☐ **Re-run movies with optimal K** and curated movie set
9. ☐ **Run EM code pipeline** — `./run_pipeline.sh configs/em_code.yaml`
10. ☐ **Run gradient decomposition** on EM medical and EM code — produce bar chart figures
11. ☐ **Run distortion simulation** — accuracy vs. out-of-subspace fraction
12. ☐ **Draft cross-domain metrics table** (Table 1)

### Week 3+

13. ☐ **Build Qualtrics experiment** with iframe embedding
14. ☐ **Submit IRB protocol** (MIT COUHES)
15. ☐ **Run simulations on all domains** — complete Table 2
16. ☐ **Draft paper sections**: Method, Experiments, Figures
17. ☐ **Pilot human experiment** with 10 participants (post-IRB)

---

## 6. File & Directory Reference

```
preference-learning-dev/
├── run_pipeline.sh                    # 8-step end-to-end pipeline
├── configs/                           # YAML configs per domain
│   ├── movies_100.yaml
│   ├── scruples_200.yaml
│   ├── em_code.yaml
│   └── em_medical.yaml
├── datasets/                          # Raw data, prepared CSVs, selected subsets
│   ├── prepare_em_code.py
│   ├── prepare_em_medical.py
│   ├── select_options.py
│   ├── movies_100/                    # Selected + embedded
│   └── scruples_200/
├── embed/embedder/embed_csv.py        # Embedding script
├── method_llm_examples/               # Dimension discovery (Step 4)
│   ├── pipeline.py
│   ├── configs/
│   └── outputs/
├── method_llm_gen/                    # Scoring + BTL (Step 5)
│   ├── pipeline.py
│   ├── prompts/
│   └── outputs/
├── method_directions/                 # Direction-finding + evaluation (Steps 6–7)
│   ├── find_directions.py
│   ├── evaluate_basis.py
│   └── outputs/
├── simulation/                        # Weight-vec + LLM simulations
│   ├── run_simulation.py
│   ├── run_llm_simulation.py
│   └── outputs/
├── web-interface/                     # Experiment interface
│   ├── index.html
│   ├── generate_trials.py
│   └── outputs/
└── analysis/                          # Post-hoc analysis scripts (to be created)
    └── em_decomposition.py            # EM gradient decomposition
```

---

## 7. Server Information

- **Cluster**: MIT ORCD "align" (align-3.csail.mit.edu)
- **GPUs**: 5 available (1 embed + 4 instruct)
- **HF_HOME**: `/raid/lingo/zachwoj/huggingface`
- **Work dir**: `/raid/lingo/zachwoj/work/preference-learning-dev`
- **Embedding model**: Qwen/Qwen3-Embedding-8B (d=4096)
- **Instruct model**: Qwen/Qwen3-32B (128K context, 4 replicas)
- **Server discovery**: `python discover_servers.py --type instruct -q`

---

## 8. Key Open Questions

1. **What is the optimal K?** Scree analysis will answer this. The slider simulation is sensitive to K (K=10 works much better than K=25 for slider feedback), but the projected condition is robust to K.

2. **Should we orthogonalize V or not?** Current approach: raw directions with G⁻¹ correction. This preserves semantic interpretability of each dimension but introduces co-movement complexity in the interface. Alternative: orthogonalize but reorder by semantic fidelity (drop dimensions where post-orthogonalization cosine < 0.8).

3. **How much does the embedding model matter?** Current Qwen3-8B captures ~47–60% of preference variance in K dimensions. A larger model might push this to 65–70%, which would strengthen all results. Worth testing with Qwen3-32B as embedder.

4. **Is the EM decomposition story strong enough for a top venue?** It needs to work cleanly: the bar chart must show interpretable, expected dimensions lighting up (security for code, evidence-based for medical). If the dimensions are noisy or unexpected, the story weakens. Prompt iteration on EM domains is critical.

5. **Slider vs. checkbox: which interface wins?** The checkbox condition (binary relevance) is simpler and faster but provides less information than adjusted slider values. The human experiment will resolve this.
