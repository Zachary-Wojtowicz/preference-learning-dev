# LLM-Persona Simulation Summary (revamped)

Predicts the experimental DV: probability that an LLM-persona participant prefers the partial/projected K-dim summary over the unrestricted standard summary, after T training trials.

## Parameters

| Parameter | Value |
|-----------|-------|
| Personas | 20 |
| Persona model | Qwen/Qwen3-32B |
| Choice model | Qwen/Qwen3-32B |
| Trials per persona | 20 |
| Test pairs (held-out) | 50 |
| Top-K inferences visible | 5 |
| λ standard | 10.0 |
| λ partial  | 0.05 |
| Rating temperature τ | 20.0 |
| Seed | 42 |

## Predicted Rating (P[partial > standard])

| Condition | Mean | SD | Pct > 0.5 |
|-----------|------|----|-----------|
| choice_only | 0.790 | 0.257 | 75% |
| inference_affirm | 0.844 | 0.207 | 95% |
| inference_categories | 0.822 | 0.219 | 90% |

## Held-Out Log-Likelihood (primary quality signal)

| Condition | LL standard | LL projected | LL partial | Δ proj−std | Δ part−std |
|-----------|-------------|--------------|------------|------------|------------|
| choice_only | -0.6843 | -0.5737 | -0.5737 | +0.1106 | +0.1106 |
| inference_affirm | -0.6843 | -0.5737 | -0.5751 | +0.1106 | +0.1092 |
| inference_categories | -0.6843 | -0.5737 | -0.5744 | +0.1106 | +0.1099 |

## Held-Out Choice Accuracy

| Condition | Acc standard | Acc projected | Acc partial |
|-----------|--------------|---------------|-------------|
| choice_only | 0.696 | 0.699 | 0.699 |
| inference_affirm | 0.696 | 0.699 | 0.669 |
| inference_categories | 0.696 | 0.699 | 0.677 |

## Significance Tests

| Comparison | n | mean Δ rating | Wilcoxon p |
|------------|---|---------------|------------|
| choice_only vs 0.5 | 20 | +0.290 | 0.0004 |
| inference_affirm vs 0.5 | 20 | +0.344 | 0.0001 |
| inference_categories vs 0.5 | 20 | +0.322 | 0.0001 |
| inference_affirm vs choice_only | 20 | +0.054 | 0.4749 |
| inference_categories vs choice_only | 20 | +0.033 | 0.7012 |

## Learning Curves (test acc by trial count)

Mean held-out accuracy across personas at each checkpoint. Should rise with more trials if learning is working.

| Condition | Fit | T=1 | T=5 | T=10 | T=15 | T=20 |
| --- | --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.533 | 0.643 | 0.647 | 0.676 | 0.696 |
| choice_only | projected | 0.523 | 0.632 | 0.646 | 0.682 | 0.699 |
| choice_only | partial | 0.523 | 0.632 | 0.646 | 0.682 | 0.699 |
| inference_affirm | standard | 0.533 | 0.643 | 0.647 | 0.676 | 0.696 |
| inference_affirm | projected | 0.523 | 0.632 | 0.646 | 0.682 | 0.699 |
| inference_affirm | partial | 0.543 | 0.628 | 0.633 | 0.665 | 0.669 |
| inference_categories | standard | 0.533 | 0.643 | 0.647 | 0.676 | 0.696 |
| inference_categories | projected | 0.523 | 0.632 | 0.646 | 0.682 | 0.699 |
| inference_categories | partial | 0.530 | 0.626 | 0.635 | 0.683 | 0.677 |

