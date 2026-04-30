# Simulation Summary

## Experimental Parameters

| Parameter | Value |
|-----------|-------|
| Number of users | 50 (10 archetypes, 40 random) |
| Number of trials | 100 |
| Number of test pairs | 200 |
| Number of dimensions (K) | 15 |
| Dimensions | Conciseness, Structure, Actionability, Clarity, Emotional Resonance, Depth, Descriptiveness, Sustainability, Community Focus, Historical Context, Practicality, Efficiency, Creativity, Authenticity, Formality |
| Beta (choice noise) | 2.0 |
| Slider noise | 0.2 |
| Learning rate | 0.01 |
| Projection lambda (partial) | 0.5 |
| Random seed | 42 |

## Final Performance (at last trial)

| Condition | Accuracy | Log-Likelihood | Utility Pearson | Weight Recovery Pearson |
| --- | --- | --- | --- | --- |
| standard | 0.707 | -0.6884 | 0.618 | 0.443 |
| projected | 0.765 | -0.6913 | 0.760 | 0.443 |
| slider | 0.774 | -0.6920 | 0.777 | 0.597 |
| partial | 0.726 | -0.6902 | 0.665 | 0.506 |

## Learning Curve (Average Accuracy by Trial)

| Trial | standard | projected | slider | partial |
| --- | --- | --- | --- | --- |
| 0 | 0.540 | 0.540 | 0.540 | 0.540 |
| 10 | 0.588 | 0.675 | 0.677 | 0.601 |
| 20 | 0.601 | 0.700 | 0.696 | 0.616 |
| 30 | 0.635 | 0.724 | 0.729 | 0.653 |
| 40 | 0.647 | 0.742 | 0.744 | 0.669 |
| 50 | 0.666 | 0.739 | 0.748 | 0.685 |
| 60 | 0.675 | 0.748 | 0.757 | 0.697 |
| 70 | 0.685 | 0.752 | 0.763 | 0.704 |
| 80 | 0.698 | 0.767 | 0.770 | 0.718 |
| 90 | 0.702 | 0.767 | 0.773 | 0.725 |
| 100 | 0.707 | 0.765 | 0.774 | 0.726 |

## First Trial to Reach 75% Accuracy

| Condition | First Trial ≥ 75% Accuracy |
|-----------|--------------------------|
| standard | Never reached |
| projected | 61 |
| slider | 51 |
| partial | Never reached |

## Key Findings

- **Best final accuracy**: slider (0.774)
- **Standard baseline accuracy**: 0.707
- **Slider vs standard gain**: +0.067
