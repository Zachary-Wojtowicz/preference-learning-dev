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
| α (feedback strength) | 1.0 |
| Rating temperature τ | 5.0 |
| Top-N dims shown in summary | 10 |
| Seed | 42 |

## Predicted Rating (P[partial > standard])

Probability the simulated participant prefers the partial K-dim summary (with feedback re-weighting) over the standard summary. 0.5 = no effect; >0.5 = partial preferred.

| Condition | Mean rating | SD | Pct > 0.5 |
|-----------|-------------|----|-----------|
| choice_only | 0.685 | 0.194 | 84% |
| inference_affirm | 0.614 | 0.210 | 67% |
| inference_categories | 0.765 | 0.176 | 90% |

## Summary-Quality Means

Quality scores against ground-truth w*. Higher is better. `combined` = 0.5·spearman + 0.5·(2·top-N sign agreement − 1).

| Condition | Fit | spearman | topn_sign | topn_overlap | combined |
| --- | --- | --- | --- | --- | --- |
| choice_only | random_projection | 0.174 | 0.188 | 1.000 | -0.225 |
| choice_only | projection_only | 0.461 | 0.239 | 1.000 | -0.031 |
| choice_only | projection_alpha | 0.461 | 0.239 | 1.000 | -0.031 |
| inference_affirm | random_projection | 0.133 | 0.183 | 1.000 | -0.250 |
| inference_affirm | projection_only | 0.382 | 0.227 | 1.000 | -0.082 |
| inference_affirm | projection_alpha | 0.313 | 0.212 | 1.000 | -0.131 |
| inference_categories | random_projection | 0.161 | 0.184 | 1.000 | -0.236 |
| inference_categories | projection_only | 0.359 | 0.218 | 1.000 | -0.102 |
| inference_categories | projection_alpha | 0.616 | 0.254 | 1.000 | 0.062 |

## LOO Choice Accuracy at T

| Condition | random_proj | projection_only | projection_alpha | D alpha-rand |
|-----------|-------------|-----------------|------------------|-------------|
| choice_only | 0.591 | 0.669 | 0.669 | +0.078 |
| inference_affirm | 0.600 | 0.678 | 0.665 | +0.064 |
| inference_categories | 0.552 | 0.653 | 0.660 | +0.108 |

## LOO Log-Likelihood at T

| Condition | LL random_proj | LL projection_only | LL projection_alpha | D alpha-rand |
|-----------|----------------|--------------------|--------------------|-------------|
| choice_only | -0.6907 | -0.5869 | -0.5869 | +0.1038 |
| inference_affirm | -0.6909 | -0.5876 | -0.6791 | +0.0118 |
| inference_categories | -0.6917 | -0.6006 | -0.6785 | +0.0132 |

## Significance Tests (paired Wilcoxon)

Tests whether the predicted rating is reliably > 0.5 within each condition (i.e., the partial-K-dim summary wins) and whether inference conditions differ from choice_only.

| Comparison | n | mean | Wilcoxon p |
|------------|---|------|------------|
| choice_only vs 0.5 | 100 | 0.685 | 0.0000 |
| inference_affirm vs 0.5 | 100 | 0.614 | 0.0000 |
| inference_categories vs 0.5 | 100 | 0.765 | 0.0000 |
| inference_affirm vs choice_only | 100 | Δ=-0.071 | 0.0056 |
| inference_categories vs choice_only | 100 | Δ=+0.080 | 0.0001 |

## Learning Curves (test acc by trial count)

Mean held-out accuracy across users at each checkpoint. Should rise monotonically with more trials if learning is working.

| Condition | Fit | T=3 | T=7 | T=11 | T=15 | T=20 |
| --- | --- | --- | --- | --- | --- | --- |
| choice_only | random_projection | 0.526 | 0.548 | 0.560 | 0.581 | 0.591 |
| choice_only | projection_only | 0.577 | 0.612 | 0.649 | 0.658 | 0.669 |
| choice_only | projection_alpha | 0.577 | 0.612 | 0.649 | 0.658 | 0.669 |
| inference_affirm | random_projection | 0.486 | 0.574 | 0.592 | 0.593 | 0.600 |
| inference_affirm | projection_only | 0.602 | 0.644 | 0.654 | 0.675 | 0.678 |
| inference_affirm | projection_alpha | 0.611 | 0.636 | 0.638 | 0.654 | 0.665 |
| inference_categories | random_projection | 0.502 | 0.513 | 0.525 | 0.546 | 0.552 |
| inference_categories | projection_only | 0.502 | 0.630 | 0.635 | 0.653 | 0.653 |
| inference_categories | projection_alpha | 0.551 | 0.655 | 0.671 | 0.673 | 0.660 |

**⚠ Non-monotonic learning detected (acc didn't improve from mid-T to end-T):**

- inference_categories/projection_alpha: T=12→0.672, T=20→0.660

## Go/No-Go Read

- Predicted win rate (other > standard) — choice_only: 84% · inference_affirm: 67% · inference_categories: 90%
- A meaningful experimental effect requires the inference conditions to be reliably above choice_only AND the Wilcoxon-vs-0.5 test to reach p<0.05 with the planned N.
- If the inference conditions don't outperform choice_only in this sim, sweep `--participant-noise` (try 0.0 / 0.15 / 0.30) and `--num-trials` to find the regime where the effect emerges.
