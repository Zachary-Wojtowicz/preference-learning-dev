# Pilot Calibration Report

- pilot file: `data.csv`
- N participants used: 30 (inference_categories only)
- 5-fold stratified CV per participant
- λ grid: 0.05,0.1,0.25,0.5,1.0,2.5,5.0
- multiplier-scale grid: 0.5,0.75,1.0,1.25,1.5
- α (feedback strength) grid: 0.0,0.25,0.5,0.75,1.0

## How to read

Each (λ, s, α) combination is scored by within-participant cross-validated held-out **log-likelihood** and **accuracy**, averaged across all 30 pilot participants and all 5 folds. Higher = better. The test pairs are held out from training for that fold but come from the participant's own real trials — so this measures how well the partial fit predicts the participant's *own* unseen choices, not a synthetic ground truth.

### Top 10 by `test_ll`

_Mean held-out log-likelihood across folds and participants. **Primary calibration metric** — sensitive to confidence calibration and least dependent on the small per-fold N._

| rank | λ | scale | α | test_ll | test_acc |
|---|---|---|---|---|---|
| 1 | 0.05 | 0.5 | 0 | -0.6414 | 0.673 |
| 2 | 0.05 | 0.75 | 0 | -0.6414 | 0.673 |
| 3 | 0.05 | 1.25 | 0 | -0.6414 | 0.673 |
| 4 | 0.05 | 1.5 | 0 | -0.6414 | 0.673 |
| 5 | 0.05 | 1 | 0 | -0.6414 | 0.673 |
| 6 | 0.05 | 0.5 | 0.25 | -0.6426 | 0.670 |
| 7 | 0.05 | 0.75 | 0.25 | -0.6431 | 0.670 |
| 8 | 0.05 | 1 | 0.25 | -0.6437 | 0.672 |
| 9 | 0.05 | 0.5 | 0.5 | -0.6440 | 0.676 |
| 10 | 0.05 | 1.25 | 0.25 | -0.6446 | 0.672 |

### Top 10 by `test_acc`

_Mean held-out accuracy. Step function — easier to interpret but noisier at small fold sizes._

| rank | λ | scale | α | test_ll | test_acc |
|---|---|---|---|---|---|
| 1 | 0.25 | 0.5 | 0.5 | -0.6769 | 0.685 |
| 2 | 0.1 | 0.5 | 0.5 | -0.6605 | 0.685 |
| 3 | 0.5 | 0.5 | 0.5 | -0.6843 | 0.683 |
| 4 | 1 | 0.5 | 0.5 | -0.6885 | 0.683 |
| 5 | 5 | 0.5 | 0.5 | -0.6922 | 0.681 |
| 6 | 2.5 | 0.5 | 0.5 | -0.6912 | 0.681 |
| 7 | 0.1 | 1 | 0.5 | -0.6616 | 0.681 |
| 8 | 0.5 | 1 | 0.5 | -0.6844 | 0.680 |
| 9 | 0.1 | 0.75 | 0.5 | -0.6609 | 0.680 |
| 10 | 0.25 | 1 | 0.5 | -0.6772 | 0.680 |

### Joint best (rank-sum of LL + accuracy)

| rank | λ | scale | α | rank_sum | test_ll | test_acc |
|---|---|---|---|---|---|---|
| 1 | 0.05 | 0.75 | 0.5 | 20 | -0.6447 | 0.680 |
| 2 | 0.05 | 0.5 | 0.75 | 25 | -0.6455 | 0.679 |
| 3 | 0.05 | 1 | 0.5 | 27 | -0.6462 | 0.679 |
| 4 | 0.05 | 0.5 | 0.5 | 34 | -0.6440 | 0.676 |
| 5 | 0.1 | 0.5 | 0.5 | 36 | -0.6605 | 0.685 |
| 6 | 0.05 | 0.5 | 0 | 43 | -0.6414 | 0.673 |
| 7 | 0.05 | 0.75 | 0 | 43 | -0.6414 | 0.673 |
| 8 | 0.05 | 1.5 | 0 | 43 | -0.6414 | 0.673 |

## Reference baselines

- **Chance**: log-likelihood = ln(0.5) = −0.693, accuracy = 0.500
- **No-feedback baseline (α=0)**: rows in the table where α=0 represent the projected fit (feedback ignored). Compare best feedback-on rows to the best α=0 row to see whether feedback adds value on real human data.

  - Best α=0:   λ=0.05, scale=0.5 → test_ll = -0.6414, acc = 0.673
  - Best α>0:   λ=0.05, scale=0.5, α=0.25 → test_ll = -0.6426, acc = 0.670
  - **Δ LL (feedback − no-feedback): -0.0012** (feedback hurts on this pilot cell)

