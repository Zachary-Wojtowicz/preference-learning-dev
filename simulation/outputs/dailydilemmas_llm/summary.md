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
| choice_only | 0.814 | 0.093 | 100% |
| inference_affirm | 0.821 | 0.085 | 100% |
| inference_categories | 0.794 | 0.094 | 100% |

## Held-Out Log-Likelihood (primary quality signal)

| Condition | LL standard | LL projected | LL partial | Δ proj−std | Δ part−std |
|-----------|-------------|--------------|------------|------------|------------|
| choice_only | -0.6918 | -0.6132 | -0.6132 | +0.0787 | +0.0787 |
| inference_affirm | -0.6918 | -0.6132 | -0.6116 | +0.0787 | +0.0803 |
| inference_categories | -0.6918 | -0.6132 | -0.6198 | +0.0787 | +0.0721 |

## Held-Out Choice Accuracy

| Condition | Acc standard | Acc projected | Acc partial |
|-----------|--------------|---------------|-------------|
| choice_only | 0.686 | 0.708 | 0.708 |
| inference_affirm | 0.686 | 0.708 | 0.705 |
| inference_categories | 0.686 | 0.708 | 0.708 |

## Significance Tests

| Comparison | n | mean Δ rating | Wilcoxon p |
|------------|---|---------------|------------|
| choice_only vs 0.5 | 20 | +0.314 | 0.0000 |
| inference_affirm vs 0.5 | 20 | +0.321 | 0.0000 |
| inference_categories vs 0.5 | 20 | +0.294 | 0.0000 |
| inference_affirm vs choice_only | 20 | +0.007 | 0.3488 |
| inference_categories vs choice_only | 20 | -0.020 | 0.0696 |

## Learning Curves (test acc by trial count)

Mean held-out accuracy across personas at each checkpoint. Should rise with more trials if learning is working.

| Condition | Fit | T=1 | T=5 | T=10 | T=15 | T=20 |
| --- | --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.611 | 0.619 | 0.668 | 0.679 | 0.686 |
| choice_only | projected | 0.627 | 0.631 | 0.707 | 0.706 | 0.708 |
| choice_only | partial | 0.627 | 0.631 | 0.707 | 0.706 | 0.708 |
| inference_affirm | standard | 0.611 | 0.619 | 0.668 | 0.679 | 0.686 |
| inference_affirm | projected | 0.627 | 0.631 | 0.707 | 0.706 | 0.708 |
| inference_affirm | partial | 0.627 | 0.650 | 0.711 | 0.712 | 0.705 |
| inference_categories | standard | 0.611 | 0.619 | 0.668 | 0.679 | 0.686 |
| inference_categories | projected | 0.627 | 0.631 | 0.707 | 0.706 | 0.708 |
| inference_categories | partial | 0.617 | 0.618 | 0.685 | 0.711 | 0.708 |

