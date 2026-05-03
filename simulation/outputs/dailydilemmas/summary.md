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
| λ partial  | 0.05 |
| Rating temperature τ | 5.0 |
| Top-N dims shown in summary | 10 |
| Seed | 42 |

## Predicted Rating (P[partial > standard])

Probability the simulated participant prefers the partial K-dim summary (with feedback re-weighting) over the standard summary. 0.5 = no effect; >0.5 = partial preferred.

| Condition | Mean rating | SD | Pct > 0.5 |
|-----------|-------------|----|-----------|
| choice_only | 0.514 | 0.098 | 56% |
| inference_affirm | 0.497 | 0.158 | 46% |
| inference_categories | 0.454 | 0.166 | 38% |

## Summary-Quality Means

Quality scores against ground-truth w*. Higher is better. `combined` = 0.5·spearman + 0.5·(2·top-N sign agreement − 1).

| Condition | Fit | spearman | topn_sign | topn_overlap | combined |
| --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.228 | 0.372 | 0.498 | -0.014 |
| choice_only | projected | 0.254 | 0.370 | 0.498 | -0.003 |
| choice_only | partial | 0.254 | 0.370 | 0.498 | -0.003 |
| inference_affirm | standard | 0.197 | 0.352 | 0.506 | -0.049 |
| inference_affirm | projected | 0.205 | 0.356 | 0.504 | -0.041 |
| inference_affirm | partial | 0.171 | 0.362 | 0.526 | -0.053 |
| inference_categories | standard | 0.234 | 0.382 | 0.508 | -0.001 |
| inference_categories | projected | 0.251 | 0.384 | 0.506 | 0.010 |
| inference_categories | partial | 0.192 | 0.360 | 0.512 | -0.044 |

## Held-Out Choice Accuracy at T

| Condition | standard | projected | partial | Δ proj−std | Δ part−std |
|-----------|----------|-----------|---------|------------|------------|
| choice_only | 0.666 | 0.695 | 0.695 | +0.029 | +0.029 |
| inference_affirm | 0.671 | 0.698 | 0.677 | +0.028 | +0.006 |
| inference_categories | 0.699 | 0.724 | 0.711 | +0.025 | +0.012 |

## Held-Out Log-Likelihood at T

| Condition | LL standard | LL projected | LL partial | Δ proj−std | Δ part−std |
|-----------|-------------|--------------|------------|------------|------------|
| choice_only | -0.6922 | -0.6281 | -0.6281 | +0.0641 | +0.0641 |
| inference_affirm | -0.6923 | -0.6314 | -0.6404 | +0.0609 | +0.0519 |
| inference_categories | -0.6922 | -0.6251 | -0.6363 | +0.0671 | +0.0559 |

## Significance Tests (paired Wilcoxon)

Tests whether the predicted rating is reliably > 0.5 within each condition (i.e., the partial-K-dim summary wins) and whether inference conditions differ from choice_only.

| Comparison | n | mean | Wilcoxon p |
|------------|---|------|------------|
| choice_only vs 0.5 | 50 | 0.514 | 0.1925 |
| inference_affirm vs 0.5 | 50 | 0.497 | 0.8859 |
| inference_categories vs 0.5 | 50 | 0.454 | 0.0594 |
| inference_affirm vs choice_only | 50 | Δ=-0.017 | 0.4433 |
| inference_categories vs choice_only | 50 | Δ=-0.060 | 0.0230 |

## Learning Curves (test acc by trial count)

Mean held-out accuracy across users at each checkpoint. Should rise monotonically with more trials if learning is working.

| Condition | Fit | T=1 | T=5 | T=10 | T=15 | T=20 |
| --- | --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.579 | 0.597 | 0.635 | 0.644 | 0.666 |
| choice_only | projected | 0.597 | 0.615 | 0.654 | 0.676 | 0.695 |
| choice_only | partial | 0.597 | 0.615 | 0.654 | 0.676 | 0.695 |
| inference_affirm | standard | 0.577 | 0.612 | 0.633 | 0.645 | 0.671 |
| inference_affirm | projected | 0.586 | 0.630 | 0.653 | 0.664 | 0.698 |
| inference_affirm | partial | 0.584 | 0.629 | 0.642 | 0.654 | 0.677 |
| inference_categories | standard | 0.573 | 0.615 | 0.657 | 0.667 | 0.699 |
| inference_categories | projected | 0.587 | 0.635 | 0.686 | 0.701 | 0.724 |
| inference_categories | partial | 0.585 | 0.615 | 0.669 | 0.693 | 0.711 |

## Go/No-Go Read

- Predicted win rate (other > standard) — choice_only: 56% · inference_affirm: 46% · inference_categories: 38%
- A meaningful experimental effect requires the inference conditions to be reliably above choice_only AND the Wilcoxon-vs-0.5 test to reach p<0.05 with the planned N.
- If the inference conditions don't outperform choice_only in this sim, sweep `--participant-noise` (try 0.0 / 0.15 / 0.30) and `--num-trials` to find the regime where the effect emerges.
