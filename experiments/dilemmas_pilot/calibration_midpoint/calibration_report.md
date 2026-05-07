# Pilot Calibration Report

- pilot file: `data.csv`
- N participants used: 47
- by condition: {'inference_categories': np.int64(30), 'choice_only': np.int64(13), 'inference_affirm': np.int64(4)}
- 5-fold stratified CV per participant
- λ_partial grid: 0.001,0.005,0.01,0.025,0.05,0.1,0.25,0.5,1.0
- γ (projection degree) grid: 0.0,0.25,0.5,0.75,1.0
- α (feedback strength) grid: 0.0,0.25,0.5,0.75,1.0
- λ_standard (fixed): 10.0

## How to read

Two questions:

1. **Does the modified projection method (partial fit on Ũ = Λ⊙U) beat the standard kernel-logistic baseline?** — head-to-head Wilcoxon test on Δ-LL across participants.
2. **What are the best (λ, scale, α)?** — max held-out LL.

CV is within-participant (5-fold stratified by chosen side). Both fits are trained on each fold's train trials and scored on the same held-out test trials, so the comparison is perfectly paired at the participant × fold level.

## 1. Head-to-head: modified projection vs. standard kernel

Per-condition Wilcoxon test on **per-participant mean Δ-LL** (blend − standard). Δ > 0 means the blended model predicted that participant's held-out choices better than the kernel baseline. Tests evaluated at the deployed experiment settings (λ_partial=0.05, γ=1.0, α=0.5) — the closest grid point to those is reported.

_Closest grid point to deployed defaults: λ=0.05, γ=1.0, α=0.5_

| Condition | n | mean LL std | mean LL part | mean Δ-LL | Wilcoxon p (Δ vs 0) | mean Δ-acc |
|---|---|---|---|---|---|---|
| choice_only | 13 | -0.6926 | -0.6522 | +0.0404 | 0.010 | +0.0154 |
| inference_affirm | 4 | -0.6921 | -0.6315 | +0.0606 | 0.125 | -0.0375 |
| inference_categories | 30 | -0.6923 | -0.6652 | +0.0271 | 0.036 | -0.0233 |

## 2. Best (λ, γ, α) per condition

Sorted by mean held-out LL of the blended fit. For `choice_only` participants there are no per-dim feedback clicks, so the partial fit collapses to the projected fit (Ũ = U) — α doesn't change anything in that cell.

### choice_only (n=12, std baseline LL = -0.6926, acc = 0.618)

| rank | λ | γ | α | LL blend | Δ-LL | acc blend | Δ-acc |
|---|---|---|---|---|---|---|---|
| 1 | 0.01 | 1 | 1 | -0.6426 | +0.0500 | 0.623 | +0.005 |
| 2 | 0.01 | 1 | 0 | -0.6426 | +0.0500 | 0.623 | +0.005 |
| 3 | 0.01 | 1 | 0.25 | -0.6426 | +0.0500 | 0.623 | +0.005 |
| 4 | 0.01 | 1 | 0.5 | -0.6426 | +0.0500 | 0.623 | +0.005 |
| 5 | 0.01 | 1 | 0.75 | -0.6426 | +0.0500 | 0.623 | +0.005 |
| 6 | 0.01 | 0.75 | 1 | -0.6439 | +0.0487 | 0.623 | +0.005 |
| 7 | 0.01 | 0.75 | 0.5 | -0.6439 | +0.0487 | 0.623 | +0.005 |
| 8 | 0.01 | 0.75 | 0.25 | -0.6439 | +0.0487 | 0.623 | +0.005 |
| 9 | 0.01 | 0.75 | 0 | -0.6439 | +0.0487 | 0.623 | +0.005 |
| 10 | 0.01 | 0.75 | 0.75 | -0.6439 | +0.0487 | 0.623 | +0.005 |

### inference_affirm (n=4, std baseline LL = -0.6921, acc = 0.713)

| rank | λ | γ | α | LL blend | Δ-LL | acc blend | Δ-acc |
|---|---|---|---|---|---|---|---|
| 1 | 0.001 | 0.75 | 0 | -0.5172 | +0.1749 | 0.713 | +0.000 |
| 2 | 0.001 | 1 | 0 | -0.5207 | +0.1714 | 0.713 | +0.000 |
| 3 | 0.001 | 0.75 | 0.25 | -0.5257 | +0.1664 | 0.713 | +0.000 |
| 4 | 0.001 | 1 | 0.25 | -0.5314 | +0.1608 | 0.713 | +0.000 |
| 5 | 0.005 | 1 | 0 | -0.5358 | +0.1563 | 0.688 | -0.025 |
| 6 | 0.001 | 0.5 | 0 | -0.5365 | +0.1556 | 0.713 | +0.000 |
| 7 | 0.005 | 1 | 0.25 | -0.5415 | +0.1506 | 0.662 | -0.050 |
| 8 | 0.001 | 0.5 | 0.25 | -0.5428 | +0.1493 | 0.713 | +0.000 |
| 9 | 0.001 | 0.75 | 0.5 | -0.5455 | +0.1467 | 0.688 | -0.025 |
| 10 | 0.005 | 1 | 0.5 | -0.5499 | +0.1422 | 0.662 | -0.050 |

### inference_categories (n=29, std baseline LL = -0.6923, acc = 0.655)

| rank | λ | γ | α | LL blend | Δ-LL | acc blend | Δ-acc |
|---|---|---|---|---|---|---|---|
| 1 | 0.01 | 1 | 0 | -0.6189 | +0.0734 | 0.663 | +0.008 |
| 2 | 0.01 | 0.75 | 0 | -0.6239 | +0.0684 | 0.663 | +0.008 |
| 3 | 0.005 | 0.75 | 0 | -0.6245 | +0.0678 | 0.646 | -0.009 |
| 4 | 0.025 | 1 | 0 | -0.6264 | +0.0659 | 0.670 | +0.015 |
| 5 | 0.005 | 1 | 0 | -0.6301 | +0.0622 | 0.646 | -0.009 |
| 6 | 0.005 | 0.5 | 0 | -0.6309 | +0.0614 | 0.648 | -0.007 |
| 7 | 0.025 | 0.75 | 0 | -0.6368 | +0.0555 | 0.670 | +0.015 |
| 8 | 0.01 | 0.5 | 0 | -0.6370 | +0.0553 | 0.663 | +0.008 |
| 9 | 0.05 | 1 | 0 | -0.6414 | +0.0509 | 0.673 | +0.018 |
| 10 | 0.025 | 1 | 0.25 | -0.6424 | +0.0499 | 0.648 | -0.007 |

## 3. Reference baselines

- **Chance**: LL = ln(0.5) = −0.693, accuracy = 0.500
- **α=0 rows** in the per-condition tables are the *projected* fit (no feedback applied, just K-dim restriction). Compare the best α>0 row to the best α=0 row within a condition to see whether the feedback channel adds value on real human data.

### inference_affirm

  - Best α=0:   λ=0.001, γ=0.75 → LL = -0.5172, acc = 0.713
  - Best α>0:   λ=0.001, γ=0.75, α=0.25 → LL = -0.5257, acc = 0.713
  - **Δ LL (best feedback − best no-feedback): -0.0085** (feedback hurts or no help)

### inference_categories

  - Best α=0:   λ=0.01, γ=1 → LL = -0.6189, acc = 0.663
  - Best α>0:   λ=0.025, γ=1, α=0.25 → LL = -0.6424, acc = 0.648
  - **Δ LL (best feedback − best no-feedback): -0.0235** (feedback hurts or no help)

