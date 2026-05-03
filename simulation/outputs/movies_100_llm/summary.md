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
| choice_only | projected | 0.640 | 0.066 | 100% |
| inference_affirm | feedback_adjusted | 0.644 | 0.085 | 90% |
| inference_categories | feedback_adjusted | 0.644 | 0.067 | 95% |

## Held-Out Log-Likelihood (primary quality signal)

| Condition | LL standard | LL other | Δ (other − standard) |
|-----------|-------------|----------|----------------------|
| choice_only | -0.6843 | -0.6549 | +0.0294 |
| inference_affirm | -0.6843 | -0.6539 | +0.0304 |
| inference_categories | -0.6843 | -0.6542 | +0.0301 |

## Held-Out Choice Accuracy

| Condition | Acc standard | Acc other |
|-----------|--------------|-----------|
| choice_only | 0.696 | 0.699 |
| inference_affirm | 0.696 | 0.662 |
| inference_categories | 0.696 | 0.656 |

## Significance Tests

| Comparison | n | mean Δ rating | Wilcoxon p |
|------------|---|---------------|------------|
| choice_only vs 0.5 | 20 | +0.140 | 0.0000 |
| inference_affirm vs 0.5 | 20 | +0.144 | 0.0000 |
| inference_categories vs 0.5 | 20 | +0.144 | 0.0000 |
| inference_affirm vs choice_only | 20 | +0.003 | 0.8983 |
| inference_categories vs choice_only | 20 | +0.003 | 0.6742 |

## Learning Curves (test acc by trial count)

Mean held-out accuracy across personas at each checkpoint. Should rise with more trials if learning is working.

| Condition | Fit | T=1 | T=5 | T=10 | T=15 | T=20 |
| --- | --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.533 | 0.643 | 0.647 | 0.676 | 0.696 |
| choice_only | projected | 0.523 | 0.636 | 0.643 | 0.690 | 0.699 |
| inference_affirm | standard | 0.533 | 0.643 | 0.647 | 0.676 | 0.696 |
| inference_affirm | feedback_adjusted | 0.559 | 0.634 | 0.635 | 0.660 | 0.662 |
| inference_categories | standard | 0.533 | 0.643 | 0.647 | 0.676 | 0.696 |
| inference_categories | feedback_adjusted | 0.539 | 0.631 | 0.632 | 0.653 | 0.656 |

