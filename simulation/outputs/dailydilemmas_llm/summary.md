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
| λ partial  | 1.0 |
| Rating temperature τ | 20.0 |
| Seed | 42 |

## Predicted Rating (P[other > standard])

| Condition | Other | Mean | SD | Pct > 0.5 |
|-----------|-------|------|----|-----------|
| choice_only | projected | 0.510 | 0.039 | 45% |
| inference_affirm | feedback_adjusted | 0.504 | 0.055 | 65% |
| inference_categories | feedback_adjusted | 0.482 | 0.064 | 45% |

## Held-Out Log-Likelihood (primary quality signal)

| Condition | LL standard | LL other | Δ (other − standard) |
|-----------|-------------|----------|----------------------|
| choice_only | -0.6916 | -0.6896 | +0.0020 |
| inference_affirm | -0.6916 | -0.6908 | +0.0008 |
| inference_categories | -0.6916 | -0.6953 | -0.0037 |

## Held-Out Choice Accuracy

| Condition | Acc standard | Acc other |
|-----------|--------------|-----------|
| choice_only | 0.545 | 0.529 |
| inference_affirm | 0.545 | 0.532 |
| inference_categories | 0.545 | 0.510 |

## Significance Tests

| Comparison | n | mean Δ rating | Wilcoxon p |
|------------|---|---------------|------------|
| choice_only vs 0.5 | 20 | +0.010 | 0.4980 |
| inference_affirm vs 0.5 | 20 | +0.004 | 0.2162 |
| inference_categories vs 0.5 | 20 | -0.018 | 0.2455 |
| inference_affirm vs choice_only | 20 | -0.006 | 0.9854 |
| inference_categories vs choice_only | 20 | -0.028 | 0.0484 |

## Learning Curves (test acc by trial count)

Mean held-out accuracy across personas at each checkpoint. Should rise with more trials if learning is working.

| Condition | Fit | T=1 | T=5 | T=10 | T=15 | T=20 |
| --- | --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.517 | 0.523 | 0.520 | 0.537 | 0.545 |
| choice_only | projected | 0.504 | 0.507 | 0.517 | 0.518 | 0.529 |
| inference_affirm | standard | 0.517 | 0.523 | 0.520 | 0.537 | 0.545 |
| inference_affirm | feedback_adjusted | 0.509 | 0.517 | 0.506 | 0.527 | 0.532 |
| inference_categories | standard | 0.517 | 0.523 | 0.520 | 0.537 | 0.545 |
| inference_categories | feedback_adjusted | 0.503 | 0.499 | 0.509 | 0.505 | 0.510 |

**⚠ Non-monotonic learning detected (acc didn't improve from mid-T to end-T):**

- inference_categories/feedback_adjusted: T=11→0.516, T=20→0.510

