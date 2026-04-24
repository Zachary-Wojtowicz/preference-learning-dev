# LLM-Persona Simulation Summary

## Experimental Parameters

| Parameter | Value |
|-----------|-------|
| Number of personas | 20 |
| Persona model | Qwen/Qwen3-32B |
| Choice model | Qwen/Qwen3-32B |
| Number of trials | 50 |
| Number of test pairs | 50 |
| Number of dimensions (K) | 25 |
| Dimensions | Emotional Depth, Action Intensity, Humor Intensity, Historical Authenticity, Moral Complexity, Suspense/Atmosphere, Family Focus, Sci-Fi/Fantasy Worldbuilding, Political Intrigue, Satirical Edge, Survival/Stress Scenarios, Visual Spectacle, Coming-of-Age Focus, Nostalgic Aesthetics, Ensemble Cast Dynamics, Social Justice Themes, Cultural Authenticity, Psychological Depth, Adventure Scope, Musical Integration, Time-Loop Mechanics, Romantic Subplots, Underdog Arcs, War/Military Focus, Family-Friendly Content |
| Learning rate | 0.01 |
| Projection lambda (partial) | 0.5 |
| Random seed | 42 |

## Final Performance (at last trial)

| Condition | Accuracy | Log-Likelihood |
| --- | --- | --- |
| standard | 0.725 | -0.6909 |
| projected | 0.721 | -0.6919 |
| slider | 0.729 | -0.6911 |
| partial | 0.751 | -0.6910 |

## Learning Curve (Average Accuracy by Trial)

| Trial | standard | projected | slider | partial |
| --- | --- | --- | --- | --- |
| 0 | 0.429 | 0.429 | 0.429 | 0.429 |
| 10 | 0.663 | 0.675 | 0.705 | 0.717 |
| 20 | 0.698 | 0.690 | 0.725 | 0.737 |
| 30 | 0.721 | 0.712 | 0.728 | 0.743 |
| 40 | 0.707 | 0.715 | 0.720 | 0.750 |
| 50 | 0.725 | 0.721 | 0.729 | 0.751 |

## First Trial to Reach 75% Accuracy

| Condition | First Trial >= 75% Accuracy |
|-----------|---------------------------|
| standard | Never reached |
| projected | Never reached |
| slider | Never reached |
| partial | 34 |

## Internal Consistency

Overall consistency rate: **89.5%**

| Persona | Name | Consistency Rate |
|---------|------|-----------------|
| 0 | Clara, 28 | 80% |
| 1 | Raj, 42 | 90% |
| 2 | Evelyn, 67 | 90% |
| 3 | Marcus, 35 | 100% |
| 4 | Zoe, 21 | 90% |
| 5 | David, 50 | 90% |
| 6 | Lila, 31 | 100% |
| 7 | Amir, 29 | 100% |
| 8 | Hannah, 19 | 90% |
| 9 | George, 72 | 80% |
| 10 | Nina, 26 | 90% |
| 11 | Javier, 46 | 70% |
| 12 | Priya, 37 | 90% |
| 13 | Kevin, 40 | 100% |
| 14 | Aisha, 24 | 100% |
| 15 | Samuel, 55 | 80% |
| 16 | Lena, 33 | 70% |
| 17 | Elijah, 27 | 90% |
| 18 | Sofia, 30 | 90% |
| 19 | Tyler, 18 | 100% |

## Key Findings

- **Best final accuracy**: partial (0.751)
- **Standard baseline accuracy**: 0.725
- **Slider vs standard gain**: +0.004
