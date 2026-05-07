#!/usr/bin/env bash
#
# migrate_to_clean.sh — Build a clean replication repo from this dev tree.
#
# Usage:
#   ./migrate_to_clean.sh [target_dir]
#
# Default target: ../preference-learning-clean
#
# This is idempotent — re-running it copies any files that have changed and
# leaves the rest alone. It does NOT delete files in the target tree.
#
# Audit-friendly: every copy is an explicit line. To exclude something,
# comment out or delete the corresponding line.

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-${SRC}/../preference-learning-clean}"
mkdir -p "$TARGET"

echo "[migrate] source: $SRC"
echo "[migrate] target: $TARGET"
echo

# Domains that ship in the paper.
DEPLOYED_DOMAINS=(dailydilemmas movies_100)              # full pipeline + experiment
OFFLINE_DOMAINS=(wines_100 coalign_50)                   # basis evaluation only
ALL_DOMAINS=("${DEPLOYED_DOMAINS[@]}" "${OFFLINE_DOMAINS[@]}")

# ---- helpers ---------------------------------------------------------------

copy_path() {
  # Copy a single path (file or directory) preserving its relative location.
  local rel="$1"
  if [[ ! -e "$SRC/$rel" ]]; then
    echo "[skip] $rel  (not in source)"
    return 0
  fi
  mkdir -p "$TARGET/$(dirname "$rel")"
  rsync -a "$SRC/$rel" "$TARGET/$(dirname "$rel")/"
  echo "[copy] $rel"
}

# ---- top-level files -------------------------------------------------------

copy_path pyproject.toml
copy_path uv.lock
copy_path .gitignore
copy_path discover_servers.py
copy_path serve.sh

# Pipeline orchestration (one bash script per domain + a generic YAML-driven runner).
copy_path run_dailydilemmas.sh
copy_path run_movies_100.sh
copy_path run_wines_100.sh
copy_path run_coalign_50.sh
copy_path run_pipeline.sh

# ---- configs/ (only the 4 deployed/offline domains) ------------------------

copy_path configs/movies_100.yaml
copy_path configs/wines_100.yaml
copy_path configs/coalign_50.yaml
# (no dailydilemmas.yaml — that domain ships the bash script as its entry point)

# ---- datasets/ -------------------------------------------------------------

# Per-domain selected + embedded artifacts (the inputs to method_llm_examples).
for d in "${ALL_DOMAINS[@]}"; do
  copy_path "datasets/$d"
done

# Per-domain prep / selection / templating scripts.
copy_path datasets/prepare_dailydilemmas.py
copy_path datasets/prepare_wines.py
copy_path datasets/prepare_coalign.py
copy_path datasets/select_options.py
copy_path datasets/select_dilemmas.py
copy_path datasets/select_coalign.py
copy_path datasets/fetch_posters.py
copy_path datasets/dailydilemmas_prompt.txt
copy_path datasets/movie_prompt.txt
copy_path datasets/wine_prompt.txt
copy_path datasets/coalign_prompt.txt

# Source CSVs for prepare scripts that aren't reproducible without them.
copy_path datasets/dailydilemmas-actions.csv
copy_path datasets/dailydilemmas-pairs.csv
copy_path datasets/wines-prepared.csv
copy_path datasets/movielens-32m-enriched.csv

# ---- embed/ (vLLM embedding infrastructure) --------------------------------

copy_path embed/server/server.py
copy_path embed/server/requirements.txt
copy_path embed/embedder/embed_csv.py
copy_path embed/embedder/requirements.txt
copy_path embed/readme.md

# ---- method_llm_examples/ (stage 1: dimension discovery) -------------------

copy_path method_llm_examples/pipeline.py
copy_path method_llm_examples/llm_example_spec.md
copy_path method_llm_examples/prompts

for d in "${ALL_DOMAINS[@]}"; do
  copy_path "method_llm_examples/configs/$d.json"
  copy_path "method_llm_examples/outputs/$d"
done

# ---- method_llm_gen/ (stage 2: per-option scoring + BTL) -------------------

