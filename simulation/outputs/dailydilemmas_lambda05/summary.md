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
| λ partial  | 0.5 |
| γ (projection blend) | 0.75 |
| α (feedback strength) | 1.0 |
| Rating temperature τ | 5.0 |
| Top-N dims shown in summary | 10 |
| Seed | 42 |

## Predicted Rating (P[partial > standard])

Probability the simulated participant prefers the partial K-dim summary (with feedback re-weighting) over the standard summary. 0.5 = no effect; >0.5 = partial preferred.

| Condition | Mean rating | SD | Pct > 0.5 |
|-----------|-------------|----|-----------|
| choice_only | 0.508 | 0.072 | 59% |
| inference_affirm | 0.727 | 0.171 | 88% |
| inference_categories | 0.721 | 0.169 | 90% |

## Summary-Quality Means

Quality scores against ground-truth w*. Higher is better. `combined` = 0.5·spearman + 0.5·(2·top-N sign agreement − 1).

| Condition | Fit | spearman | topn_sign | topn_overlap | combined |
| --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.246 | 0.381 | 0.527 | 0.004 |
| choice_only | projected | 0.254 | 0.383 | 0.532 | 0.010 |
| choice_only | partial | 0.254 | 0.383 | 0.532 | 0.010 |
| choice_only | blend | 0.254 | 0.383 | 0.532 | 0.010 |
| inference_affirm | standard | 0.251 | 0.369 | 0.527 | -0.006 |
| inference_affirm | projected | 0.249 | 0.374 | 0.524 | -0.001 |
| inference_affirm | partial | 0.483 | 0.487 | 0.586 | 0.229 |
| inference_affirm | blend | 0.483 | 0.487 | 0.586 | 0.229 |
| inference_categories | standard | 0.239 | 0.361 | 0.532 | -0.020 |
| inference_categories | projected | 0.248 | 0.371 | 0.542 | -0.005 |
| inference_categories | partial | 0.448 | 0.480 | 0.583 | 0.204 |
| inference_categories | blend | 0.448 | 0.480 | 0.583 | 0.204 |

## Held-Out Choice Accuracy at T

| Condition | standard | projected | partial | blend | Δ blend−std |
|-----------|----------|-----------|---------|-------|------------|
| choice_only | 0.535 | 0.568 | 0.568 | 0.566 | +0.030 |
| inference_affirm | 0.541 | 0.566 | 0.582 | 0.582 | +0.042 |
| inference_categories | 0.536 | 0.572 | 0.578 | 0.578 | +0.042 |

## Held-Out Log-Likelihood at T

| Condition | LL standard | LL projected | LL partial | LL blend | Δ blend−std |
|-----------|-------------|--------------|------------|----------|------------|
| choice_only | -0.6919 | -0.6806 | -0.6806 | -0.6823 | +0.0096 |
| inference_affirm | -0.6919 | -0.6810 | -0.6750 | -0.6775 | +0.0144 |
| inference_categories | -0.6918 | -0.6791 | -0.6755 | -0.6776 | +0.0142 |

## Significance Tests (paired Wilcoxon)

Tests whether the predicted rating is reliably > 0.5 within each condition (i.e., the partial-K-dim summary wins) and whether inference conditions differ from choice_only.

| Comparison | n | mean | Wilcoxon p |
|------------|---|------|------------|
| choice_only vs 0.5 | 100 | 0.508 | 0.0356 |
| inference_affirm vs 0.5 | 100 | 0.727 | 0.0000 |
| inference_categories vs 0.5 | 100 | 0.721 | 0.0000 |
| inference_affirm vs choice_only | 100 | Δ=+0.220 | 0.0000 |
| inference_categories vs choice_only | 100 | Δ=+0.213 | 0.0000 |

## Learning Curves (test acc by trial count)

Mean held-out accuracy across users at each checkpoint. Should rise monotonically with more trials if learning is working.

| Condition | Fit | T=1 | T=5 | T=10 | T=15 | T=20 |
| --- | --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.507 | 0.513 | 0.530 | 0.533 | 0.535 |
| choice_only | projected | 0.514 | 0.531 | 0.549 | 0.564 | 0.568 |
| choice_only | partial | 0.514 | 0.531 | 0.549 | 0.564 | 0.568 |
| choice_only | blend | 0.514 | 0.530 | 0.550 | 0.563 | 0.566 |
| inference_affirm | standard | 0.498 | 0.512 | 0.524 | 0.535 | 0.541 |
| inference_affirm | projected | 0.505 | 0.532 | 0.544 | 0.558 | 0.566 |
| inference_affirm | partial | 0.514 | 0.551 | 0.565 | 0.575 | 0.582 |
| inference_affirm | blend | 0.514 | 0.551 | 0.566 | 0.577 | 0.582 |
| inference_categories | standard | 0.512 | 0.516 | 0.528 | 0.529 | 0.536 |
| inference_categories | projected | 0.518 | 0.534 | 0.546 | 0.557 | 0.572 |
| inference_categories | partial | 0.525 | 0.545 | 0.562 | 0.571 | 0.578 |
| inference_categories | blend | 0.526 | 0.546 | 0.562 | 0.571 | 0.578 |

## Go/No-Go Read

- Predicted win rate (other > standard) — choice_only: 59% · inference_affirm: 88% · inference_categories: 90%
- A meaningful experimental effect requires the inference conditions to be reliably above choice_only AND the Wilcoxon-vs-0.5 test to reach p<0.05 with the planned N.
- If the inference conditions don't outperform choice_only in this sim, sweep `--participant-noise` (try 0.0 / 0.15 / 0.30) and `--num-trials` to find the regime where the effect emerges.
