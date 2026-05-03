# Calibration Grid — Weight-vec Sim

- domain options: movielens-32m-enriched-qwen3emb-100-embedded.parquet
- N users: 30, trials: 20, test pairs: 200
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
| 1 | 1 | 1.5 | 0.75 | 0.519 | -0.657 | 0.677 | 0.657 |
| 2 | 0.5 | 1.5 | 0.75 | 0.518 | -0.641 | 0.680 | 0.660 |
| 3 | 0.25 | 1 | 0.75 | 0.517 | -0.618 | 0.684 | 0.623 |
| 4 | 0.5 | 1.25 | 0.75 | 0.517 | -0.639 | 0.683 | 0.650 |
| 5 | 0.25 | 1.25 | 0.75 | 0.516 | -0.621 | 0.682 | 0.648 |
| 6 | 0.5 | 1 | 1 | 0.515 | -0.645 | 0.666 | 0.637 |
| 7 | 0.25 | 1.5 | 0.5 | 0.515 | -0.612 | 0.696 | 0.642 |
| 8 | 1 | 1.5 | 1 | 0.514 | -0.660 | 0.658 | 0.647 |

### Top 8 by `test_ll`

_Held-out test log-likelihood. Higher = better calibrated predictions on unseen pairs._

| rank | λ | scale | α | spearman | test_ll | test_acc | rating |
|---|---|---|---|---|---|---|---|
| 1 | 0.1 | 0.5 | 0 | 0.437 | -0.555 | 0.727 | 0.519 |
| 2 | 0.1 | 0.75 | 0 | 0.437 | -0.555 | 0.727 | 0.519 |
| 3 | 0.1 | 1.25 | 0 | 0.437 | -0.555 | 0.727 | 0.519 |
| 4 | 0.1 | 1.5 | 0 | 0.437 | -0.555 | 0.727 | 0.519 |
| 5 | 0.1 | 1 | 0 | 0.437 | -0.555 | 0.727 | 0.519 |
| 6 | 0.1 | 0.5 | 0.25 | 0.465 | -0.556 | 0.725 | 0.546 |
| 7 | 0.1 | 0.75 | 0.25 | 0.477 | -0.557 | 0.724 | 0.581 |
| 8 | 0.1 | 1 | 0.25 | 0.485 | -0.559 | 0.721 | 0.585 |

### Top 8 by `test_acc`

_Held-out test accuracy. Step function — less sensitive than LL — but easy to interpret._

| rank | λ | scale | α | spearman | test_ll | test_acc | rating |
|---|---|---|---|---|---|---|---|
| 1 | 0.5 | 1.25 | 0 | 0.433 | -0.623 | 0.735 | 0.509 |
| 2 | 0.5 | 1.5 | 0 | 0.433 | -0.623 | 0.735 | 0.509 |
| 3 | 0.5 | 0.75 | 0 | 0.433 | -0.623 | 0.735 | 0.509 |
| 4 | 0.5 | 1 | 0 | 0.433 | -0.623 | 0.735 | 0.509 |
| 5 | 0.5 | 0.5 | 0 | 0.433 | -0.623 | 0.735 | 0.509 |
| 6 | 1 | 0.5 | 0 | 0.426 | -0.649 | 0.733 | 0.505 |
| 7 | 1 | 0.75 | 0 | 0.426 | -0.649 | 0.733 | 0.505 |
| 8 | 1 | 1 | 0 | 0.426 | -0.649 | 0.733 | 0.505 |

### Top 8 by `rating_partial_vs_standard`

_Predicted experimental DV: P(participant prefers partial summary over standard). Aggregated by mapping summary quality through a sigmoid; this is the same DV the human pilot's evaluation screen estimates._

| rank | λ | scale | α | spearman | test_ll | test_acc | rating |
|---|---|---|---|---|---|---|---|
| 1 | 0.5 | 1.5 | 0.75 | 0.518 | -0.641 | 0.680 | 0.660 |
| 2 | 1 | 1.5 | 0.75 | 0.519 | -0.657 | 0.677 | 0.657 |
| 3 | 0.25 | 1.5 | 0.75 | 0.513 | -0.624 | 0.678 | 0.657 |
| 4 | 0.25 | 1.5 | 1 | 0.509 | -0.633 | 0.662 | 0.651 |
| 5 | 0.5 | 1.25 | 0.75 | 0.517 | -0.639 | 0.683 | 0.650 |
| 6 | 0.5 | 1.5 | 1 | 0.509 | -0.646 | 0.662 | 0.649 |
| 7 | 0.25 | 1.25 | 0.75 | 0.516 | -0.621 | 0.682 | 0.648 |
| 8 | 1 | 1.5 | 1 | 0.514 | -0.660 | 0.658 | 0.647 |

## Condition: inference_categories

### Top 8 by `spearman`

_Spearman rank correlation between the K-dim score vector and the ground-truth w*. Higher = the inferred preference vector is the right shape. **Most reliable** calibration target since it isolates 'is the model recovering the user's preferences?'._

| rank | λ | scale | α | spearman | test_ll | test_acc | rating |
|---|---|---|---|---|---|---|---|
| 1 | 1 | 1.5 | 1 | 0.617 | -0.655 | 0.684 | 0.730 |
| 2 | 1 | 1.5 | 0.75 | 0.617 | -0.653 | 0.698 | 0.738 |
| 3 | 2.5 | 1.5 | 1 | 0.613 | -0.673 | 0.677 | 0.724 |
| 4 | 0.5 | 1.5 | 0.75 | 0.612 | -0.633 | 0.704 | 0.725 |
| 5 | 0.25 | 1.5 | 0.75 | 0.611 | -0.611 | 0.706 | 0.705 |
| 6 | 1 | 1.25 | 1 | 0.610 | -0.656 | 0.685 | 0.719 |
| 7 | 0.5 | 1.25 | 0.75 | 0.608 | -0.632 | 0.703 | 0.718 |
| 8 | 2.5 | 1.5 | 0.75 | 0.607 | -0.672 | 0.692 | 0.737 |

