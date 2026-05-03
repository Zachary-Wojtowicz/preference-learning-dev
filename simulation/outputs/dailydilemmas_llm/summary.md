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
| choice_only | 0.581 | 0.031 | 100% |
| inference_affirm | 0.578 | 0.029 | 100% |
| inference_categories | 0.564 | 0.040 | 95% |

## Held-Out Log-Likelihood (primary quality signal)

| Condition | LL standard | LL projected | LL partial | Δ proj−std | Δ part−std |
|-----------|-------------|--------------|------------|------------|------------|
| choice_only | -0.6918 | -0.6755 | -0.6755 | +0.0164 | +0.0164 |
| inference_affirm | -0.6918 | -0.6755 | -0.6760 | +0.0164 | +0.0158 |
| inference_categories | -0.6918 | -0.6755 | -0.6789 | +0.0164 | +0.0130 |

## Held-Out Choice Accuracy

| Condition | Acc standard | Acc projected | Acc partial |
|-----------|--------------|---------------|-------------|
| choice_only | 0.686 | 0.703 | 0.703 |
| inference_affirm | 0.686 | 0.703 | 0.694 |
| inference_categories | 0.686 | 0.703 | 0.679 |

## Significance Tests

| Comparison | n | mean Δ rating | Wilcoxon p |
|------------|---|---------------|------------|
| choice_only vs 0.5 | 20 | +0.081 | 0.0000 |
| inference_affirm vs 0.5 | 20 | +0.078 | 0.0000 |
| inference_categories vs 0.5 | 20 | +0.064 | 0.0000 |
| inference_affirm vs choice_only | 20 | -0.002 | 0.8124 |
| inference_categories vs choice_only | 20 | -0.017 | 0.0153 |

## Learning Curves (test acc by trial count)

Mean held-out accuracy across personas at each checkpoint. Should rise with more trials if learning is working.

| Condition | Fit | T=1 | T=5 | T=10 | T=15 | T=20 |
| --- | --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.611 | 0.619 | 0.668 | 0.679 | 0.686 |
| choice_only | projected | 0.627 | 0.633 | 0.700 | 0.702 | 0.703 |
| choice_only | partial | 0.627 | 0.633 | 0.700 | 0.702 | 0.703 |
| inference_affirm | standard | 0.611 | 0.619 | 0.668 | 0.679 | 0.686 |
| inference_affirm | projected | 0.627 | 0.633 | 0.700 | 0.702 | 0.703 |
| inference_affirm | partial | 0.625 | 0.644 | 0.699 | 0.699 | 0.694 |
| inference_categories | standard | 0.611 | 0.619 | 0.668 | 0.679 | 0.686 |
| inference_categories | projected | 0.627 | 0.633 | 0.700 | 0.702 | 0.703 |
| inference_categories | partial | 0.612 | 0.583 | 0.625 | 0.680 | 0.679 |

