# Simulation Summary (revamped)

Predicts the experimental DV: probability that a participant prefers the partial/projected K-dim summary over the unrestricted standard summary.

## Parameters

| Parameter | Value |
|-----------|-------|
| Users | 50 |
| Trials per user | 20 |
| Test pairs (held-out) | 200 |
| K (dimensions) | 25 |
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
| choice_only | projected | 0.510 | 0.059 | 62% |
| inference_affirm | feedback_adjusted | 0.619 | 0.223 | 74% |
| inference_categories | feedback_adjusted | 0.701 | 0.200 | 84% |

## Summary-Quality Means

Quality scores against ground-truth w*. Higher is better. `combined` = 0.5·spearman + 0.5·(2·top-N sign agreement − 1).

| Condition | Fit | spearman | topn_sign | topn_overlap | combined |
| --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.383 | 0.458 | 0.438 | 0.149 |
| choice_only | projected | 0.387 | 0.464 | 0.438 | 0.157 |
| inference_affirm | standard | 0.376 | 0.418 | 0.422 | 0.106 |
| inference_affirm | feedback_adjusted | 0.456 | 0.500 | 0.498 | 0.228 |
| inference_categories | standard | 0.384 | 0.442 | 0.436 | 0.134 |
| inference_categories | feedback_adjusted | 0.554 | 0.556 | 0.522 | 0.333 |

## Held-Out Choice Accuracy at T (diagnostic)

| Condition | Standard fit | Other fit | Δ (other − standard) |
|-----------|--------------|-----------|----------------------|
| choice_only | 0.661 | 0.713 | +0.052 |
| inference_affirm | 0.669 | 0.677 | +0.009 |
| inference_categories | 0.661 | 0.686 | +0.025 |

## Held-Out Log-Likelihood at T

| Condition | LL standard | LL other | Δ (other − standard) |
|-----------|-------------|----------|----------------------|
| choice_only | -0.6862 | -0.6515 | +0.0347 |
| inference_affirm | -0.6860 | -0.6579 | +0.0281 |
| inference_categories | -0.6864 | -0.6550 | +0.0314 |

## Significance Tests (paired Wilcoxon)

Tests whether the predicted rating is reliably > 0.5 within each condition (i.e., the K-dim summary wins) and whether inference conditions differ from choice_only.

| Comparison | n | mean | Wilcoxon p |
|------------|---|------|------------|
| choice_only vs 0.5 | 50 | 0.510 | 0.0264 |
| inference_affirm vs 0.5 | 50 | 0.619 | 0.0006 |
| inference_categories vs 0.5 | 50 | 0.701 | 0.0000 |
| inference_affirm vs choice_only | 50 | Δ=+0.110 | 0.0009 |
| inference_categories vs choice_only | 50 | Δ=+0.191 | 0.0000 |

## Learning Curves (test acc by trial count)

Mean held-out accuracy across users at each checkpoint. Should rise monotonically with more trials if learning is working.

| Condition | Fit | T=1 | T=5 | T=10 | T=15 | T=20 |
| --- | --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.555 | 0.591 | 0.621 | 0.642 | 0.661 |
| choice_only | projected | 0.577 | 0.629 | 0.674 | 0.699 | 0.713 |
| inference_affirm | standard | 0.550 | 0.591 | 0.635 | 0.647 | 0.669 |
| inference_affirm | feedback_adjusted | 0.556 | 0.596 | 0.639 | 0.663 | 0.677 |
| inference_categories | standard | 0.569 | 0.600 | 0.628 | 0.647 | 0.661 |
| inference_categories | feedback_adjusted | 0.576 | 0.627 | 0.649 | 0.673 | 0.686 |

## Go/No-Go Read

- Predicted win rate (other > standard) — choice_only: 62% · inference_affirm: 74% · inference_categories: 84%
- A meaningful experimental effect requires the inference conditions to be reliably above choice_only AND the Wilcoxon-vs-0.5 test to reach p<0.05 with the planned N.
- If the inference conditions don't outperform choice_only in this sim, sweep `--participant-noise` (try 0.0 / 0.15 / 0.30) and `--num-trials` to find the regime where the effect emerges.
