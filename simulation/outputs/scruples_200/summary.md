# Simulation Summary

## Experimental Parameters

| Parameter | Value |
|-----------|-------|
| Number of users | 50 (10 archetypes, 40 random) |
| Number of trials | 100 |
| Number of test pairs | 200 |
| Number of dimensions (K) | 25 |
| Dimensions | Autonomy, Emotional Honesty, Social Connection, Spontaneity, Conflict Avoidance, Creativity, Efficiency, Humor, Emotional Catharsis, Moral Boundaries, Intellectual Engagement, Comfort, Social Recognition, Cultural Awareness, Identity Exploration, Direct Communication, Emotional Restraint, Social Obligation Avoidance, Digital Convenience, Ethical Responsibility, Financial Stability, Personal Growth, Tradition, Institutional Efficiency, Digital Autonomy |
| Beta (choice noise) | 2.0 |
| Slider noise | 0.2 |
| Learning rate | 0.01 |
| Projection lambda (partial) | 0.5 |
| Random seed | 42 |

## Final Performance (at last trial)

| Condition | Accuracy | Log-Likelihood | Utility Pearson | Weight Recovery Pearson |
| --- | --- | --- | --- | --- |
| standard | 0.640 | -0.6918 | 0.458 | 0.523 |
| projected | 0.708 | -0.6921 | 0.665 | 0.523 |
| slider | 0.722 | -0.6924 | 0.715 | 0.651 |
| partial | 0.674 | -0.6921 | 0.561 | 0.574 |

## Learning Curve (Average Accuracy by Trial)

| Trial | standard | projected | slider | partial |
| --- | --- | --- | --- | --- |
| 0 | 0.528 | 0.528 | 0.528 | 0.528 |
| 10 | 0.541 | 0.589 | 0.603 | 0.565 |
| 20 | 0.572 | 0.632 | 0.643 | 0.595 |
| 30 | 0.582 | 0.655 | 0.662 | 0.608 |
| 40 | 0.591 | 0.673 | 0.685 | 0.622 |
| 50 | 0.605 | 0.686 | 0.694 | 0.640 |
| 60 | 0.610 | 0.693 | 0.703 | 0.651 |
| 70 | 0.623 | 0.699 | 0.705 | 0.657 |
| 80 | 0.631 | 0.701 | 0.716 | 0.664 |
| 90 | 0.637 | 0.705 | 0.720 | 0.670 |
| 100 | 0.640 | 0.708 | 0.722 | 0.674 |

## First Trial to Reach 75% Accuracy

| Condition | First Trial ≥ 75% Accuracy |
|-----------|--------------------------|
| standard | Never reached |
| projected | Never reached |
| slider | Never reached |
| partial | Never reached |

## Key Findings

- **Best final accuracy**: slider (0.722)
- **Standard baseline accuracy**: 0.640
- **Slider vs standard gain**: +0.082
