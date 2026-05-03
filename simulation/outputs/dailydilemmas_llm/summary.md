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
| λ partial  | 0.5 |
| Rating temperature τ | 20.0 |
| Seed | 42 |

## Predicted Rating (P[partial > standard])

| Condition | Mean | SD | Pct > 0.5 |
|-----------|------|----|-----------|
| choice_only | 0.509 | 0.067 | 50% |
| inference_affirm | 0.498 | 0.090 | 65% |
| inference_categories | 0.456 | 0.099 | 40% |

## Held-Out Log-Likelihood (primary quality signal)

| Condition | LL standard | LL projected | LL partial | Δ proj−std | Δ part−std |
|-----------|-------------|--------------|------------|------------|------------|
| choice_only | -0.6916 | -0.6897 | -0.6897 | +0.0019 | +0.0019 |
| inference_affirm | -0.6916 | -0.6897 | -0.6922 | +0.0019 | -0.0006 |
| inference_categories | -0.6916 | -0.6897 | -0.7007 | +0.0019 | -0.0091 |

## Held-Out Choice Accuracy

| Condition | Acc standard | Acc projected | Acc partial |
|-----------|--------------|---------------|-------------|
| choice_only | 0.545 | 0.529 | 0.529 |
| inference_affirm | 0.545 | 0.529 | 0.534 |
| inference_categories | 0.545 | 0.529 | 0.505 |

## Significance Tests

| Comparison | n | mean Δ rating | Wilcoxon p |
|------------|---|---------------|------------|
| choice_only vs 0.5 | 20 | +0.009 | 0.8124 |
| inference_affirm vs 0.5 | 20 | -0.002 | 0.4749 |
| inference_categories vs 0.5 | 20 | -0.044 | 0.1231 |
| inference_affirm vs choice_only | 20 | -0.011 | 0.8983 |
| inference_categories vs choice_only | 20 | -0.053 | 0.0192 |

## Learning Curves (test acc by trial count)

Mean held-out accuracy across personas at each checkpoint. Should rise with more trials if learning is working.

| Condition | Fit | T=1 | T=5 | T=10 | T=15 | T=20 |
| --- | --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.517 | 0.523 | 0.520 | 0.537 | 0.545 |
| choice_only | projected | 0.504 | 0.505 | 0.511 | 0.518 | 0.529 |
| choice_only | partial | 0.504 | 0.505 | 0.511 | 0.518 | 0.529 |
| inference_affirm | standard | 0.517 | 0.523 | 0.520 | 0.537 | 0.545 |
| inference_affirm | projected | 0.504 | 0.505 | 0.511 | 0.518 | 0.529 |
| inference_affirm | partial | 0.509 | 0.519 | 0.510 | 0.532 | 0.534 |
| inference_categories | standard | 0.517 | 0.523 | 0.520 | 0.537 | 0.545 |
| inference_categories | projected | 0.504 | 0.505 | 0.511 | 0.518 | 0.529 |
| inference_categories | partial | 0.503 | 0.496 | 0.510 | 0.502 | 0.505 |

