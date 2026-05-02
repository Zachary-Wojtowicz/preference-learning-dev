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
| choice_only | projected | 0.521 | 0.035 | 80% |
| inference_affirm | feedback_adjusted | 0.531 | 0.056 | 75% |
| inference_categories | feedback_adjusted | 0.479 | 0.070 | 35% |

## Held-Out Log-Likelihood (primary quality signal)

| Condition | LL standard | LL other | Δ (other − standard) |
|-----------|-------------|----------|----------------------|
| choice_only | -0.6922 | -0.6881 | +0.0041 |
| inference_affirm | -0.6922 | -0.6860 | +0.0062 |
| inference_categories | -0.6922 | -0.6965 | -0.0043 |

## Held-Out Choice Accuracy

| Condition | Acc standard | Acc other |
|-----------|--------------|-----------|
| choice_only | 0.541 | 0.550 |
| inference_affirm | 0.541 | 0.536 |
| inference_categories | 0.541 | 0.508 |

## Significance Tests

| Comparison | n | mean Δ rating | Wilcoxon p |
|------------|---|---------------|------------|
| choice_only vs 0.5 | 20 | +0.021 | 0.0121 |
| inference_affirm vs 0.5 | 20 | +0.031 | 0.0215 |
| inference_categories vs 0.5 | 20 | -0.021 | 0.2162 |
| inference_affirm vs choice_only | 20 | +0.010 | 0.2611 |
| inference_categories vs choice_only | 20 | -0.042 | 0.0136 |
