#!/bin/bash
# Parameter sweep for preference learning method.
# Runs pilot learning curves at various (D, lambda, alpha) settings
# and collects final-T results into a comparison CSV.
#
# Usage:
#   cd preference-learning-dev
#   bash experiments/sweep_params.sh

set -e

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$BASE_DIR"

PILOT_CSV="experiments/pilot/data.csv"
EMB_PARQUET="datasets/dailydilemmas/selected_actions-embedded.parquet"
DIRECTIONS="method_directions/outputs/dailydilemmas/directions.npz"
OID_COL="action_id"

SWEEP_DIR="experiments/pilot/sweep"
RESULTS_CSV="$SWEEP_DIR/sweep_results.csv"
mkdir -p "$SWEEP_DIR"

# Write CSV header
echo "run_id,n_dims,lambda,alpha,condition,fit,acc,ll,n_participants" > "$RESULTS_CSV"

# Helper: extract final-T results from a learning curves CSV and append to results
extract_results() {
    local run_id="$1"
    local ndims="$2"
    local lam="$3"
    local alpha="$4"
    local csv_path="$5"

    python3 - "$run_id" "$ndims" "$lam" "$alpha" "$csv_path" "$RESULTS_CSV" << 'PYEOF'
import sys, pandas as pd

run_id, ndims, lam, alpha, csv_path, out_path = sys.argv[1:7]
df = pd.read_csv(csv_path)

# Get final-t per participant
max_t = df.groupby('qualtrics_id')['t'].max()
final = df.merge(max_t.reset_index().rename(columns={'t': 'max_t'}), on='qualtrics_id')
final = final[final['t'] == final['max_t']]

rows = []
for cond in ['choice_only', 'inference_affirm', 'inference_categories']:
    cdf = final[final['condition'] == cond]
    if cdf.empty:
        continue
    n = cdf['qualtrics_id'].nunique()
    for fit in ['random_projection', 'projection_only', 'projection_alpha']:
        s = cdf[cdf['fit'] == fit]
        if s.empty:
            continue
        rows.append(f"{run_id},{ndims},{lam},{alpha},{cond},{fit},{s['test_acc'].mean():.4f},{s['test_ll'].mean():.4f},{n}")

with open(out_path, 'a') as f:
    f.write('\n'.join(rows) + '\n')
PYEOF
}

echo "=========================================="
echo "STEP 1: Sweep D (number of dimensions)"
echo "=========================================="
for D in 5 8 10; do
    RUN="d${D}"
    OUT="$SWEEP_DIR/$RUN"
    echo "  Running D=$D ..."
    python3 experiments/pilot/learning_curves.py \
        --pilot-csv "$PILOT_CSV" \
        --embeddings-parquet "$EMB_PARQUET" \
        --directions "$DIRECTIONS" \
        --option-id-column "$OID_COL" \
        --n-dims "$D" \
        --lambda-standard 0.01 --lambda-partial 0.01 \
        --alpha-deployed 0.5 \
        --output-dir "$OUT" 2>&1 | tail -5
    extract_results "$RUN" "$D" "0.01" "0.5" "$OUT/learning_curves.csv"
    echo "  Done: $RUN"
done

echo ""
echo "=========================================="
echo "STEP 2: Sweep lambda (at best D from step 1)"
echo "=========================================="
echo "  (Using D=10 as default; check step 1 results to adjust)"
BEST_D=10
for L in 0.001 0.01 0.1; do
    RUN="d${BEST_D}_l${L}"
    OUT="$SWEEP_DIR/$RUN"
    echo "  Running D=$BEST_D, lambda=$L ..."
    python3 experiments/pilot/learning_curves.py \
        --pilot-csv "$PILOT_CSV" \
        --embeddings-parquet "$EMB_PARQUET" \
        --directions "$DIRECTIONS" \
        --option-id-column "$OID_COL" \
        --n-dims "$BEST_D" \
        --lambda-standard "$L" --lambda-partial "$L" \
        --alpha-deployed 0.5 \
        --output-dir "$OUT" 2>&1 | tail -5
    extract_results "$RUN" "$BEST_D" "$L" "0.5" "$OUT/learning_curves.csv"
    echo "  Done: $RUN"
done

