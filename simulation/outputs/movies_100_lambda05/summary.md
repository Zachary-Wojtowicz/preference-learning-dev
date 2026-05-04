# Simulation Summary (revamped)

Predicts the experimental DV: probability that a participant prefers the partial/projected K-dim summary over the unrestricted standard summary.

## Parameters

| Parameter | Value |
|-----------|-------|
| Users | 100 |
| Trials per user | 20 |
| Test pairs (held-out) | 200 |
| K (dimensions) | 25 |
| Top-K inferences visible | 5 |
| Participant noise (per-dim slip prob) | 0.1 |
| Beta (choice noise) | 2.0 |
| λ standard | 10.0 |
| λ partial  | 0.5 |
| γ (projection blend) | 1.0 |
| α (feedback strength) | 1.0 |
| Rating temperature τ | 5.0 |
| Top-N dims shown in summary | 10 |
| Seed | 42 |

## Predicted Rating (P[partial > standard])

Probability the simulated participant prefers the partial K-dim summary (with feedback re-weighting) over the standard summary. 0.5 = no effect; >0.5 = partial preferred.

| Condition | Mean rating | SD | Pct > 0.5 |
|-----------|-------------|----|-----------|
| choice_only | 0.525 | 0.075 | 65% |
| inference_affirm | 0.601 | 0.156 | 76% |
| inference_categories | 0.569 | 0.182 | 68% |

## Summary-Quality Means

Quality scores against ground-truth w*. Higher is better. `combined` = 0.5·spearman + 0.5·(2·top-N sign agreement − 1).

| Condition | Fit | spearman | topn_sign | topn_overlap | combined |
| --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.412 | 0.476 | 0.444 | 0.182 |
| choice_only | projected | 0.422 | 0.492 | 0.451 | 0.203 |
| choice_only | partial | 0.422 | 0.492 | 0.451 | 0.203 |
| choice_only | blend | 0.422 | 0.492 | 0.451 | 0.203 |
| inference_affirm | standard | 0.409 | 0.483 | 0.441 | 0.187 |
| inference_affirm | projected | 0.425 | 0.502 | 0.453 | 0.214 |
| inference_affirm | partial | 0.530 | 0.514 | 0.485 | 0.279 |
| inference_affirm | blend | 0.530 | 0.514 | 0.485 | 0.279 |
| inference_categories | standard | 0.423 | 0.485 | 0.442 | 0.197 |
| inference_categories | projected | 0.434 | 0.496 | 0.452 | 0.213 |
| inference_categories | partial | 0.511 | 0.505 | 0.477 | 0.261 |
| inference_categories | blend | 0.511 | 0.505 | 0.477 | 0.261 |

## Held-Out Choice Accuracy at T

| Condition | standard | projected | partial | blend | Δ blend−std |
|-----------|----------|-----------|---------|-------|------------|
| choice_only | 0.658 | 0.716 | 0.716 | 0.716 | +0.058 |
| inference_affirm | 0.667 | 0.729 | 0.702 | 0.702 | +0.035 |
| inference_categories | 0.659 | 0.724 | 0.681 | 0.681 | +0.021 |

## Held-Out Log-Likelihood at T

| Condition | LL standard | LL projected | LL partial | LL blend | Δ blend−std |
|-----------|-------------|--------------|------------|----------|------------|
| choice_only | -0.6865 | -0.6276 | -0.6276 | -0.6276 | +0.0589 |
| inference_affirm | -0.6861 | -0.6240 | -0.6252 | -0.6252 | +0.0610 |
| inference_categories | -0.6866 | -0.6268 | -0.6315 | -0.6315 | +0.0552 |

## Significance Tests (paired Wilcoxon)

Tests whether the predicted rating is reliably > 0.5 within each condition (i.e., the partial-K-dim summary wins) and whether inference conditions differ from choice_only.

| Comparison | n | mean | Wilcoxon p |
|------------|---|------|------------|
| choice_only vs 0.5 | 100 | 0.525 | 0.0001 |
| inference_affirm vs 0.5 | 100 | 0.601 | 0.0000 |
| inference_categories vs 0.5 | 100 | 0.569 | 0.0003 |
| inference_affirm vs choice_only | 100 | Δ=+0.076 | 0.0000 |
| inference_categories vs choice_only | 100 | Δ=+0.044 | 0.0306 |

## Learning Curves (test acc by trial count)

Mean held-out accuracy across users at each checkpoint. Should rise monotonically with more trials if learning is working.

| Condition | Fit | T=1 | T=5 | T=10 | T=15 | T=20 |
| --- | --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.545 | 0.589 | 0.629 | 0.646 | 0.658 |
| choice_only | projected | 0.554 | 0.632 | 0.676 | 0.701 | 0.716 |
| choice_only | partial | 0.554 | 0.632 | 0.676 | 0.701 | 0.716 |
| choice_only | blend | 0.554 | 0.632 | 0.676 | 0.701 | 0.716 |
| inference_affirm | standard | 0.541 | 0.589 | 0.633 | 0.654 | 0.667 |
| inference_affirm | projected | 0.553 | 0.620 | 0.674 | 0.708 | 0.729 |
| inference_affirm | partial | 0.557 | 0.627 | 0.671 | 0.689 | 0.702 |
| inference_affirm | blend | 0.557 | 0.627 | 0.671 | 0.689 | 0.702 |
| inference_categories | standard | 0.540 | 0.584 | 0.618 | 0.641 | 0.659 |
| inference_categories | projected | 0.546 | 0.625 | 0.674 | 0.703 | 0.724 |
| inference_categories | partial | 0.553 | 0.610 | 0.649 | 0.668 | 0.681 |
| inference_categories | blend | 0.553 | 0.610 | 0.649 | 0.668 | 0.681 |

## Go/No-Go Read

- Predicted win rate (other > standard) — choice_only: 65% · inference_affirm: 76% · inference_categories: 68%
- A meaningful experimental effect requires the inference conditions to be reliably above choice_only AND the Wilcoxon-vs-0.5 test to reach p<0.05 with the planned N.
- If the inference conditions don't outperform choice_only in this sim, sweep `--participant-noise` (try 0.0 / 0.15 / 0.30) and `--num-trials` to find the regime where the effect emerges.
