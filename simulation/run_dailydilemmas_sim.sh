#!/usr/bin/env bash
# Run the simulation for dailydilemmas with parameters matching the
# experimental config in web-interface/outputs/dailydilemmas/experiment_config.json.
#
# Outputs go to simulation/outputs/dailydilemmas/:
#   - per_user_per_condition.csv  (final-T metrics, one row per user x condition)
#   - learning_curves.csv         (LOO accuracy/LL at every checkpoint)
#   - summary.md                  (markdown summary table)
#   - predicted_dv.png            (predicted experimental DV per condition)
#   - loo_comparison.png          (LOO accuracy by fit type, reproducible from data)
#   - learning_curves.png         (accuracy/LL vs trials, all conditions)
#   - user_profiles.json          (synthetic w* per user)

set -euo pipefail

cd "$(dirname "$0")/.."

python simulation/run_simulation.py \
    --embeddings-parquet datasets/dailydilemmas/selected_actions-embedded.parquet \
    --bt-scores method_llm_gen/outputs/dailydilemmas/bt_scores.csv \
    --directions method_directions/outputs/dailydilemmas/directions.npz \
    --output-dir simulation/outputs/dailydilemmas \
    --option-id-column action_id \
    --predefined-pairs datasets/dailydilemmas/predefined_pairs.json \
    --n-dims 10 \
    --num-users 100 \
    --num-trials 20 \
    --top-k-inferences 3 \
    --lambda-partial 0.01 \
    --feedback-alpha 1.0 \
    --beta 2.0 \
    --participant-noise 0.10 \
    --multiplier-scale 1.0 \
    --seed 42

echo
echo "Done. See simulation/outputs/dailydilemmas/summary.md for results."
