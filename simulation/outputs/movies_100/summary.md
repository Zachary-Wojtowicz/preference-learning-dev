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
| slider | 0.795 | -0.6911 | 0.791 | 0.684 |
| partial | 0.793 | -0.6902 | 0.781 | 0.626 |

## Learning Curve (Average Accuracy by Trial)

| Trial | standard | projected | slider | partial |
| --- | --- | --- | --- | --- |
| 0 | 0.500 | 0.500 | 0.500 | 0.500 |
| 10 | 0.647 | 0.696 | 0.702 | 0.677 |
| 20 | 0.681 | 0.735 | 0.743 | 0.714 |
| 30 | 0.694 | 0.751 | 0.753 | 0.728 |
| 40 | 0.707 | 0.768 | 0.757 | 0.740 |
| 50 | 0.721 | 0.779 | 0.766 | 0.751 |
| 60 | 0.734 | 0.793 | 0.774 | 0.761 |
| 70 | 0.739 | 0.800 | 0.781 | 0.772 |
| 80 | 0.750 | 0.810 | 0.787 | 0.780 |
| 90 | 0.762 | 0.811 | 0.790 | 0.788 |
| 100 | 0.765 | 0.817 | 0.795 | 0.793 |

## First Trial to Reach 75% Accuracy

| Condition | First Trial ≥ 75% Accuracy |
|-----------|--------------------------|
| standard | 81 |
| projected | 30 |
| slider | 28 |
| partial | 49 |

## Key Findings

- **Best final accuracy**: projected (0.817)
- **Standard baseline accuracy**: 0.765
- **Slider vs standard gain**: +0.031
