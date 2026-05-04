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
| λ partial  | 0.01 |
| γ (projection blend) | 1.0 |
| α (feedback strength) | 1.0 |
| Rating temperature τ | 5.0 |
| Top-N dims shown in summary | 10 |
| Seed | 42 |

## Predicted Rating (P[partial > standard])

Probability the simulated participant prefers the partial K-dim summary (with feedback re-weighting) over the standard summary. 0.5 = no effect; >0.5 = partial preferred.

| Condition | Mean rating | SD | Pct > 0.5 |
|-----------|-------------|----|-----------|
| choice_only | 0.532 | 0.136 | 58% |
| inference_affirm | 0.543 | 0.197 | 59% |
| inference_categories | 0.489 | 0.220 | 51% |

## Summary-Quality Means

Quality scores against ground-truth w*. Higher is better. `combined` = 0.5·spearman + 0.5·(2·top-N sign agreement − 1).

| Condition | Fit | spearman | topn_sign | topn_overlap | combined |
| --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.412 | 0.476 | 0.444 | 0.182 |
| choice_only | projected | 0.429 | 0.495 | 0.456 | 0.210 |
| choice_only | partial | 0.429 | 0.495 | 0.456 | 0.210 |
| choice_only | blend | 0.429 | 0.495 | 0.456 | 0.210 |
| inference_affirm | standard | 0.409 | 0.483 | 0.441 | 0.187 |
| inference_affirm | projected | 0.458 | 0.507 | 0.461 | 0.236 |
| inference_affirm | partial | 0.464 | 0.496 | 0.470 | 0.228 |
| inference_affirm | blend | 0.464 | 0.496 | 0.470 | 0.228 |
| inference_categories | standard | 0.423 | 0.485 | 0.442 | 0.197 |
| inference_categories | projected | 0.446 | 0.507 | 0.471 | 0.230 |
| inference_categories | partial | 0.433 | 0.467 | 0.459 | 0.184 |
| inference_categories | blend | 0.433 | 0.467 | 0.459 | 0.184 |

## Held-Out Choice Accuracy at T

| Condition | standard | projected | partial | blend | Δ blend−std |
|-----------|----------|-----------|---------|-------|------------|
| choice_only | 0.658 | 0.708 | 0.708 | 0.708 | +0.049 |
| inference_affirm | 0.667 | 0.721 | 0.672 | 0.672 | +0.005 |
| inference_categories | 0.659 | 0.712 | 0.652 | 0.652 | -0.008 |

## Held-Out Log-Likelihood at T

| Condition | LL standard | LL projected | LL partial | LL blend | Δ blend−std |
|-----------|-------------|--------------|------------|----------|------------|
| choice_only | -0.6865 | -0.6190 | -0.6190 | -0.6190 | +0.0675 |
| inference_affirm | -0.6861 | -0.5858 | -1.2750 | -1.2750 | -0.5889 |
| inference_categories | -0.6866 | -0.6060 | -1.7847 | -1.7847 | -1.0980 |

## Significance Tests (paired Wilcoxon)

Tests whether the predicted rating is reliably > 0.5 within each condition (i.e., the partial-K-dim summary wins) and whether inference conditions differ from choice_only.

| Comparison | n | mean | Wilcoxon p |
|------------|---|------|------------|
| choice_only vs 0.5 | 100 | 0.532 | 0.0256 |
| inference_affirm vs 0.5 | 100 | 0.543 | 0.0303 |
| inference_categories vs 0.5 | 100 | 0.489 | 0.6648 |
| inference_affirm vs choice_only | 100 | Δ=+0.011 | 0.7310 |
| inference_categories vs choice_only | 100 | Δ=-0.044 | 0.0843 |

## Learning Curves (test acc by trial count)

Mean held-out accuracy across users at each checkpoint. Should rise monotonically with more trials if learning is working.

| Condition | Fit | T=1 | T=5 | T=10 | T=15 | T=20 |
| --- | --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.545 | 0.589 | 0.629 | 0.646 | 0.658 |
| choice_only | projected | 0.554 | 0.629 | 0.670 | 0.694 | 0.708 |
| choice_only | partial | 0.554 | 0.629 | 0.670 | 0.694 | 0.708 |
| choice_only | blend | 0.554 | 0.629 | 0.670 | 0.694 | 0.708 |
| inference_affirm | standard | 0.541 | 0.589 | 0.633 | 0.654 | 0.667 |
| inference_affirm | projected | 0.553 | 0.617 | 0.671 | 0.701 | 0.721 |
| inference_affirm | partial | 0.557 | 0.623 | 0.650 | 0.657 | 0.672 |
| inference_affirm | blend | 0.557 | 0.623 | 0.650 | 0.657 | 0.672 |
| inference_categories | standard | 0.540 | 0.584 | 0.618 | 0.641 | 0.659 |
| inference_categories | projected | 0.546 | 0.620 | 0.668 | 0.690 | 0.712 |
| inference_categories | partial | 0.553 | 0.606 | 0.630 | 0.639 | 0.652 |
| inference_categories | blend | 0.553 | 0.606 | 0.630 | 0.639 | 0.652 |

## Go/No-Go Read

- Predicted win rate (other > standard) — choice_only: 58% · inference_affirm: 59% · inference_categories: 51%
- A meaningful experimental effect requires the inference conditions to be reliably above choice_only AND the Wilcoxon-vs-0.5 test to reach p<0.05 with the planned N.
- If the inference conditions don't outperform choice_only in this sim, sweep `--participant-noise` (try 0.0 / 0.15 / 0.30) and `--num-trials` to find the regime where the effect emerges.