echo ""
echo "=========================================="
echo "STEP 3: Sweep alpha (feedback prior strength)"
echo "  On PILOT (sparse feedback):"
echo "=========================================="
BEST_L=0.01
for A in 0.0 0.1 0.5 1.0 2.0; do
    RUN="d${BEST_D}_l${BEST_L}_a${A}"
    OUT="$SWEEP_DIR/$RUN"
    echo "  Running D=$BEST_D, lambda=$BEST_L, alpha=$A ..."
    python3 experiments/pilot/learning_curves.py \
        --pilot-csv "$PILOT_CSV" \
        --embeddings-parquet "$EMB_PARQUET" \
        --directions "$DIRECTIONS" \
        --option-id-column "$OID_COL" \
        --n-dims "$BEST_D" \
        --lambda-standard "$BEST_L" --lambda-partial "$BEST_L" \
        --alpha-deployed "$A" \
        --output-dir "$OUT" 2>&1 | tail -5
    extract_results "$RUN" "$BEST_D" "$BEST_L" "$A" "$OUT/learning_curves.csv"
    echo "  Done: $RUN"
done

echo ""
echo "=========================================="
echo "STEP 4: Sweep alpha on SIMULATION (full feedback)"
echo "=========================================="
SIM_EMB="datasets/dailydilemmas/selected_actions-embedded.parquet"
SIM_BT="method_llm_gen/outputs/dailydilemmas/bt_scores.csv"
SIM_DIR="method_directions/outputs/dailydilemmas/directions.npz"
SIM_RESULTS="$SWEEP_DIR/sim_sweep_results.csv"
echo "run_id,n_dims,lambda,alpha,condition,fit,acc,ll,n_users" > "$SIM_RESULTS"

for A in 0.0 0.1 0.5 1.0 2.0 5.0; do
    RUN="sim_a${A}"
    OUT="$SWEEP_DIR/$RUN"
    echo "  Running simulation alpha=$A ..."
    python3 simulation/run_simulation.py \
        --embeddings-parquet "$SIM_EMB" \
        --bt-scores "$SIM_BT" \
        --directions "$SIM_DIR" \
        --option-id-column action_id \
        --n-dims "$BEST_D" \
        --lambda-standard "$BEST_L" --lambda-partial "$BEST_L" \
        --feedback-alpha "$A" \
        --output-dir "$OUT" \
        --num-users 100 --num-trials 20 --seed 42 2>&1 | tail -5

    # Extract simulation results from learning_curves.csv
    python3 - "$RUN" "$BEST_D" "$BEST_L" "$A" "$OUT/learning_curves.csv" "$SIM_RESULTS" << 'PYEOF'
import sys, pandas as pd

run_id, ndims, lam, alpha, csv_path, out_path = sys.argv[1:7]
df = pd.read_csv(csv_path)

# Get final checkpoint per user
max_t = df.groupby('user_id')['n_trials'].max()
final = df.merge(max_t.reset_index().rename(columns={'n_trials': 'max_t'}), on='user_id')
final = final[final['n_trials'] == final['max_t']]

rows = []
for cond in ['choice_only', 'inference_affirm', 'inference_categories']:
    cdf = final[final['condition'] == cond]
    if cdf.empty:
        continue
    n = cdf['user_id'].nunique()
    for fit in ['random_projection', 'projection_only', 'projection_alpha']:
        s = cdf[cdf['fit_type'] == fit]
        if s.empty:
            continue
        rows.append(f"{run_id},{ndims},{lam},{alpha},{cond},{fit},{s['test_acc'].mean():.4f},{s['test_ll'].mean():.4f},{n}")

with open(out_path, 'a') as f:
    f.write('\n'.join(rows) + '\n')
PYEOF
    echo "  Done: $RUN"
done

echo ""
echo "=========================================="
echo "STEP 5: Summary table"
echo "=========================================="

python3 - "$RESULTS_CSV" "$SIM_RESULTS" << 'PYEOF'
import pandas as pd
import sys

pilot_path, sim_path = sys.argv[1], sys.argv[2]

