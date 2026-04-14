# Simulation Summary

## Experimental Parameters

| Parameter | Value |
|-----------|-------|
| Number of users | 50 (5 archetypes, 45 random) |
| Number of trials | 100 |
| Number of test pairs | 200 |
| Number of dimensions (K) | 10 |
| Dimensions | Action vs. Character-Driven, Historical vs. Contemporary, Romantic vs. Non-Romantic, Family-Friendly vs. Adult-Themed, Visual Appeal vs. Narrative Complexity, Humor vs. Seriousness, Classic Adaptation vs. Original Story, Realism vs. Fantasy, Star Power vs. Ensemble Cast, Adventure vs. Drama |
| Beta (choice noise) | 2.0 |
| Slider noise | 0.2 |
| Learning rate | 0.01 |
| Projection lambda (partial) | 0.5 |
| Random seed | 42 |

## Final Performance (at last trial)

| Condition | Accuracy | Log-Likelihood | Utility Pearson | Weight Recovery Pearson |
| --- | --- | --- | --- | --- |
| standard | 0.726 | -1.0846 | 0.621 | 0.674 |
| projected | 0.824 | -0.3704 | 0.833 | 0.674 |
| slider | 0.511 | -0.8582 | 0.007 | 0.077 |
| partial | 0.746 | -0.6050 | 0.671 | 0.698 |

## Learning Curve (Average Accuracy by Trial)

| Trial | standard | projected | slider | partial |
| --- | --- | --- | --- | --- |
| 0 | 0.506 | 0.506 | 0.506 | 0.506 |
| 10 | 0.622 | 0.719 | 0.518 | 0.625 |
| 20 | 0.670 | 0.765 | 0.505 | 0.676 |
| 30 | 0.675 | 0.777 | 0.524 | 0.688 |
| 40 | 0.686 | 0.792 | 0.513 | 0.697 |
| 50 | 0.700 | 0.811 | 0.507 | 0.716 |
| 60 | 0.706 | 0.822 | 0.500 | 0.721 |
| 70 | 0.718 | 0.824 | 0.513 | 0.737 |
| 80 | 0.714 | 0.814 | 0.505 | 0.735 |
| 90 | 0.723 | 0.834 | 0.514 | 0.744 |
| 100 | 0.726 | 0.824 | 0.511 | 0.746 |

## First Trial to Reach 75% Accuracy

| Condition | First Trial ≥ 75% Accuracy |
|-----------|--------------------------|
| standard | Never reached |
| projected | 16 |
| slider | Never reached |
| partial | Never reached |

## Key Findings

- **Best final accuracy**: projected (0.824)
- **Standard baseline accuracy**: 0.726
- **Slider vs standard gain**: -0.215
