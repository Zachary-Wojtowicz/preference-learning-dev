# Simulation Summary (revamped)

Predicts the experimental DV: probability that a participant prefers the partial/projected K-dim summary over the unrestricted standard summary.

## Parameters

| Parameter | Value |
|-----------|-------|
| Users | 50 |
| Trials per user | 20 |
| Test pairs (held-out) | 200 |
| K (dimensions) | 20 |
| Top-K inferences visible | 5 |
| Participant noise (per-dim slip prob) | 0.1 |
| Beta (choice noise) | 2.0 |
| λ standard | 10.0 |
| λ partial  | 1.0 |
| Rating temperature τ | 5.0 |
| Top-N dims shown in summary | 10 |
| Seed | 42 |

## Predicted Rating (P[other > standard])

Probability the simulated participant prefers the K-dim (partial/projected) summary over the standard summary. 0.5 = no effect; >0.5 = K-dim preferred.

| Condition | Other-fit type | Mean rating | SD | Pct > 0.5 |
|-----------|----------------|-------------|----|-----------|
| choice_only | projected | 0.511 | 0.042 | 48% |
| inference_affirm | feedback_adjusted | 0.488 | 0.280 | 50% |
| inference_categories | feedback_adjusted | 0.518 | 0.249 | 56% |

## Summary-Quality Means

Quality scores against ground-truth w*. Higher is better. `combined` = 0.5·spearman + 0.5·(2·top-N sign agreement − 1).

| Condition | Fit | spearman | topn_sign | topn_overlap | combined |
| --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.279 | 0.406 | 0.544 | 0.045 |
| choice_only | projected | 0.280 | 0.414 | 0.544 | 0.054 |
| inference_affirm | standard | 0.207 | 0.388 | 0.544 | -0.008 |
| inference_affirm | feedback_adjusted | 0.167 | 0.378 | 0.602 | -0.039 |
| inference_categories | standard | 0.281 | 0.398 | 0.540 | 0.038 |
| inference_categories | feedback_adjusted | 0.263 | 0.416 | 0.580 | 0.048 |

## Held-Out Choice Accuracy (diagnostic)

| Condition | Standard fit | Other fit |
|-----------|--------------|-----------|
| choice_only | 0.549 | 0.575 |
| inference_affirm | 0.543 | 0.534 |
| inference_categories | 0.548 | 0.544 |

## Significance Tests (paired Wilcoxon)

Tests whether the predicted rating is reliably > 0.5 within each condition (i.e., the K-dim summary wins) and whether inference conditions differ from choice_only.

| Comparison | n | mean | Wilcoxon p |
|------------|---|------|------------|
| choice_only vs 0.5 | 50 | 0.511 | 0.3590 |
| inference_affirm vs 0.5 | 50 | 0.488 | 0.7304 |
| inference_categories vs 0.5 | 50 | 0.518 | 0.5786 |
| inference_affirm vs choice_only | 50 | Δ=-0.022 | 0.6119 |
| inference_categories vs choice_only | 50 | Δ=+0.007 | 0.7522 |

## Go/No-Go Read

- Predicted win rate (other > standard) — choice_only: 48% · inference_affirm: 50% · inference_categories: 56%
- A meaningful experimental effect requires the inference conditions to be reliably above choice_only AND the Wilcoxon-vs-0.5 test to reach p<0.05 with the planned N.
- If the inference conditions don't outperform choice_only in this sim, sweep `--participant-noise` (try 0.0 / 0.15 / 0.30) and `--num-trials` to find the regime where the effect emerges.
