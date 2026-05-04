# Simulation Summary (revamped)

Predicts the experimental DV: probability that a participant prefers the partial/projected K-dim summary over the unrestricted standard summary.

## Parameters

| Parameter | Value |
|-----------|-------|
| Users | 100 |
| Trials per user | 20 |
| Test pairs (held-out) | 200 |
| K (dimensions) | 25 |
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
| choice_only | 0.544 | 0.097 | 68% |
| inference_affirm | 0.584 | 0.143 | 72% |
| inference_categories | 0.590 | 0.148 | 71% |

## Summary-Quality Means

Quality scores against ground-truth w*. Higher is better. `combined` = 0.5·spearman + 0.5·(2·top-N sign agreement − 1).

| Condition | Fit | spearman | topn_sign | topn_overlap | combined |
| --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.419 | 0.478 | 0.436 | 0.187 |
| choice_only | projected | 0.443 | 0.503 | 0.460 | 0.225 |
| choice_only | partial | 0.443 | 0.503 | 0.460 | 0.225 |
| choice_only | blend | 0.443 | 0.503 | 0.460 | 0.225 |
| inference_affirm | standard | 0.394 | 0.474 | 0.445 | 0.171 |
| inference_affirm | projected | 0.433 | 0.500 | 0.458 | 0.216 |
| inference_affirm | partial | 0.481 | 0.505 | 0.480 | 0.246 |
| inference_affirm | blend | 0.481 | 0.505 | 0.480 | 0.246 |
| inference_categories | standard | 0.428 | 0.464 | 0.432 | 0.178 |
| inference_categories | projected | 0.453 | 0.487 | 0.451 | 0.213 |
| inference_categories | partial | 0.502 | 0.509 | 0.482 | 0.260 |
| inference_categories | blend | 0.502 | 0.509 | 0.482 | 0.260 |

## Held-Out Choice Accuracy at T

| Condition | standard | projected | partial | blend | Δ blend−std |
|-----------|----------|-----------|---------|-------|------------|
| choice_only | 0.671 | 0.734 | 0.734 | 0.734 | +0.063 |
| inference_affirm | 0.659 | 0.719 | 0.705 | 0.705 | +0.046 |
| inference_categories | 0.669 | 0.733 | 0.716 | 0.716 | +0.048 |

## Held-Out Log-Likelihood at T

| Condition | LL standard | LL projected | LL partial | LL blend | Δ blend−std |
|-----------|-------------|--------------|------------|----------|------------|
| choice_only | -0.6859 | -0.5468 | -0.5468 | -0.5468 | +0.1391 |
| inference_affirm | -0.6865 | -0.5597 | -0.5660 | -0.5660 | +0.1204 |
| inference_categories | -0.6861 | -0.5520 | -0.5613 | -0.5613 | +0.1248 |

## Significance Tests (paired Wilcoxon)

Tests whether the predicted rating is reliably > 0.5 within each condition (i.e., the partial-K-dim summary wins) and whether inference conditions differ from choice_only.

| Comparison | n | mean | Wilcoxon p |
|------------|---|------|------------|
| choice_only vs 0.5 | 100 | 0.544 | 0.0000 |
| inference_affirm vs 0.5 | 100 | 0.584 | 0.0000 |
| inference_categories vs 0.5 | 100 | 0.590 | 0.0000 |
| inference_affirm vs choice_only | 100 | Δ=+0.039 | 0.0177 |
| inference_categories vs choice_only | 100 | Δ=+0.046 | 0.0220 |

## Learning Curves (test acc by trial count)

Mean held-out accuracy across users at each checkpoint. Should rise monotonically with more trials if learning is working.

| Condition | Fit | T=1 | T=5 | T=10 | T=15 | T=20 |
| --- | --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.536 | 0.599 | 0.631 | 0.653 | 0.671 |
| choice_only | projected | 0.557 | 0.631 | 0.675 | 0.713 | 0.734 |
| choice_only | partial | 0.557 | 0.631 | 0.675 | 0.713 | 0.734 |
| choice_only | blend | 0.557 | 0.631 | 0.675 | 0.713 | 0.734 |
| inference_affirm | standard | 0.546 | 0.596 | 0.625 | 0.644 | 0.659 |
| inference_affirm | projected | 0.563 | 0.625 | 0.669 | 0.699 | 0.719 |
| inference_affirm | partial | 0.568 | 0.634 | 0.670 | 0.692 | 0.705 |
| inference_affirm | blend | 0.568 | 0.634 | 0.670 | 0.692 | 0.705 |
| inference_categories | standard | 0.546 | 0.600 | 0.626 | 0.650 | 0.669 |
| inference_categories | projected | 0.569 | 0.638 | 0.679 | 0.705 | 0.733 |
| inference_categories | partial | 0.574 | 0.637 | 0.672 | 0.700 | 0.716 |
| inference_categories | blend | 0.574 | 0.637 | 0.672 | 0.700 | 0.716 |

## Go/No-Go Read

- Predicted win rate (other > standard) — choice_only: 68% · inference_affirm: 72% · inference_categories: 71%
- A meaningful experimental effect requires the inference conditions to be reliably above choice_only AND the Wilcoxon-vs-0.5 test to reach p<0.05 with the planned N.
- If the inference conditions don't outperform choice_only in this sim, sweep `--participant-noise` (try 0.0 / 0.15 / 0.30) and `--num-trials` to find the regime where the effect emerges.
