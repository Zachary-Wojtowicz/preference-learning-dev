# Pilot Calibration Report

- pilot file: `data.csv`
- N participants used: 47
- by condition: {'inference_categories': np.int64(30), 'choice_only': np.int64(13), 'inference_affirm': np.int64(4)}
- 5-fold stratified CV per participant
- λ_partial grid: 0.05,0.1,0.25,0.5,1.0,2.5,5.0
- multiplier-scale grid: 0.5,0.75,1.0,1.25,1.5
- α (feedback strength) grid: 0.0,0.25,0.5,0.75,1.0
- λ_standard (fixed): 10.0

## How to read

Two questions:

1. **Does the modified projection method (partial fit on Ũ = Λ⊙U) beat the standard kernel-logistic baseline?** — head-to-head Wilcoxon test on Δ-LL across participants.
2. **What are the best (λ, scale, α)?** — max held-out LL.

CV is within-participant (5-fold stratified by chosen side). Both fits are trained on each fold's train trials and scored on the same held-out test trials, so the comparison is perfectly paired at the participant × fold level.

## 1. Head-to-head: modified projection vs. standard kernel

Per-condition Wilcoxon test on **per-participant mean Δ-LL** (partial − standard). Δ > 0 means the modified projection predicted that participant's held-out choices better than the kernel baseline. Tests evaluated at the deployed experiment settings (λ_partial=0.05, scale=1.0, α=0.5) — the closest grid point to those is reported.

_Closest grid point to deployed defaults: λ=0.05, scale=1.0, α=0.5_

| Condition | n | mean LL std | mean LL part | mean Δ-LL | Wilcoxon p (Δ vs 0) | mean Δ-acc |
|---|---|---|---|---|---|---|
| choice_only | 13 | -0.6926 | -0.6522 | +0.0404 | 0.010 | +0.0154 |
| inference_affirm | 4 | -0.6921 | -0.6322 | +0.0599 | 0.250 | -0.0125 |
| inference_categories | 30 | -0.6923 | -0.6461 | +0.0462 | 0.000 | +0.0200 |

## 2. Best (λ, scale, α) per condition

Sorted by mean held-out LL of the partial fit. For `choice_only` participants there are no per-dim feedback clicks, so the partial fit collapses to the projected fit (Ũ = U) — α and scale don't change anything in that cell.

### choice_only (n=12, std baseline LL = -0.6926, acc = 0.618)

| rank | λ | scale | α | LL part | Δ-LL | acc part | Δ-acc |
|---|---|---|---|---|---|---|---|
| 1 | 0.05 | 0.5 | 0 | -0.6549 | +0.0377 | 0.630 | +0.012 |
| 2 | 0.05 | 1 | 0.75 | -0.6549 | +0.0377 | 0.630 | +0.012 |
| 3 | 0.05 | 0.5 | 0.25 | -0.6549 | +0.0377 | 0.630 | +0.012 |
| 4 | 0.05 | 1.5 | 1 | -0.6549 | +0.0377 | 0.630 | +0.012 |
| 5 | 0.05 | 1.5 | 0.75 | -0.6549 | +0.0377 | 0.630 | +0.012 |
| 6 | 0.05 | 1.5 | 0.5 | -0.6549 | +0.0377 | 0.630 | +0.012 |
| 7 | 0.05 | 1.5 | 0.25 | -0.6549 | +0.0377 | 0.630 | +0.012 |
| 8 | 0.05 | 1.5 | 0 | -0.6549 | +0.0377 | 0.630 | +0.012 |
| 9 | 0.05 | 1.25 | 1 | -0.6549 | +0.0377 | 0.630 | +0.012 |
| 10 | 0.05 | 1.25 | 0.5 | -0.6549 | +0.0377 | 0.630 | +0.012 |

### inference_affirm (n=4, std baseline LL = -0.6921, acc = 0.713)

| rank | λ | scale | α | LL part | Δ-LL | acc part | Δ-acc |
|---|---|---|---|---|---|---|---|
| 1 | 0.05 | 0.5 | 0 | -0.6285 | +0.0637 | 0.675 | -0.037 |
| 2 | 0.05 | 1 | 0 | -0.6285 | +0.0637 | 0.675 | -0.037 |
| 3 | 0.05 | 1.5 | 0 | -0.6285 | +0.0637 | 0.675 | -0.037 |
| 4 | 0.05 | 0.75 | 0 | -0.6285 | +0.0637 | 0.675 | -0.037 |
| 5 | 0.05 | 1.25 | 0 | -0.6285 | +0.0637 | 0.675 | -0.037 |
| 6 | 0.05 | 1.5 | 0.25 | -0.6289 | +0.0633 | 0.713 | +0.000 |
| 7 | 0.05 | 1.25 | 0.25 | -0.6293 | +0.0629 | 0.700 | -0.013 |
| 8 | 0.05 | 1 | 0.25 | -0.6297 | +0.0624 | 0.688 | -0.025 |
| 9 | 0.05 | 0.75 | 0.25 | -0.6303 | +0.0619 | 0.688 | -0.025 |
| 10 | 0.05 | 0.5 | 0.25 | -0.6309 | +0.0612 | 0.662 | -0.050 |

### inference_categories (n=29, std baseline LL = -0.6923, acc = 0.655)

| rank | λ | scale | α | LL part | Δ-LL | acc part | Δ-acc |
|---|---|---|---|---|---|---|---|
| 1 | 0.05 | 0.5 | 0 | -0.6414 | +0.0509 | 0.673 | +0.018 |
| 2 | 0.05 | 1 | 0 | -0.6414 | +0.0509 | 0.673 | +0.018 |
| 3 | 0.05 | 1.5 | 0 | -0.6414 | +0.0509 | 0.673 | +0.018 |
| 4 | 0.05 | 0.75 | 0 | -0.6414 | +0.0509 | 0.673 | +0.018 |
| 5 | 0.05 | 1.25 | 0 | -0.6414 | +0.0509 | 0.673 | +0.018 |
| 6 | 0.05 | 0.5 | 0.25 | -0.6432 | +0.0491 | 0.672 | +0.017 |
| 7 | 0.05 | 0.75 | 0.25 | -0.6435 | +0.0488 | 0.675 | +0.020 |
| 8 | 0.05 | 1 | 0.25 | -0.6438 | +0.0485 | 0.669 | +0.014 |
| 9 | 0.05 | 1.25 | 0.25 | -0.6442 | +0.0481 | 0.673 | +0.018 |
| 10 | 0.05 | 1.5 | 0.25 | -0.6446 | +0.0477 | 0.670 | +0.015 |

## 3. Reference baselines

- **Chance**: LL = ln(0.5) = −0.693, accuracy = 0.500
- **α=0 rows** in the per-condition tables are the *projected* fit (no feedback applied, just K-dim restriction). Compare the best α>0 row to the best α=0 row within a condition to see whether the feedback channel adds value on real human data.

### inference_affirm

  - Best α=0:   λ=0.05, scale=0.5 → LL = -0.6285, acc = 0.675
  - Best α>0:   λ=0.05, scale=1.5, α=0.25 → LL = -0.6289, acc = 0.713
  - **Δ LL (best feedback − best no-feedback): -0.0004** (feedback hurts or no help)

### inference_categories

  - Best α=0:   λ=0.05, scale=0.5 → LL = -0.6414, acc = 0.673
  - Best α>0:   λ=0.05, scale=0.5, α=0.25 → LL = -0.6432, acc = 0.672
  - **Δ LL (best feedback − best no-feedback): -0.0017** (feedback hurts or no help)

