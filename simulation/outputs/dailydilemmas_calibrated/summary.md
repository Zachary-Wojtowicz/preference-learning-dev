# Simulation Summary (revamped)

Predicts the experimental DV: probability that a participant prefers the partial/projected K-dim summary over the unrestricted standard summary.

## Parameters

| Parameter | Value |
|-----------|-------|
| Users | 100 |
| Trials per user | 20 |
| Test pairs (held-out) | 200 |
| K (dimensions) | 20 |
| Top-K inferences visible | 5 |
| Participant noise (per-dim slip prob) | 0.1 |
| Beta (choice noise) | 2.0 |
| λ standard | 10.0 |
| λ partial  | 0.01 |
| γ (projection blend) | 0.75 |
| α (feedback strength) | 1.0 |
| Rating temperature τ | 5.0 |
| Top-N dims shown in summary | 10 |
| Seed | 42 |

## Predicted Rating (P[partial > standard])

Probability the simulated participant prefers the partial K-dim summary (with feedback re-weighting) over the standard summary. 0.5 = no effect; >0.5 = partial preferred.

| Condition | Mean rating | SD | Pct > 0.5 |
|-----------|-------------|----|-----------|
| choice_only | 0.504 | 0.158 | 52% |
| inference_affirm | 0.620 | 0.213 | 70% |
| inference_categories | 0.634 | 0.221 | 73% |

## Summary-Quality Means

Quality scores against ground-truth w*. Higher is better. `combined` = 0.5·spearman + 0.5·(2·top-N sign agreement − 1).

| Condition | Fit | spearman | topn_sign | topn_overlap | combined |
| --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.246 | 0.381 | 0.527 | 0.004 |
| choice_only | projected | 0.259 | 0.377 | 0.504 | 0.007 |
| choice_only | partial | 0.259 | 0.377 | 0.504 | 0.007 |
| choice_only | blend | 0.259 | 0.377 | 0.504 | 0.007 |
| inference_affirm | standard | 0.251 | 0.369 | 0.527 | -0.006 |
| inference_affirm | projected | 0.249 | 0.364 | 0.515 | -0.011 |
| inference_affirm | partial | 0.384 | 0.426 | 0.560 | 0.118 |
| inference_affirm | blend | 0.384 | 0.426 | 0.560 | 0.118 |
| inference_categories | standard | 0.239 | 0.361 | 0.532 | -0.020 |
| inference_categories | projected | 0.260 | 0.394 | 0.549 | 0.024 |
| inference_categories | partial | 0.378 | 0.432 | 0.552 | 0.121 |
| inference_categories | blend | 0.378 | 0.432 | 0.552 | 0.121 |

## Held-Out Choice Accuracy at T

| Condition | standard | projected | partial | blend | Δ blend−std |
|-----------|----------|-----------|---------|-------|------------|
| choice_only | 0.535 | 0.567 | 0.567 | 0.567 | +0.032 |
| inference_affirm | 0.541 | 0.567 | 0.566 | 0.566 | +0.025 |
| inference_categories | 0.536 | 0.579 | 0.567 | 0.567 | +0.031 |

## Held-Out Log-Likelihood at T

| Condition | LL standard | LL projected | LL partial | LL blend | Δ blend−std |
|-----------|-------------|--------------|------------|----------|------------|
| choice_only | -0.6919 | -0.9381 | -0.9381 | -0.8239 | -0.1320 |
| inference_affirm | -0.6919 | -0.9545 | -2.3629 | -1.8471 | -1.1552 |
| inference_categories | -0.6918 | -0.9196 | -2.7589 | -2.1528 | -1.4610 |

## Significance Tests (paired Wilcoxon)

Tests whether the predicted rating is reliably > 0.5 within each condition (i.e., the partial-K-dim summary wins) and whether inference conditions differ from choice_only.

| Comparison | n | mean | Wilcoxon p |
|------------|---|------|------------|
| choice_only vs 0.5 | 100 | 0.504 | 0.6951 |
| inference_affirm vs 0.5 | 100 | 0.620 | 0.0000 |
| inference_categories vs 0.5 | 100 | 0.634 | 0.0000 |
| inference_affirm vs choice_only | 100 | Δ=+0.116 | 0.0000 |
| inference_categories vs choice_only | 100 | Δ=+0.130 | 0.0000 |

## Learning Curves (test acc by trial count)

Mean held-out accuracy across users at each checkpoint. Should rise monotonically with more trials if learning is working.

| Condition | Fit | T=1 | T=5 | T=10 | T=15 | T=20 |
| --- | --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.507 | 0.513 | 0.530 | 0.533 | 0.535 |
| choice_only | projected | 0.514 | 0.533 | 0.549 | 0.561 | 0.567 |
| choice_only | partial | 0.514 | 0.533 | 0.549 | 0.561 | 0.567 |
| choice_only | blend | 0.514 | 0.533 | 0.548 | 0.560 | 0.567 |
| inference_affirm | standard | 0.498 | 0.512 | 0.524 | 0.535 | 0.541 |
| inference_affirm | projected | 0.505 | 0.533 | 0.540 | 0.559 | 0.567 |
| inference_affirm | partial | 0.514 | 0.544 | 0.555 | 0.566 | 0.566 |
| inference_affirm | blend | 0.514 | 0.545 | 0.555 | 0.566 | 0.566 |
| inference_categories | standard | 0.512 | 0.516 | 0.528 | 0.529 | 0.536 |
| inference_categories | projected | 0.518 | 0.535 | 0.551 | 0.560 | 0.579 |
| inference_categories | partial | 0.525 | 0.543 | 0.551 | 0.558 | 0.567 |
| inference_categories | blend | 0.525 | 0.543 | 0.551 | 0.558 | 0.567 |

## Go/No-Go Read

- Predicted win rate (other > standard) — choice_only: 52% · inference_affirm: 70% · inference_categories: 73%
- A meaningful experimental effect requires the inference conditions to be reliably above choice_only AND the Wilcoxon-vs-0.5 test to reach p<0.05 with the planned N.
- If the inference conditions don't outperform choice_only in this sim, sweep `--participant-noise` (try 0.0 / 0.15 / 0.30) and `--num-trials` to find the regime where the effect emerges.
