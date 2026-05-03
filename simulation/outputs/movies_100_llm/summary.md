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
| choice_only | 0.729 | 0.105 | 100% |
| inference_affirm | 0.711 | 0.112 | 95% |
| inference_categories | 0.721 | 0.098 | 95% |

## Held-Out Log-Likelihood (primary quality signal)

| Condition | LL standard | LL projected | LL partial | Δ proj−std | Δ part−std |
|-----------|-------------|--------------|------------|------------|------------|
| choice_only | -0.6843 | -0.6317 | -0.6317 | +0.0526 | +0.0526 |
| inference_affirm | -0.6843 | -0.6317 | -0.6369 | +0.0526 | +0.0474 |
| inference_categories | -0.6843 | -0.6317 | -0.6347 | +0.0526 | +0.0496 |

## Held-Out Choice Accuracy

| Condition | Acc standard | Acc projected | Acc partial |
|-----------|--------------|---------------|-------------|
| choice_only | 0.696 | 0.695 | 0.695 |
| inference_affirm | 0.696 | 0.695 | 0.664 |
| inference_categories | 0.696 | 0.695 | 0.658 |

## Significance Tests

| Comparison | n | mean Δ rating | Wilcoxon p |
|------------|---|---------------|------------|
| choice_only vs 0.5 | 20 | +0.229 | 0.0000 |
| inference_affirm vs 0.5 | 20 | +0.211 | 0.0000 |
| inference_categories vs 0.5 | 20 | +0.221 | 0.0000 |
| inference_affirm vs choice_only | 20 | -0.019 | 0.4980 |
| inference_categories vs choice_only | 20 | -0.009 | 0.5217 |

## Learning Curves (test acc by trial count)

Mean held-out accuracy across personas at each checkpoint. Should rise with more trials if learning is working.

| Condition | Fit | T=1 | T=5 | T=10 | T=15 | T=20 |
| --- | --- | --- | --- | --- | --- | --- |
| choice_only | standard | 0.533 | 0.643 | 0.647 | 0.676 | 0.696 |
| choice_only | projected | 0.523 | 0.637 | 0.643 | 0.690 | 0.695 |
| choice_only | partial | 0.523 | 0.637 | 0.643 | 0.690 | 0.695 |
| inference_affirm | standard | 0.533 | 0.643 | 0.647 | 0.676 | 0.696 |
| inference_affirm | projected | 0.523 | 0.637 | 0.643 | 0.690 | 0.695 |
| inference_affirm | partial | 0.559 | 0.636 | 0.637 | 0.659 | 0.664 |
| inference_categories | standard | 0.533 | 0.643 | 0.647 | 0.676 | 0.696 |
| inference_categories | projected | 0.523 | 0.637 | 0.643 | 0.690 | 0.695 |
| inference_categories | partial | 0.539 | 0.629 | 0.631 | 0.662 | 0.658 |