copy_path method_llm_gen/pipeline.py
copy_path method_llm_gen/prompts
copy_path method_llm_gen/requirements.txt
copy_path method_llm_gen/method_readme.md
copy_path method_llm_gen/pipeline_readme.md

for d in "${ALL_DOMAINS[@]}"; do
  copy_path "method_llm_gen/configs/$d.json"
  copy_path "method_llm_gen/outputs/$d"
done

# ---- method_directions/ (stage 3: directions in encoder space) -------------

copy_path method_directions/find_directions.py
copy_path method_directions/evaluate_basis.py

for d in "${ALL_DOMAINS[@]}"; do
  copy_path "method_directions/outputs/$d"
done

# ---- simulation/ -----------------------------------------------------------

copy_path simulation/run_simulation.py
copy_path simulation/run_llm_simulation.py
copy_path simulation/simulation_spec.md
copy_path simulation/llm_simulation_spec.md

# Only the deployed-domain sim outputs that are referenced in the paper.
copy_path simulation/outputs/dailydilemmas
copy_path simulation/outputs/dailydilemmas_llm
copy_path simulation/outputs/movies_100_llm
# (no movies_100 weight-vector sim was run; nothing to copy)

# ---- web-interface/ (the deployed Qualtrics-embedded experiment) -----------

copy_path web-interface/index.html
copy_path web-interface/consent_form.html
copy_path web-interface/generate_trials.py
copy_path web-interface/update_configs.py
copy_path web-interface/polish_labels.py
copy_path web-interface/export_eval_data.py
copy_path web-interface/test_eval_parity.py
copy_path web-interface/test_js_parity.js
copy_path web-interface/test_end_to_end.js
copy_path web-interface/qualtrics_qid2_questionjs.txt

for d in "${DEPLOYED_DOMAINS[@]}"; do
  copy_path "web-interface/outputs/$d"
done

# ---- experiments/ (pre-registered analysis) --------------------------------

copy_path experiments/pipeline.py
copy_path experiments/configs.py
copy_path experiments/analyze.py
copy_path experiments/calibrate_methods.py
copy_path experiments/learning_curves.py
copy_path experiments/analyze_decomposition.py
copy_path experiments/select_top_dims.py

# Per-domain raw data + pre-registration + analysis outputs.
copy_path experiments/dilemmas/data.csv
copy_path experiments/dilemmas/prereg.md
copy_path experiments/dilemmas/analysis_outputs

copy_path experiments/movies/data.csv
copy_path experiments/movies/prereg.md
copy_path experiments/movies/analysis_outputs

# Cross-domain joint outputs (the canonical paper figures + tables).
copy_path experiments/outputs/dilemmas
copy_path experiments/outputs/movies
copy_path experiments/outputs/decomposition
copy_path experiments/outputs/paper

# ---- README ----------------------------------------------------------------

cat > "$TARGET/README.md" <<'README_EOF'
# Natural-Language Preference-Dimension Learning

Replication code and data for **"From Weights to Words: Expressing and Editing
Preference Model Inferences in Natural Language."**

## What this repo contains

A pipeline that uses a large language model to discover an interpretable,
low-dimensional basis of preference dimensions from text descriptions of
options, and a regularized Bradley-Terry-Luce estimator that infers a
participant's preferences on that basis from binary choices and (optionally)
natural-language feedback. We instantiate it across four domains and validate
it in two pre-registered human-subjects experiments:

| Domain          | K  | Status        | N (experiment) |
|-----------------|----|---------------|----------------|
| dailydilemmas   | 10 | full pipeline | 446            |
| movies_100      | 10 | full pipeline | 429            |
| wines_100       | 15 | offline only  | —              |
| coalign_50      | 15 | offline only  | —              |

## Setup

```bash
# Python env (uses uv; pyproject.toml + uv.lock are pinned).
uv sync

# For pipeline runs, you also need vLLM-style endpoints for:
#   - Qwen3-Embedding-8B  (the encoder φ)
#   - Qwen3-32B-Instruct  (the LLM that drives discovery + scoring)
# See embed/server/ and serve.sh for launch scripts; discover_servers.py
# locates running endpoints on a multi-host cluster.
```

