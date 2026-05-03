# Calibration Grid — Weight-vec Sim

- domain options: selected_actions-embedded.parquet
- N users: 30, trials: 20, test pairs: 100
- λ grid: 0.1,0.25,0.5,1.0,2.5,5.0
- multiplier-scale grid: 0.5,0.75,1.0,1.25,1.5
- α (feedback strength) grid: 0.0,0.25,0.5,0.75,1.0

## How to read

Each section ranks (λ, scale, α) settings within a condition by a particular criterion. The 'partial' fit is the one whose parameters we're calibrating; 'standard' (kernel) and 'projected' rows are reference baselines.

## Condition: inference_affirm

### Top 8 by `spearman`

_Spearman rank correlation between the K-dim score vector and the ground-truth w*. Higher = the inferred preference vector is the right shape. **Most reliable** calibration target since it isolates 'is the model recovering the user's preferences?'._

| rank | λ | scale | α | spearman | test_ll | test_acc | rating |
|---|---|---|---|---|---|---|---|
| 1 | 0.25 | 1 | 1 | 0.234 | -0.676 | 0.674 | 0.555 |
| 2 | 0.5 | 1 | 1 | 0.229 | -0.684 | 0.668 | 0.561 |
| 3 | 0.1 | 1 | 0.75 | 0.229 | -0.656 | 0.684 | 0.544 |
| 4 | 0.5 | 1.25 | 1 | 0.229 | -0.684 | 0.656 | 0.557 |
| 5 | 0.1 | 1 | 1 | 0.229 | -0.659 | 0.684 | 0.558 |
| 6 | 2.5 | 1 | 1 | 0.229 | -0.691 | 0.659 | 0.567 |
| 7 | 1 | 1 | 1 | 0.229 | -0.688 | 0.660 | 0.560 |
| 8 | 2.5 | 1.25 | 1 | 0.228 | -0.691 | 0.651 | 0.574 |

### Top 8 by `test_ll`

_Held-out test log-likelihood. Higher = better calibrated predictions on unseen pairs._

| rank | λ | scale | α | spearman | test_ll | test_acc | rating |
|---|---|---|---|---|---|---|---|
| 1 | 0.1 | 0.5 | 0 | 0.198 | -0.647 | 0.684 | 0.533 |
| 2 | 0.1 | 0.75 | 0 | 0.198 | -0.647 | 0.684 | 0.533 |
| 3 | 0.1 | 1.25 | 0 | 0.198 | -0.647 | 0.684 | 0.533 |
| 4 | 0.1 | 1.5 | 0 | 0.198 | -0.647 | 0.684 | 0.533 |
| 5 | 0.1 | 1 | 0 | 0.198 | -0.647 | 0.684 | 0.533 |
| 6 | 0.1 | 0.5 | 0.25 | 0.204 | -0.649 | 0.684 | 0.542 |
| 7 | 0.1 | 0.75 | 0.25 | 0.204 | -0.649 | 0.683 | 0.536 |
| 8 | 0.1 | 1 | 0.25 | 0.214 | -0.649 | 0.685 | 0.535 |

### Top 8 by `test_acc`

_Held-out test accuracy. Step function — less sensitive than LL — but easy to interpret._

| rank | λ | scale | α | spearman | test_ll | test_acc | rating |
|---|---|---|---|---|---|---|---|
| 1 | 0.1 | 1 | 0.5 | 0.223 | -0.652 | 0.689 | 0.541 |
| 2 | 0.1 | 0.5 | 0.75 | 0.214 | -0.655 | 0.688 | 0.527 |
| 3 | 0.25 | 1.25 | 0.5 | 0.213 | -0.672 | 0.688 | 0.531 |
| 4 | 0.1 | 0.75 | 0.5 | 0.216 | -0.652 | 0.687 | 0.542 |
| 5 | 0.25 | 1 | 0.5 | 0.211 | -0.672 | 0.687 | 0.524 |
| 6 | 0.1 | 0.75 | 0.75 | 0.223 | -0.655 | 0.687 | 0.541 |
| 7 | 0.1 | 1.25 | 0.5 | 0.224 | -0.653 | 0.687 | 0.537 |
| 8 | 0.1 | 1.5 | 0.25 | 0.215 | -0.650 | 0.687 | 0.543 |

