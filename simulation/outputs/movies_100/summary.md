# Simulation Summary

## Experimental Parameters

| Parameter | Value |
|-----------|-------|
| Number of users | 50 (10 archetypes, 40 random) |
| Number of trials | 100 |
| Number of test pairs | 200 |
| Number of dimensions (K) | 25 |
| Dimensions | Emotional Depth, Action Intensity, Humor Intensity, Historical Authenticity, Moral Complexity, Suspense/Atmosphere, Family Focus, Sci-Fi/Fantasy Worldbuilding, Political Intrigue, Satirical Edge, Survival/Stress Scenarios, Visual Spectacle, Coming-of-Age Focus, Nostalgic Aesthetics, Ensemble Cast Dynamics, Social Justice Themes, Cultural Authenticity, Psychological Depth, Adventure Scope, Musical Integration, Time-Loop Mechanics, Romantic Subplots, Underdog Arcs, War/Military Focus, Family-Friendly Content |
| Beta (choice noise) | 2.0 |
| Slider noise | 0.2 |
| Learning rate | 0.01 |
| Projection lambda (partial) | 0.5 |
| Random seed | 42 |

## Final Performance (at last trial)

| Condition | Accuracy | Log-Likelihood | Utility Pearson | Weight Recovery Pearson |
| --- | --- | --- | --- | --- |
| standard | 0.765 | -0.6894 | 0.715 | 0.571 |
| projected | 0.817 | -0.6903 | 0.823 | 0.571 |
| slider | 0.587 | -0.6924 | 0.282 | 0.300 |
| partial | 0.750 | -0.6909 | 0.696 | 0.557 |

## Learning Curve (Average Accuracy by Trial)

| Trial | standard | projected | slider | partial |
| --- | --- | --- | --- | --- |
| 0 | 0.500 | 0.500 | 0.500 | 0.500 |
| 10 | 0.647 | 0.696 | 0.574 | 0.650 |
| 20 | 0.681 | 0.735 | 0.578 | 0.679 |
| 30 | 0.694 | 0.751 | 0.578 | 0.696 |
| 40 | 0.707 | 0.768 | 0.582 | 0.706 |
| 50 | 0.721 | 0.779 | 0.587 | 0.721 |
| 60 | 0.734 | 0.793 | 0.586 | 0.730 |
| 70 | 0.739 | 0.800 | 0.588 | 0.735 |
| 80 | 0.750 | 0.810 | 0.592 | 0.743 |
| 90 | 0.762 | 0.811 | 0.593 | 0.750 |
| 100 | 0.765 | 0.817 | 0.587 | 0.750 |

## First Trial to Reach 75% Accuracy

| Condition | First Trial ≥ 75% Accuracy |
|-----------|--------------------------|
| standard | 81 |
| projected | 30 |
| slider | Never reached |
| partial | 91 |

## Key Findings

- **Best final accuracy**: projected (0.817)
- **Standard baseline accuracy**: 0.765
- **Slider vs standard gain**: -0.177
