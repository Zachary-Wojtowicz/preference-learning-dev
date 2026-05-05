# Simulation Summary (revamped)

Predicts the experimental DV: probability that a participant prefers the partial/projected K-dim summary over the unrestricted standard summary.

## Parameters

| Parameter | Value |
|-----------|-------|
| Users | 100 |
| Trials per user | 20 |
| Test pairs (held-out) | 200 |
| K (dimensions) | 10 |
| Top-K inferences visible | 3 |
| Participant noise (per-dim slip prob) | 0.1 |
| Beta (choice noise) | 2.0 |
| λ standard | 0.01 |
| λ partial  | 0.01 |
| γ (projection blend) | 1.0 |
| α (feedback strength) | 0.0 |
| Rating temperature τ | 5.0 |
| Top-N dims shown in summary | 10 |
| Seed | 42 |

## Predicted Rating (P[partial > standard])

Probability the simulated participant prefers the partial K-dim summary (with feedback re-weighting) over the standard summary. 0.5 = no effect; >0.5 = partial preferred.

| Condition | Mean rating | SD | Pct > 0.5 |
|-----------|-------------|----|-----------|
| choice_only | 0.576 | 0.264 | 59% |
| inference_affirm | 0.526 | 0.256 | 56% |
| inference_categories | 0.578 | 0.229 | 62% |

## Summary-Quality Means

Quality scores against ground-truth w*. Higher is better. `combined` = 0.5·spearman + 0.5·(2·top-N sign agreement − 1).

| Condition | Fit | spearman | topn_sign | topn_overlap | combined |
| --- | --- | --- | --- | --- | --- |
| choice_only | random_projection | 0.164 | 0.284 | 1.000 | -0.134 |
| choice_only | projection_only | 0.280 | 0.312 | 1.000 | -0.048 |
| choice_only | projection_alpha | 0.280 | 0.312 | 1.000 | -0.048 |
| inference_affirm | random_projection | 0.163 | 0.268 | 1.000 | -0.151 |
| inference_affirm | projection_only | 0.178 | 0.276 | 1.000 | -0.135 |
| inference_affirm | projection_alpha | 0.178 | 0.276 | 1.000 | -0.135 |
| inference_categories | random_projection | 0.168 | 0.270 | 1.000 | -0.146 |
| inference_categories | projection_only | 0.290 | 0.291 | 1.000 | -0.064 |
| inference_categories | projection_alpha | 0.290 | 0.291 | 1.000 | -0.064 |

## LOO Choice Accuracy at T

| Condition | random_proj | projection_only | projection_alpha | D alpha-rand |
|-----------|-------------|-----------------|------------------|-------------|
| choice_only | 0.515 | 0.550 | 0.550 | +0.035 |
| inference_affirm | 0.500 | 0.526 | 0.526 | +0.026 |
| inference_categories | 0.493 | 0.522 | 0.522 | +0.029 |

## LOO Log-Likelihood at T

| Condition | LL random_proj | LL projection_only | LL projection_alpha | D alpha-rand |
|-----------|----------------|--------------------|--------------------|-------------|
| choice_only | -0.6935 | -0.8808 | -0.8808 | -0.1874 |
| inference_affirm | -0.6972 | -0.9115 | -0.9115 | -0.2143 |
| inference_categories | -0.6953 | -0.9101 | -0.9101 | -0.2147 |

## Significance Tests (paired Wilcoxon)

Tests whether the predicted rating is reliably > 0.5 within each condition (i.e., the partial-K-dim summary wins) and whether inference conditions differ from choice_only.

| Comparison | n | mean | Wilcoxon p |
|------------|---|------|------------|
| choice_only vs 0.5 | 100 | 0.576 | 0.0051 |
| inference_affirm vs 0.5 | 100 | 0.526 | 0.2638 |
| inference_categories vs 0.5 | 100 | 0.578 | 0.0010 |
| inference_affirm vs choice_only | 100 | Δ=-0.050 | 0.0860 |
| inference_categories vs choice_only | 100 | Δ=+0.002 | 0.9643 |

## Learning Curves (test acc by trial count)

Mean held-out accuracy across users at each checkpoint. Should rise monotonically with more trials if learning is working.

| Condition | Fit | T=3 | T=7 | T=11 | T=15 | T=20 |
| --- | --- | --- | --- | --- | --- | --- |
| choice_only | random_projection | 0.525 | 0.514 | 0.504 | 0.486 | 0.515 |
| choice_only | projection_only | 0.571 | 0.524 | 0.555 | 0.551 | 0.550 |
| choice_only | projection_alpha | 0.571 | 0.524 | 0.555 | 0.551 | 0.550 |
| inference_affirm | random_projection | 0.546 | 0.498 | 0.499 | 0.495 | 0.500 |
| inference_affirm | projection_only | 0.488 | 0.527 | 0.546 | 0.517 | 0.526 |
| inference_affirm | projection_alpha | 0.488 | 0.527 | 0.546 | 0.517 | 0.526 |
| inference_categories | random_projection | 0.562 | 0.541 | 0.514 | 0.497 | 0.493 |
| inference_categories | projection_only | 0.567 | 0.543 | 0.536 | 0.521 | 0.522 |
| inference_categories | projection_alpha | 0.567 | 0.543 | 0.536 | 0.521 | 0.522 |

**⚠ Non-monotonic learning detected (acc didn't improve from mid-T to end-T):**

- inference_categories/random_projection: T=12→0.509, T=20→0.493
- inference_categories/projection_only: T=12→0.533, T=20→0.521
- inference_categories/projection_alpha: T=12→0.533, T=20→0.521

## Go/No-Go Read

- Predicted win rate (other > standard) — choice_only: 59% · inference_affirm: 56% · inference_categories: 62%
- A meaningful experimental effect requires the inference conditions to be reliably above choice_only AND the Wilcoxon-vs-0.5 test to reach p<0.05 with the planned N.
- If the inference conditions don't outperform choice_only in this sim, sweep `--participant-noise` (try 0.0 / 0.15 / 0.30) and `--num-trials` to find the regime where the effect emerges.
