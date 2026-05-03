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
| λ partial  | 0.5 |
| Rating temperature τ | 5.0 |
| Top-N dims shown in summary | 10 |
| Seed | 42 |

## Predicted Rating (P[partial > standard])

Probability the simulated participant prefers the partial K-dim summary (with feedback re-weighting) over the standard summary. 0.5 = no effect; >0.5 = partial preferred.

| Condition | Mean rating | SD | Pct > 0.5 |
|-----------|-------------|----|-----------|
| choice_only | 0.518 | 0.063 | 64% |
| inference_affirm | 0.631 | 0.221 | 74% |
| inference_categories | 0.691 | 0.203 | 84% |

## Summary-Quality Means

Quality scores against ground-truth w*. Higher is better. `combined` = 0.5·spearman + 0.5·(2·top-N sign agreement − 1).

| Condition | Fit | spearman | topn_sign | topn_overlap | combined |
| --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.383 | 0.458 | 0.438 | 0.149 |
| choice_only | projected | 0.393 | 0.468 | 0.450 | 0.164 |
| choice_only | partial | 0.393 | 0.468 | 0.450 | 0.164 |
| inference_affirm | standard | 0.376 | 0.418 | 0.422 | 0.106 |
| inference_affirm | projected | 0.398 | 0.430 | 0.422 | 0.129 |
| inference_affirm | partial | 0.459 | 0.510 | 0.494 | 0.239 |
| inference_categories | standard | 0.384 | 0.442 | 0.436 | 0.134 |
| inference_categories | projected | 0.396 | 0.448 | 0.434 | 0.146 |
| inference_categories | partial | 0.547 | 0.550 | 0.512 | 0.324 |

## Held-Out Choice Accuracy at T

| Condition | standard | projected | partial | Δ proj−std | Δ part−std |
|-----------|----------|-----------|---------|------------|------------|
| choice_only | 0.661 | 0.716 | 0.716 | +0.054 | +0.054 |
| inference_affirm | 0.669 | 0.719 | 0.680 | +0.051 | +0.012 |
| inference_categories | 0.661 | 0.720 | 0.691 | +0.058 | +0.030 |

## Held-Out Log-Likelihood at T

| Condition | LL standard | LL projected | LL partial | Δ proj−std | Δ part−std |
|-----------|-------------|--------------|------------|------------|------------|
| choice_only | -0.6862 | -0.6257 | -0.6257 | +0.0605 | +0.0605 |
| inference_affirm | -0.6860 | -0.6244 | -0.6397 | +0.0616 | +0.0463 |
| inference_categories | -0.6864 | -0.6264 | -0.6354 | +0.0600 | +0.0511 |

## Significance Tests (paired Wilcoxon)

Tests whether the predicted rating is reliably > 0.5 within each condition (i.e., the partial-K-dim summary wins) and whether inference conditions differ from choice_only.

| Comparison | n | mean | Wilcoxon p |
|------------|---|------|------------|
| choice_only vs 0.5 | 50 | 0.518 | 0.0107 |
| inference_affirm vs 0.5 | 50 | 0.631 | 0.0002 |
| inference_categories vs 0.5 | 50 | 0.691 | 0.0000 |
| inference_affirm vs choice_only | 50 | Δ=+0.113 | 0.0005 |
| inference_categories vs choice_only | 50 | Δ=+0.174 | 0.0000 |

## Learning Curves (test acc by trial count)

Mean held-out accuracy across users at each checkpoint. Should rise monotonically with more trials if learning is working.

| Condition | Fit | T=1 | T=5 | T=10 | T=15 | T=20 |
| --- | --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.555 | 0.591 | 0.621 | 0.642 | 0.661 |
| choice_only | projected | 0.577 | 0.628 | 0.674 | 0.699 | 0.716 |
| choice_only | partial | 0.577 | 0.628 | 0.674 | 0.699 | 0.716 |
| inference_affirm | standard | 0.550 | 0.591 | 0.635 | 0.647 | 0.669 |
| inference_affirm | projected | 0.568 | 0.619 | 0.667 | 0.698 | 0.719 |
| inference_affirm | partial | 0.556 | 0.597 | 0.641 | 0.665 | 0.680 |
| inference_categories | standard | 0.569 | 0.600 | 0.628 | 0.647 | 0.661 |
| inference_categories | projected | 0.587 | 0.635 | 0.678 | 0.704 | 0.720 |
| inference_categories | partial | 0.576 | 0.629 | 0.652 | 0.673 | 0.691 |

## Go/No-Go Read

- Predicted win rate (other > standard) — choice_only: 64% · inference_affirm: 74% · inference_categories: 84%
- A meaningful experimental effect requires the inference conditions to be reliably above choice_only AND the Wilcoxon-vs-0.5 test to reach p<0.05 with the planned N.
- If the inference conditions don't outperform choice_only in this sim, sweep `--participant-noise` (try 0.0 / 0.15 / 0.30) and `--num-trials` to find the regime where the effect emerges.
