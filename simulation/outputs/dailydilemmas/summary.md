# Simulation Summary (revamped)

Predicts the experimental DV: probability that a participant prefers the partial/projected K-dim summary over the unrestricted standard summary.

## Parameters

| Parameter | Value |
|-----------|-------|
| Users | 50 |
| Trials per user | 20 |
| Test pairs (held-out) | 100 |
| K (dimensions) | 20 |
| Top-K inferences visible | 5 |
| Participant noise (per-dim slip prob) | 0.1 |
| Beta (choice noise) | 2.0 |
| λ standard | 10.0 |
| λ partial  | 0.5 |
| Rating temperature τ | 5.0 |
| Top-N dims shown in summary | 10 |
| Seed | 42 |

## Predicted Rating (P[partial > standard])

Probability the simulated participant prefers the partial K-dim summary (with feedback re-weighting) over the standard summary. 0.5 = no effect; >0.5 = partial preferred.

| Condition | Mean rating | SD | Pct > 0.5 |
|-----------|-------------|----|-----------|
| choice_only | 0.500 | 0.043 | 40% |
| inference_affirm | 0.495 | 0.215 | 44% |
| inference_categories | 0.430 | 0.256 | 40% |

## Summary-Quality Means

Quality scores against ground-truth w*. Higher is better. `combined` = 0.5·spearman + 0.5·(2·top-N sign agreement − 1).

| Condition | Fit | spearman | topn_sign | topn_overlap | combined |
| --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.228 | 0.372 | 0.498 | -0.014 |
| choice_only | projected | 0.232 | 0.370 | 0.498 | -0.014 |
| choice_only | partial | 0.232 | 0.370 | 0.498 | -0.014 |
| inference_affirm | standard | 0.197 | 0.352 | 0.506 | -0.049 |
| inference_affirm | projected | 0.198 | 0.352 | 0.506 | -0.049 |
| inference_affirm | partial | 0.141 | 0.378 | 0.558 | -0.052 |
| inference_categories | standard | 0.234 | 0.382 | 0.508 | -0.001 |
| inference_categories | projected | 0.238 | 0.376 | 0.508 | -0.005 |
| inference_categories | partial | 0.119 | 0.358 | 0.556 | -0.082 |

## Held-Out Choice Accuracy at T

| Condition | standard | projected | partial | Δ proj−std | Δ part−std |
|-----------|----------|-----------|---------|------------|------------|
| choice_only | 0.666 | 0.680 | 0.680 | +0.014 | +0.014 |
| inference_affirm | 0.671 | 0.689 | 0.645 | +0.018 | -0.025 |
| inference_categories | 0.699 | 0.714 | 0.666 | +0.015 | -0.033 |

## Held-Out Log-Likelihood at T

| Condition | LL standard | LL projected | LL partial | Δ proj−std | Δ part−std |
|-----------|-------------|--------------|------------|------------|------------|
| choice_only | -0.6922 | -0.6807 | -0.6807 | +0.0115 | +0.0115 |
| inference_affirm | -0.6923 | -0.6812 | -0.6853 | +0.0110 | +0.0069 |
| inference_categories | -0.6922 | -0.6805 | -0.6852 | +0.0117 | +0.0070 |

## Significance Tests (paired Wilcoxon)

Tests whether the predicted rating is reliably > 0.5 within each condition (i.e., the partial-K-dim summary wins) and whether inference conditions differ from choice_only.

| Comparison | n | mean | Wilcoxon p |
|------------|---|------|------------|
| choice_only vs 0.5 | 50 | 0.500 | 0.1970 |
| inference_affirm vs 0.5 | 50 | 0.495 | 0.7888 |
| inference_categories vs 0.5 | 50 | 0.430 | 0.0518 |
| inference_affirm vs choice_only | 50 | Δ=-0.005 | 0.7888 |
| inference_categories vs choice_only | 50 | Δ=-0.070 | 0.0555 |

## Learning Curves (test acc by trial count)

Mean held-out accuracy across users at each checkpoint. Should rise monotonically with more trials if learning is working.

| Condition | Fit | T=1 | T=5 | T=10 | T=15 | T=20 |
| --- | --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.579 | 0.597 | 0.635 | 0.644 | 0.666 |
| choice_only | projected | 0.597 | 0.613 | 0.652 | 0.664 | 0.680 |
| choice_only | partial | 0.597 | 0.613 | 0.652 | 0.664 | 0.680 |
| inference_affirm | standard | 0.577 | 0.612 | 0.633 | 0.645 | 0.671 |
| inference_affirm | projected | 0.586 | 0.630 | 0.649 | 0.660 | 0.689 |
| inference_affirm | partial | 0.573 | 0.606 | 0.616 | 0.632 | 0.645 |
| inference_categories | standard | 0.573 | 0.615 | 0.657 | 0.667 | 0.699 |
| inference_categories | projected | 0.587 | 0.634 | 0.685 | 0.690 | 0.714 |
| inference_categories | partial | 0.575 | 0.584 | 0.634 | 0.650 | 0.666 |

## Go/No-Go Read

- Predicted win rate (other > standard) — choice_only: 40% · inference_affirm: 44% · inference_categories: 40%
- A meaningful experimental effect requires the inference conditions to be reliably above choice_only AND the Wilcoxon-vs-0.5 test to reach p<0.05 with the planned N.
- If the inference conditions don't outperform choice_only in this sim, sweep `--participant-noise` (try 0.0 / 0.15 / 0.30) and `--num-trials` to find the regime where the effect emerges.