### Top 8 by `rating_partial_vs_standard`

_Predicted experimental DV: P(participant prefers partial summary over standard). Aggregated by mapping summary quality through a sigmoid; this is the same DV the human pilot's evaluation screen estimates._

| rank | λ | scale | α | spearman | test_ll | test_acc | rating |
|---|---|---|---|---|---|---|---|
| 1 | 5 | 1.25 | 1 | 0.225 | -0.692 | 0.650 | 0.575 |
| 2 | 2.5 | 1.25 | 1 | 0.228 | -0.691 | 0.651 | 0.574 |
| 3 | 1 | 1.5 | 1 | 0.214 | -0.688 | 0.648 | 0.570 |
| 4 | 2.5 | 1.5 | 1 | 0.215 | -0.691 | 0.646 | 0.569 |
| 5 | 5 | 1.5 | 1 | 0.215 | -0.692 | 0.644 | 0.569 |
| 6 | 2.5 | 1 | 1 | 0.229 | -0.691 | 0.659 | 0.567 |
| 7 | 5 | 1 | 1 | 0.226 | -0.692 | 0.657 | 0.566 |
| 8 | 1 | 1.25 | 1 | 0.225 | -0.688 | 0.655 | 0.565 |

## Condition: inference_categories

### Top 8 by `spearman`

_Spearman rank correlation between the K-dim score vector and the ground-truth w*. Higher = the inferred preference vector is the right shape. **Most reliable** calibration target since it isolates 'is the model recovering the user's preferences?'._

| rank | λ | scale | α | spearman | test_ll | test_acc | rating |
|---|---|---|---|---|---|---|---|
| 1 | 0.5 | 0.75 | 0.25 | 0.263 | -0.679 | 0.716 | 0.517 |
| 2 | 1 | 0.75 | 0.25 | 0.261 | -0.686 | 0.715 | 0.516 |
| 3 | 0.1 | 1.25 | 0 | 0.261 | -0.640 | 0.716 | 0.547 |
| 4 | 0.1 | 1.5 | 0 | 0.261 | -0.640 | 0.716 | 0.547 |
| 5 | 0.1 | 0.5 | 0 | 0.261 | -0.640 | 0.716 | 0.547 |
| 6 | 0.1 | 0.75 | 0 | 0.261 | -0.640 | 0.716 | 0.547 |
| 7 | 0.1 | 1 | 0 | 0.261 | -0.640 | 0.716 | 0.547 |
| 8 | 0.25 | 0.5 | 0.25 | 0.260 | -0.667 | 0.718 | 0.536 |

### Top 8 by `test_ll`

_Held-out test log-likelihood. Higher = better calibrated predictions on unseen pairs._

| rank | λ | scale | α | spearman | test_ll | test_acc | rating |
|---|---|---|---|---|---|---|---|
| 1 | 0.1 | 0.5 | 0 | 0.261 | -0.640 | 0.716 | 0.547 |
| 2 | 0.1 | 0.75 | 0 | 0.261 | -0.640 | 0.716 | 0.547 |
| 3 | 0.1 | 1.25 | 0 | 0.261 | -0.640 | 0.716 | 0.547 |
| 4 | 0.1 | 1.5 | 0 | 0.261 | -0.640 | 0.716 | 0.547 |
| 5 | 0.1 | 1 | 0 | 0.261 | -0.640 | 0.716 | 0.547 |
| 6 | 0.1 | 0.5 | 0.25 | 0.259 | -0.642 | 0.721 | 0.541 |
| 7 | 0.1 | 0.75 | 0.25 | 0.255 | -0.642 | 0.721 | 0.538 |
| 8 | 0.1 | 1 | 0.25 | 0.256 | -0.643 | 0.720 | 0.530 |

### Top 8 by `test_acc`

_Held-out test accuracy. Step function — less sensitive than LL — but easy to interpret._