print("\n" + "="*80)
print("PILOT SWEEP RESULTS (inference_categories, projection_only vs random)")
print("="*80)
df = pd.read_csv(pilot_path)
ic = df[(df['condition'] == 'inference_categories')]
if not ic.empty:
    for run_id in ic['run_id'].unique():
        rdf = ic[ic['run_id'] == run_id]
        rand_acc = rdf[rdf['fit'] == 'random_projection']['acc'].values
        proj_acc = rdf[rdf['fit'] == 'projection_only']['acc'].values
        alpha_acc = rdf[rdf['fit'] == 'projection_alpha']['acc'].values
        rand_ll = rdf[rdf['fit'] == 'random_projection']['ll'].values
        proj_ll = rdf[rdf['fit'] == 'projection_only']['ll'].values
        alpha_ll = rdf[rdf['fit'] == 'projection_alpha']['ll'].values
        n = rdf['n_participants'].iloc[0]
        d, l, a = rdf[['n_dims', 'lambda', 'alpha']].iloc[0]
        print(f"  {run_id:25s}  D={int(d):2d}  l={l:.3f}  a={a:.1f}  n={int(n):2d}  "
              f"rand={rand_acc[0]:.3f}  proj={proj_acc[0]:.3f}  alpha={alpha_acc[0]:.3f}  "
              f"D_proj={proj_acc[0]-rand_acc[0]:+.3f}  D_alpha={alpha_acc[0]-rand_acc[0]:+.3f}  "
              f"ll_proj={proj_ll[0]:.4f}  ll_alpha={alpha_ll[0]:.4f}")

print("\n" + "="*80)
print("SIMULATION SWEEP RESULTS (inference_categories, projection_alpha)")
print("="*80)
df = pd.read_csv(sim_path)
ic = df[(df['condition'] == 'inference_categories')]
if not ic.empty:
    for run_id in ic['run_id'].unique():
        rdf = ic[ic['run_id'] == run_id]
        rand_acc = rdf[rdf['fit'] == 'random_projection']['acc'].values
        proj_acc = rdf[rdf['fit'] == 'projection_only']['acc'].values
        alpha_acc = rdf[rdf['fit'] == 'projection_alpha']['acc'].values
        rand_ll = rdf[rdf['fit'] == 'random_projection']['ll'].values
        alpha_ll = rdf[rdf['fit'] == 'projection_alpha']['ll'].values
        n = rdf['n_users'].iloc[0]
        d, l, a = rdf[['n_dims', 'lambda', 'alpha']].iloc[0]
        print(f"  {run_id:25s}  D={int(d):2d}  l={l:.3f}  a={a:.1f}  n={int(n):3d}  "
              f"rand={rand_acc[0]:.3f}  proj={proj_acc[0]:.3f}  alpha={alpha_acc[0]:.3f}  "
              f"D_proj={proj_acc[0]-rand_acc[0]:+.3f}  D_alpha={alpha_acc[0]-rand_acc[0]:+.3f}  "
              f"ll_alpha={alpha_ll[0]:.4f}")

print("\n" + "="*80)
print("BEST CONFIGURATIONS")
print("="*80)
# Best pilot config (by projection_only accuracy advantage over random)
pilot = pd.read_csv(pilot_path)
ic = pilot[pilot['condition'] == 'inference_categories']
if not ic.empty:
    pivoted = ic.pivot_table(index='run_id', columns='fit', values='acc')
    if 'projection_only' in pivoted.columns and 'random_projection' in pivoted.columns:
        pivoted['advantage'] = pivoted['projection_only'] - pivoted['random_projection']
        best = pivoted['advantage'].idxmax()
        best_row = ic[ic['run_id'] == best].iloc[0]
        print(f"  Best pilot (proj vs rand):  {best}  "
              f"D={int(best_row['n_dims'])}  l={best_row['lambda']}  "
              f"advantage={pivoted.loc[best, 'advantage']:+.3f}")

# Best sim config (by projection_alpha accuracy)
sim = pd.read_csv(sim_path)
ic_sim = sim[sim['condition'] == 'inference_categories']
if not ic_sim.empty:
    alpha_accs = ic_sim[ic_sim['fit'] == 'projection_alpha'].set_index('run_id')['acc']
    best_sim = alpha_accs.idxmax()
    best_sim_row = ic_sim[ic_sim['run_id'] == best_sim].iloc[0]
    print(f"  Best sim (alpha acc):      {best_sim}  "
          f"D={int(best_sim_row['n_dims'])}  l={best_sim_row['lambda']}  "
          f"a={best_sim_row['alpha']}  acc={alpha_accs[best_sim]:.3f}")

print()
PYEOF

echo ""
echo "Full results saved to:"
echo "  Pilot:      $RESULTS_CSV"
echo "  Simulation: $SIM_RESULTS"
echo "  Plots in:   $SWEEP_DIR/*/learning_curves.png"
echo "              $SWEEP_DIR/*/pilot_results.png"
