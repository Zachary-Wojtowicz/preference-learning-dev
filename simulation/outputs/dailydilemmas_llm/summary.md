# LLM-Persona Simulation Summary

## Experimental Parameters

| Parameter | Value |
|-----------|-------|
| Number of personas | 20 |
| Persona model | Qwen/Qwen3-32B |
| Choice model | Qwen/Qwen3-32B |
| Number of trials | 50 |
| Number of test pairs | 50 |
| Number of dimensions (K) | 20 |
| Dimensions | Moral Integrity, Conflict Avoidance, Emotional Well-Being, Risk Aversion, Autonomy, Social Harmony, Long-Term Orientation, Formality Avoidance, Emotional Authenticity, Tradition Adherence, Efficiency, Privacy, Financial Prudence, Decisiveness, Creativity, Structure Preference, Empathy, Duty Orientation, Stability, Experience Orientation |
| Learning rate | 0.01 |
| Projection lambda (partial) | 0.5 |
| Random seed | 42 |

## Final Performance (at last trial)

| Condition | Accuracy | Log-Likelihood |
| --- | --- | --- |
| standard | 0.574 | -0.6928 |
| projected | 0.553 | -0.6929 |
| slider | 0.572 | -0.6928 |
| partial | 0.585 | -0.6928 |

## Learning Curve (Average Accuracy by Trial)

| Trial | standard | projected | slider | partial |
| --- | --- | --- | --- | --- |
| 0 | 0.343 | 0.343 | 0.343 | 0.343 |
| 10 | 0.531 | 0.529 | 0.537 | 0.541 |
| 20 | 0.549 | 0.554 | 0.557 | 0.570 |
| 30 | 0.564 | 0.565 | 0.569 | 0.580 |
| 40 | 0.572 | 0.561 | 0.554 | 0.582 |
| 50 | 0.574 | 0.553 | 0.572 | 0.585 |

## First Trial to Reach 75% Accuracy

| Condition | First Trial >= 75% Accuracy |
|-----------|---------------------------|
| standard | Never reached |
| projected | Never reached |
| slider | Never reached |
| partial | Never reached |

## Internal Consistency

Overall consistency rate: **79.5%**

| Persona | Name | Consistency Rate |
|---------|------|-----------------|
| 0 | Elena, 28 | 100% |
| 1 | Marcus, 45 | 80% |
| 2 | Priya, 33 | 70% |
| 3 | Javier, 61 | 90% |
| 4 | Aisha, 29 | 90% |
| 5 | Daniel, 54 | 70% |
| 6 | Lina, 22 | 60% |
| 7 | Tom, 58 | 80% |
| 8 | Samira, 37 | 80% |
| 9 | Henry, 66 | 90% |
| 10 | Naomi, 41 | 80% |
| 11 | Kevin, 30 | 80% |
| 12 | Mei, 50 | 60% |
| 13 | Carlos, 43 | 70% |
| 14 | Rebecca, 35 | 100% |
| 15 | Ivan, 52 | 90% |
| 16 | Chloe, 26 | 80% |
| 17 | George, 60 | 90% |
| 18 | Nia, 39 | 50% |
| 19 | Lucas, 27 | 80% |

## Key Findings

- **Best final accuracy**: partial (0.585)
- **Standard baseline accuracy**: 0.574
- **Slider vs standard gain**: -0.002
