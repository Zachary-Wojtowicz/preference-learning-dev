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
| Beta (choice noise) | 10.0 |
| λ standard | 0.01 |
| λ partial  | 0.01 |
| γ (projection blend) | 1.0 |
| α default | 1.0 |
| α affirm | 0.25 |
| α categories | 0.25 |
| Rating temperature τ | 5.0 |
| Top-N dims shown in summary | 10 |
| Seed | 42 |

## Predicted Rating (P[partial > standard])

Probability the simulated participant prefers the partial K-dim summary (with feedback re-weighting) over the standard summary. 0.5 = no effect; >0.5 = partial preferred.

| Condition | Mean rating | SD | Pct > 0.5 |
|-----------|-------------|----|-----------|
| choice_only | 0.635 | 0.208 | 72% |
| inference_affirm | 0.653 | 0.201 | 73% |
| inference_categories | 0.687 | 0.192 | 83% |

## Summary-Quality Means

Quality scores against ground-truth w*. Higher is better. `combined` = 0.5·spearman + 0.5·(2·top-N sign agreement − 1).

| Condition | Fit | spearman | topn_sign | topn_overlap | combined |
| --- | --- | --- | --- | --- | --- |
| choice_only | random_projection | 0.144 | 0.186 | 1.000 | -0.242 |
| choice_only | projection_only | 0.362 | 0.217 | 1.000 | -0.102 |
| choice_only | projection_alpha | 0.362 | 0.217 | 1.000 | -0.102 |
| inference_affirm | random_projection | 0.144 | 0.188 | 1.000 | -0.240 |
| inference_affirm | projection_only | 0.384 | 0.228 | 1.000 | -0.080 |
| inference_affirm | projection_alpha | 0.391 | 0.227 | 1.000 | -0.077 |
| inference_categories | random_projection | 0.166 | 0.179 | 1.000 | -0.238 |
| inference_categories | projection_only | 0.410 | 0.234 | 1.000 | -0.061 |
| inference_categories | projection_alpha | 0.468 | 0.232 | 1.000 | -0.034 |

## LOO Choice Accuracy at T

| Condition | random_proj | projection_only | projection_alpha | D alpha-rand |
|-----------|-------------|-----------------|------------------|-------------|
| choice_only | 0.605 | 0.677 | 0.677 | +0.072 |
| inference_affirm | 0.575 | 0.663 | 0.665 | +0.090 |
| inference_categories | 0.576 | 0.679 | 0.676 | +0.100 |

## LOO Log-Likelihood at T

| Condition | LL random_proj | LL projection_only | LL projection_alpha | D alpha-rand |
|-----------|----------------|--------------------|--------------------|-------------|
| choice_only | -0.6908 | -0.5851 | -0.5851 | +0.1057 |
| inference_affirm | -0.6914 | -0.6028 | -0.6562 | +0.0351 |
| inference_categories | -0.6915 | -0.5812 | -0.6518 | +0.0397 |

## Significance Tests (paired Wilcoxon)

Tests whether the predicted rating is reliably > 0.5 within each condition (i.e., the partial-K-dim summary wins) and whether inference conditions differ from choice_only.

| Comparison | n | mean | Wilcoxon p |
|------------|---|------|------------|
| choice_only vs 0.5 | 100 | 0.635 | 0.0000 |
| inference_affirm vs 0.5 | 100 | 0.653 | 0.0000 |
| inference_categories vs 0.5 | 100 | 0.687 | 0.0000 |
| inference_affirm vs choice_only | 100 | Δ=+0.018 | 0.7583 |
| inference_categories vs choice_only | 100 | Δ=+0.052 | 0.0581 |

## Learning Curves (test acc by trial count)

Mean held-out accuracy across users at each checkpoint. Should rise monotonically with more trials if learning is working.

| Condition | Fit | T=3 | T=7 | T=11 | T=15 | T=20 |
| --- | --- | --- | --- | --- | --- | --- |
| choice_only | random_projection | 0.495 | 0.580 | 0.615 | 0.592 | 0.605 |
| choice_only | projection_only | 0.590 | 0.638 | 0.658 | 0.659 | 0.677 |
| choice_only | projection_alpha | 0.590 | 0.638 | 0.658 | 0.659 | 0.677 |
| inference_affirm | random_projection | 0.502 | 0.505 | 0.536 | 0.555 | 0.575 |
| inference_affirm | projection_only | 0.556 | 0.593 | 0.625 | 0.645 | 0.663 |
| inference_affirm | projection_alpha | 0.594 | 0.600 | 0.623 | 0.635 | 0.665 |
| inference_categories | random_projection | 0.519 | 0.519 | 0.543 | 0.561 | 0.576 |
| inference_categories | projection_only | 0.542 | 0.632 | 0.668 | 0.664 | 0.679 |
| inference_categories | projection_alpha | 0.565 | 0.658 | 0.667 | 0.667 | 0.676 |

**⚠ Non-monotonic learning detected (acc didn't improve from mid-T to end-T):**

- choice_only/random_projection: T=12→0.609, T=20→0.605
- inference_categories/projection_alpha: T=12→0.677, T=20→0.675

## Go/No-Go Read

- Predicted win rate (other > standard) — choice_only: 72% · inference_affirm: 73% · inference_categories: 83%
- A meaningful experimental effect requires the inference conditions to be reliably above choice_only AND the Wilcoxon-vs-0.5 test to reach p<0.05 with the planned N.
- If the inference conditions don't outperform choice_only in this sim, sweep `--participant-noise` (try 0.0 / 0.15 / 0.30) and `--num-trials` to find the regime where the effect emerges.
