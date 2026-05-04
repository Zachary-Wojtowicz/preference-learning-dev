# Simulation Summary (revamped)

Predicts the experimental DV: probability that a participant prefers the partial/projected K-dim summary over the unrestricted standard summary.

## Parameters

| Parameter | Value |
|-----------|-------|
| Users | 100 |
| Trials per user | 20 |
| Test pairs (held-out) | 200 |
| K (dimensions) | 20 |
| Top-K inferences visible | 3 |
| Participant noise (per-dim slip prob) | 0.1 |
| Beta (choice noise) | 2.0 |
| λ standard | 10.0 |
| λ partial  | 0.1 |
| γ (projection blend) | 1.0 |
| α (feedback strength) | 0.75 |
| Rating temperature τ | 5.0 |
| Top-N dims shown in summary | 10 |
| Seed | 42 |

## Predicted Rating (P[partial > standard])

Probability the simulated participant prefers the partial K-dim summary (with feedback re-weighting) over the standard summary. 0.5 = no effect; >0.5 = partial preferred.

| Condition | Mean rating | SD | Pct > 0.5 |
|-----------|-------------|----|-----------|
| choice_only | 0.513 | 0.137 | 52% |
| inference_affirm | 0.633 | 0.154 | 83% |
| inference_categories | 0.619 | 0.181 | 77% |

## Summary-Quality Means

Quality scores against ground-truth w*. Higher is better. `combined` = 0.5·spearman + 0.5·(2·top-N sign agreement − 1).

| Condition | Fit | spearman | topn_sign | topn_overlap | combined |
| --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.250 | 0.366 | 0.526 | -0.009 |
| choice_only | projected | 0.257 | 0.374 | 0.527 | 0.002 |
| choice_only | partial | 0.257 | 0.374 | 0.527 | 0.002 |
| choice_only | blend | 0.257 | 0.374 | 0.527 | 0.002 |
| inference_affirm | standard | 0.240 | 0.374 | 0.520 | -0.006 |
| inference_affirm | projected | 0.261 | 0.382 | 0.532 | 0.012 |
| inference_affirm | partial | 0.365 | 0.434 | 0.545 | 0.117 |
| inference_affirm | blend | 0.365 | 0.434 | 0.545 | 0.117 |
| inference_categories | standard | 0.266 | 0.391 | 0.542 | 0.024 |
| inference_categories | projected | 0.280 | 0.401 | 0.535 | 0.041 |
| inference_categories | partial | 0.379 | 0.452 | 0.566 | 0.141 |
| inference_categories | blend | 0.379 | 0.452 | 0.566 | 0.141 |

## Held-Out Choice Accuracy at T

| Condition | standard | projected | partial | blend | Δ blend−std |
|-----------|----------|-----------|---------|-------|------------|
| choice_only | 0.545 | 0.576 | 0.576 | 0.576 | +0.031 |
| inference_affirm | 0.540 | 0.570 | 0.582 | 0.582 | +0.042 |
| inference_categories | 0.542 | 0.573 | 0.579 | 0.579 | +0.037 |

## Held-Out Log-Likelihood at T

| Condition | LL standard | LL projected | LL partial | LL blend | Δ blend−std |
|-----------|-------------|--------------|------------|----------|------------|
| choice_only | -0.6917 | -0.6887 | -0.6887 | -0.6887 | +0.0030 |
| inference_affirm | -0.6918 | -0.6910 | -0.6882 | -0.6882 | +0.0036 |
| inference_categories | -0.6918 | -0.6870 | -0.6913 | -0.6913 | +0.0005 |

## Significance Tests (paired Wilcoxon)

Tests whether the predicted rating is reliably > 0.5 within each condition (i.e., the partial-K-dim summary wins) and whether inference conditions differ from choice_only.

| Comparison | n | mean | Wilcoxon p |
|------------|---|------|------------|
| choice_only vs 0.5 | 100 | 0.513 | 0.4473 |
| inference_affirm vs 0.5 | 100 | 0.633 | 0.0000 |
| inference_categories vs 0.5 | 100 | 0.619 | 0.0000 |
| inference_affirm vs choice_only | 100 | Δ=+0.120 | 0.0000 |
| inference_categories vs choice_only | 100 | Δ=+0.106 | 0.0000 |

## Learning Curves (test acc by trial count)

Mean held-out accuracy across users at each checkpoint. Should rise monotonically with more trials if learning is working.

| Condition | Fit | T=1 | T=5 | T=10 | T=15 | T=20 |
| --- | --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.509 | 0.524 | 0.535 | 0.539 | 0.545 |
| choice_only | projected | 0.517 | 0.537 | 0.554 | 0.560 | 0.576 |
| choice_only | partial | 0.517 | 0.537 | 0.554 | 0.560 | 0.576 |
| choice_only | blend | 0.517 | 0.537 | 0.554 | 0.560 | 0.576 |
| inference_affirm | standard | 0.503 | 0.525 | 0.535 | 0.536 | 0.540 |
| inference_affirm | projected | 0.504 | 0.541 | 0.551 | 0.561 | 0.570 |
| inference_affirm | partial | 0.514 | 0.550 | 0.565 | 0.576 | 0.582 |
| inference_affirm | blend | 0.514 | 0.550 | 0.565 | 0.576 | 0.582 |
| inference_categories | standard | 0.499 | 0.526 | 0.535 | 0.534 | 0.542 |
| inference_categories | projected | 0.499 | 0.539 | 0.550 | 0.556 | 0.573 |
| inference_categories | partial | 0.515 | 0.548 | 0.560 | 0.567 | 0.579 |
| inference_categories | blend | 0.515 | 0.548 | 0.560 | 0.567 | 0.579 |

## Go/No-Go Read

- Predicted win rate (other > standard) — choice_only: 52% · inference_affirm: 83% · inference_categories: 77%
- A meaningful experimental effect requires the inference conditions to be reliably above choice_only AND the Wilcoxon-vs-0.5 test to reach p<0.05 with the planned N.
- If the inference conditions don't outperform choice_only in this sim, sweep `--participant-noise` (try 0.0 / 0.15 / 0.30) and `--num-trials` to find the regime where the effect emerges.
