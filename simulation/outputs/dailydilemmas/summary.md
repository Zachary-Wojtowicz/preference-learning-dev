# Simulation Summary

## Experimental Parameters

| Parameter | Value |
|-----------|-------|
| Number of users | 50 (10 archetypes, 40 random) |
| Number of trials | 100 |
| Number of test pairs | 200 |
| Number of dimensions (K) | 20 |
| Dimensions | Moral Integrity, Conflict Avoidance, Emotional Well-Being, Risk Aversion, Autonomy, Social Harmony, Long-Term Orientation, Formality Avoidance, Emotional Authenticity, Tradition Adherence, Efficiency, Privacy, Financial Prudence, Decisiveness, Creativity, Structure Preference, Empathy, Duty Orientation, Stability, Experience Orientation |
| Beta (choice noise) | 2.0 |
| Slider noise | 0.2 |
| Learning rate | 0.01 |
| Projection lambda (partial) | 0.5 |
| Random seed | 42 |

## Final Performance (at last trial)

| Condition | Accuracy | Log-Likelihood | Utility Pearson | Weight Recovery Pearson |
| --- | --- | --- | --- | --- |
| standard | 0.567 | -0.6925 | 0.241 | 0.405 |
| projected | 0.597 | -0.6926 | 0.356 | 0.405 |
| slider | 0.597 | -0.6928 | 0.366 | 0.540 |
| partial | 0.588 | -0.6927 | 0.300 | 0.464 |

## Learning Curve (Average Accuracy by Trial)

| Trial | standard | projected | slider | partial |
| --- | --- | --- | --- | --- |
| 0 | 0.567 | 0.567 | 0.567 | 0.567 |
| 10 | 0.519 | 0.531 | 0.537 | 0.529 |
| 20 | 0.533 | 0.551 | 0.556 | 0.543 |
| 30 | 0.538 | 0.565 | 0.567 | 0.548 |
| 40 | 0.550 | 0.565 | 0.567 | 0.558 |
| 50 | 0.552 | 0.574 | 0.577 | 0.559 |
| 60 | 0.562 | 0.585 | 0.588 | 0.577 |
| 70 | 0.563 | 0.586 | 0.590 | 0.576 |
| 80 | 0.566 | 0.593 | 0.596 | 0.582 |
| 90 | 0.567 | 0.593 | 0.599 | 0.581 |
| 100 | 0.567 | 0.597 | 0.597 | 0.588 |

## First Trial to Reach 75% Accuracy

| Condition | First Trial ≥ 75% Accuracy |
|-----------|--------------------------|
| standard | Never reached |
| projected | Never reached |
| slider | Never reached |
| partial | Never reached |

## Key Findings

- **Best final accuracy**: projected (0.597)
- **Standard baseline accuracy**: 0.567
- **Slider vs standard gain**: +0.030