## Reproducing the paper

There are three replication levels, each more from-scratch than the last.

### Level 1 — analysis only (cached experiment data)

Reproduces every table and figure in §4 of the paper from the participant
data shipped in `experiments/{dilemmas,movies}/data.csv`:

```bash
python experiments/pipeline.py
```

This runs `analyze.py` (H1/H2/H3 tests), `calibrate_methods.py` (the α/λ/
multiplier sweep), `learning_curves.py`, and `analyze_decomposition.py`,
producing all artifacts under `experiments/outputs/`. Joint paper figures
land in `experiments/outputs/paper/`.

### Level 2 — analysis + simulations (cached pipeline outputs)

Re-runs the synthetic and LLM-persona simulations on top of the discovered
basis. Requires a running Qwen3-32B endpoint for the LLM-persona sim.

```bash
python simulation/run_simulation.py        --help
python simulation/run_llm_simulation.py    --help
# Or invoke per-domain via the bash scripts (sections at the end).
```

### Level 3 — full pipeline from scratch

Each per-domain `run_*.sh` script orchestrates the eight pipeline stages
(prepare → embed → select → discover dimensions → score options → fit BTL →
find directions → evaluate). They expect vLLM endpoints to be running and
will exit early if not.

```bash
./run_dailydilemmas.sh
./run_movies_100.sh
./run_wines_100.sh
./run_coalign_50.sh
```

Each script is idempotent: stages skip if their outputs already exist.

## Directory layout

```
configs/                   YAML pipeline configs (one per offline domain)
datasets/                  prep + selection scripts, embed templates,
                            per-domain selected-and-embedded parquet files
embed/                     vLLM embedder client + server launch
method_llm_examples/       Pipeline stage 1: pair → reasons → themes →
                            named unipolar dimensions
method_llm_gen/            Pipeline stage 2: LLM-as-judge per-option
                            scoring → Bradley-Terry scores
method_directions/         Pipeline stage 3: ridge regression maps
                            embeddings to dimension scores → V
simulation/                Weight-vector + LLM-persona simulations
web-interface/             The deployed Qualtrics-embedded experiment
                            (single-file HTML app + trial generator)
experiments/               Pre-registered analysis pipeline + raw
                            participant data + pre-registrations + figures
run_<domain>.sh            Per-domain end-to-end pipeline orchestration
discover_servers.py        Find running vLLM endpoints on the cluster
serve.sh                   Launch instruct + embed servers
```

## Method recap

For each domain we discover a basis V ∈ ℝ^(d×K) of K named, interpretable
preference directions. Inference for one participant:

```
(per-trial projections)   u_t = V^T (φ(a_t) − φ(a'_t)) ∈ ℝ^K
(BTL likelihood)          z_t ~ Bernoulli(σ(u_t^T θ))
(estimator)               θ̂ = argmin_θ  −Σ_t log σ((2z_t−1) u_t^T θ)
                                       + λ/2 ‖θ‖²
                                       + μ/2 ‖θ − θ̄‖²
```

θ̄ is a feedback-derived prior built from the participant's natural-language
edits to model inferences (zero in the choice-only condition). Newton's
method, implemented twice — once in Python for offline analysis, once in
JavaScript for the in-browser fit. `web-interface/test_eval_parity.py`
verifies they agree to numerical tolerance.

## Pre-registrations

* Moral dilemmas: <https://aspredicted.org/z3qu4z.pdf>
* Movies: <https://aspredicted.org/n8m8yr.pdf>

Local copies live at `experiments/{dilemmas,movies}/prereg.md`.

## Citation

```bibtex
@inproceedings{wojtowicz2026weights,
  title  = {From Weights to Words: Expressing and Editing Preference Model
            Inferences in Natural Language},
  author = {Wojtowicz, Zachary and others},
  year   = {2026},
  booktitle = {Advances in Neural Information Processing Systems},
}
```
README_EOF

echo
echo "[migrate] wrote $TARGET/README.md"
echo "[migrate] done."
echo
echo "Next steps:"
echo "  cd $TARGET"
echo "  git init && git add -A && git commit -m 'Initial clean replication repo'"