### Top 8 by `test_ll`

_Held-out test log-likelihood. Higher = better calibrated predictions on unseen pairs._

| rank | λ | scale | α | spearman | test_ll | test_acc | rating |
|---|---|---|---|---|---|---|---|
| 1 | 0.1 | 1 | 0.25 | 0.529 | -0.550 | 0.730 | 0.628 |
| 2 | 0.1 | 1.25 | 0.25 | 0.539 | -0.550 | 0.727 | 0.640 |
| 3 | 0.1 | 0.75 | 0.25 | 0.513 | -0.550 | 0.727 | 0.604 |
| 4 | 0.1 | 1.5 | 0.25 | 0.550 | -0.551 | 0.727 | 0.667 |
| 5 | 0.1 | 0.5 | 0.25 | 0.496 | -0.552 | 0.726 | 0.577 |
| 6 | 0.1 | 0.5 | 0 | 0.446 | -0.556 | 0.719 | 0.513 |
| 7 | 0.1 | 1.25 | 0 | 0.446 | -0.556 | 0.719 | 0.513 |
| 8 | 0.1 | 1.5 | 0 | 0.446 | -0.556 | 0.719 | 0.513 |

### Top 8 by `test_acc`

_Held-out test accuracy. Step function — less sensitive than LL — but easy to interpret._

| rank | λ | scale | α | spearman | test_ll | test_acc | rating |
|---|---|---|---|---|---|---|---|
| 1 | 0.5 | 1.5 | 0.25 | 0.541 | -0.622 | 0.731 | 0.653 |
| 2 | 0.1 | 1 | 0.25 | 0.529 | -0.550 | 0.730 | 0.628 |
| 3 | 0.25 | 0.75 | 0.25 | 0.501 | -0.591 | 0.730 | 0.588 |
| 4 | 0.25 | 1.5 | 0.25 | 0.547 | -0.590 | 0.728 | 0.656 |
| 5 | 1 | 1.25 | 0.25 | 0.515 | -0.649 | 0.728 | 0.612 |
| 6 | 0.25 | 1 | 0.25 | 0.522 | -0.590 | 0.728 | 0.617 |
| 7 | 0.5 | 1.25 | 0.25 | 0.526 | -0.622 | 0.728 | 0.632 |
| 8 | 1 | 1.5 | 0.25 | 0.532 | -0.648 | 0.728 | 0.646 |

### Top 8 by `rating_partial_vs_standard`

_Predicted experimental DV: P(participant prefers partial summary over standard). Aggregated by mapping summary quality through a sigmoid; this is the same DV the human pilot's evaluation screen estimates._

| rank | λ | scale | α | spearman | test_ll | test_acc | rating |
|---|---|---|---|---|---|---|---|
| 1 | 5 | 1.5 | 0.75 | 0.604 | -0.681 | 0.691 | 0.741 |
| 2 | 1 | 1.5 | 0.75 | 0.617 | -0.653 | 0.698 | 0.738 |
| 3 | 2.5 | 1.5 | 0.75 | 0.607 | -0.672 | 0.692 | 0.737 |
| 4 | 5 | 1.5 | 1 | 0.605 | -0.681 | 0.674 | 0.732 |
| 5 | 1 | 1.5 | 1 | 0.617 | -0.655 | 0.684 | 0.730 |
| 6 | 2.5 | 1.25 | 1 | 0.606 | -0.674 | 0.677 | 0.728 |
| 7 | 5 | 1.25 | 0.75 | 0.591 | -0.682 | 0.689 | 0.728 |
| 8 | 2.5 | 1.25 | 0.75 | 0.593 | -0.673 | 0.692 | 0.727 |

## Joint-best recommendation (rank-sum across all 4 metrics)

Each (λ, scale, α) gets ranked by each metric within each condition; the rank-sum aggregates all four. Lowest rank-sum = settings that look good on all criteria simultaneously. Robust to a single metric being noisy.

### inference_affirm

| rank | λ | scale | α | rank-sum | spearman | test_ll | rating |
|---|---|---|---|---|---|---|---|
| 1 | 0.25 | 1.5 | 0.5 | 147 | 0.515 | -0.612 | 0.642 |
| 2 | 0.25 | 1.25 | 0.5 | 149 | 0.511 | -0.609 | 0.641 |
| 3 | 0.1 | 1.25 | 0.5 | 150 | 0.512 | -0.584 | 0.628 |
| 4 | 0.25 | 1.25 | 0.75 | 158 | 0.516 | -0.621 | 0.648 |
| 5 | 0.1 | 1.5 | 0.5 | 161 | 0.511 | -0.590 | 0.624 |

### inference_categories

| rank | λ | scale | α | rank-sum | spearman | test_ll | rating |
|---|---|---|---|---|---|---|---|
| 1 | 0.1 | 1.5 | 0.25 | 131 | 0.550 | -0.551 | 0.667 |
| 2 | 0.25 | 1.25 | 0.5 | 146 | 0.591 | -0.599 | 0.701 |
| 3 | 0.1 | 1.5 | 0.5 | 148 | 0.596 | -0.569 | 0.697 |
| 4 | 0.25 | 1.5 | 0.25 | 156 | 0.547 | -0.590 | 0.656 |
| 5 | 0.5 | 1.5 | 0.5 | 158 | 0.598 | -0.627 | 0.716 |

