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
| λ partial  | 0.5 |
| Rating temperature τ | 5.0 |
| Top-N dims shown in summary | 10 |
| Seed | 42 |

## Predicted Rating (P[partial > standard])

Probability the simulated participant prefers the partial K-dim summary (with feedback re-weighting) over the standard summary. 0.5 = no effect; >0.5 = partial preferred.

| Condition | Mean rating | SD | Pct > 0.5 |
|-----------|-------------|----|-----------|
| choice_only | 0.512 | 0.040 | 58% |
| inference_affirm | 0.495 | 0.271 | 50% |
| inference_categories | 0.514 | 0.243 | 54% |

## Summary-Quality Means

Quality scores against ground-truth w*. Higher is better. `combined` = 0.5·spearman + 0.5·(2·top-N sign agreement − 1).

| Condition | Fit | spearman | topn_sign | topn_overlap | combined |
| --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.279 | 0.406 | 0.544 | 0.045 |
| choice_only | projected | 0.287 | 0.412 | 0.536 | 0.056 |
| choice_only | partial | 0.287 | 0.412 | 0.536 | 0.056 |
| inference_affirm | standard | 0.207 | 0.388 | 0.544 | -0.008 |
| inference_affirm | projected | 0.208 | 0.388 | 0.534 | -0.008 |
| inference_affirm | partial | 0.165 | 0.384 | 0.590 | -0.034 |
| inference_categories | standard | 0.281 | 0.398 | 0.540 | 0.038 |
| inference_categories | projected | 0.289 | 0.402 | 0.552 | 0.046 |
| inference_categories | partial | 0.267 | 0.412 | 0.578 | 0.045 |

## Held-Out Choice Accuracy at T

| Condition | standard | projected | partial | Δ proj−std | Δ part−std |
|-----------|----------|-----------|---------|------------|------------|
| choice_only | 0.549 | 0.576 | 0.576 | +0.027 | +0.027 |
| inference_affirm | 0.543 | 0.566 | 0.534 | +0.022 | -0.009 |
| inference_categories | 0.548 | 0.575 | 0.548 | +0.027 | +0.000 |

## Held-Out Log-Likelihood at T

| Condition | LL standard | LL projected | LL partial | Δ proj−std | Δ part−std |
|-----------|-------------|--------------|------------|------------|------------|
| choice_only | -0.6916 | -0.6767 | -0.6767 | +0.0149 | +0.0149 |
| inference_affirm | -0.6918 | -0.6812 | -0.6913 | +0.0106 | +0.0005 |
| inference_categories | -0.6916 | -0.6774 | -0.6858 | +0.0142 | +0.0058 |

## Significance Tests (paired Wilcoxon)

Tests whether the predicted rating is reliably > 0.5 within each condition (i.e., the partial-K-dim summary wins) and whether inference conditions differ from choice_only.

| Comparison | n | mean | Wilcoxon p |
|------------|---|------|------------|
| choice_only vs 0.5 | 50 | 0.512 | 0.0457 |
| inference_affirm vs 0.5 | 50 | 0.495 | 0.9154 |
| inference_categories vs 0.5 | 50 | 0.514 | 0.6877 |
| inference_affirm vs choice_only | 50 | Δ=-0.017 | 0.8109 |
| inference_categories vs choice_only | 50 | Δ=+0.002 | 0.9010 |

## Learning Curves (test acc by trial count)

Mean held-out accuracy across users at each checkpoint. Should rise monotonically with more trials if learning is working.

| Condition | Fit | T=1 | T=5 | T=10 | T=15 | T=20 |
| --- | --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.507 | 0.523 | 0.538 | 0.549 | 0.549 |
| choice_only | projected | 0.515 | 0.541 | 0.556 | 0.573 | 0.576 |
| choice_only | partial | 0.515 | 0.541 | 0.556 | 0.573 | 0.576 |
| inference_affirm | standard | 0.515 | 0.523 | 0.530 | 0.538 | 0.543 |
| inference_affirm | projected | 0.526 | 0.537 | 0.551 | 0.557 | 0.566 |
| inference_affirm | partial | 0.523 | 0.530 | 0.541 | 0.540 | 0.534 |
| inference_categories | standard | 0.506 | 0.519 | 0.532 | 0.544 | 0.548 |
| inference_categories | projected | 0.524 | 0.536 | 0.555 | 0.571 | 0.575 |
| inference_categories | partial | 0.520 | 0.530 | 0.547 | 0.548 | 0.548 |

**⚠ Non-monotonic learning detected (acc didn't improve from mid-T to end-T):**

- inference_affirm/partial: T=11→0.541, T=20→0.534

## Go/No-Go Read

- Predicted win rate (other > standard) — choice_only: 58% · inference_affirm: 50% · inference_categories: 54%
- A meaningful experimental effect requires the inference conditions to be reliably above choice_only AND the Wilcoxon-vs-0.5 test to reach p<0.05 with the planned N.
- If the inference conditions don't outperform choice_only in this sim, sweep `--participant-noise` (try 0.0 / 0.15 / 0.30) and `--num-trials` to find the regime where the effect emerges.
