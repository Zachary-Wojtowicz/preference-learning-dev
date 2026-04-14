#!/usr/bin/env bash
# run_pipeline.sh <name> <raw_dirs_args...>
# Runs all three pipeline stages for one dataset / variety slice.
# Usage:
#   ./method_pca/run_pipeline.sh pinot_noir \
#       --input-parquet datasets/wine-130k_embedded.parquet \
#       --filter-column variety --filter-value "Pinot Noir" \
#       --pca-components 10 --ica-components 10 \
#       --label-column title --domain-hint "Pinot Noir tasting notes"

set -euo pipefail

NAME="$1"; shift
OUTDIR="method_pca/outputs/${NAME}"
PY=".venv/bin/python"

echo "=== [$NAME] Step 1: raw directions ==="
$PY method_pca/raw_directions.py --output-dir "$OUTDIR" "$@"

echo "=== [$NAME] Step 2: label directions ==="
$PY method_pca/label_directions.py \
    --directions-json "$OUTDIR/directions.json" \
    --output-json "$OUTDIR/labeled_directions.json"

echo "=== [$NAME] Step 3: match & check ==="
$PY method_pca/match_and_check.py \
    --labeled-json "$OUTDIR/labeled_directions.json" \
    --output-json "$OUTDIR/match_report.json" \
    --output-md "$OUTDIR/match_report.md"

echo "=== [$NAME] Done → $OUTDIR ==="