| rank | λ | scale | α | spearman | test_ll | test_acc | rating |
|---|---|---|---|---|---|---|---|
| 1 | 0.1 | 0.5 | 0.25 | 0.259 | -0.642 | 0.721 | 0.541 |
| 2 | 0.1 | 0.75 | 0.25 | 0.255 | -0.642 | 0.721 | 0.538 |
| 3 | 0.25 | 0.5 | 0.5 | 0.249 | -0.669 | 0.721 | 0.522 |
| 4 | 0.1 | 1 | 0.25 | 0.256 | -0.643 | 0.720 | 0.530 |
| 5 | 0.5 | 0.5 | 0.5 | 0.254 | -0.680 | 0.720 | 0.513 |
| 6 | 0.1 | 1.25 | 0.25 | 0.252 | -0.643 | 0.718 | 0.526 |
| 7 | 1 | 0.5 | 0.5 | 0.254 | -0.686 | 0.718 | 0.514 |
| 8 | 0.25 | 0.75 | 0.25 | 0.259 | -0.667 | 0.718 | 0.519 |

### Top 8 by `rating_partial_vs_standard`

_Predicted experimental DV: P(participant prefers partial summary over standard). Aggregated by mapping summary quality through a sigmoid; this is the same DV the human pilot's evaluation screen estimates._

| rank | λ | scale | α | spearman | test_ll | test_acc | rating |
|---|---|---|---|---|---|---|---|
| 1 | 0.1 | 0.5 | 0 | 0.261 | -0.640 | 0.716 | 0.547 |
| 2 | 0.1 | 0.75 | 0 | 0.261 | -0.640 | 0.716 | 0.547 |
| 3 | 0.1 | 1.25 | 0 | 0.261 | -0.640 | 0.716 | 0.547 |
| 4 | 0.1 | 1.5 | 0 | 0.261 | -0.640 | 0.716 | 0.547 |
| 5 | 0.1 | 1 | 0 | 0.261 | -0.640 | 0.716 | 0.547 |
| 6 | 0.1 | 0.5 | 0.25 | 0.259 | -0.642 | 0.721 | 0.541 |
| 7 | 0.1 | 0.75 | 0.25 | 0.255 | -0.642 | 0.721 | 0.538 |
| 8 | 0.25 | 0.5 | 0.25 | 0.260 | -0.667 | 0.718 | 0.536 |

## Joint-best recommendation (rank-sum across all 4 metrics)

Each (λ, scale, α) gets ranked by each metric within each condition; the rank-sum aggregates all four. Lowest rank-sum = settings that look good on all criteria simultaneously. Robust to a single metric being noisy.

### inference_affirm

| rank | λ | scale | α | rank-sum | spearman | test_ll | rating |
|---|---|---|---|---|---|---|---|
| 1 | 0.1 | 1 | 1 | 70 | 0.229 | -0.659 | 0.558 |
| 2 | 0.1 | 0.75 | 1 | 82 | 0.227 | -0.658 | 0.551 |
| 3 | 0.1 | 1 | 0.75 | 83 | 0.229 | -0.656 | 0.544 |
| 4 | 0.1 | 1 | 0.5 | 83 | 0.223 | -0.652 | 0.541 |
| 5 | 0.1 | 1.5 | 0.5 | 91 | 0.221 | -0.653 | 0.544 |

### inference_categories

| rank | λ | scale | α | rank-sum | spearman | test_ll | rating |
|---|---|---|---|---|---|---|---|
| 1 | 0.1 | 0.5 | 0.25 | 31 | 0.259 | -0.642 | 0.541 |
| 2 | 0.1 | 0.5 | 0 | 36 | 0.261 | -0.640 | 0.547 |
| 3 | 0.1 | 0.75 | 0 | 36 | 0.261 | -0.640 | 0.547 |
| 4 | 0.1 | 1 | 0 | 36 | 0.261 | -0.640 | 0.547 |
| 5 | 0.1 | 1.25 | 0 | 36 | 0.261 | -0.640 | 0.547 |

