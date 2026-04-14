# Simulation Summary

## Experimental Parameters

| Parameter | Value |
|-----------|-------|
| Number of users | 50 (5 archetypes, 45 random) |
| Number of trials | 100 |
| Number of test pairs | 200 |
| Number of dimensions (K) | 10 |
| Dimensions | Directness vs. Indirectness in Communication, Conflict Avoidance vs. Confrontation, Privacy and Personal Space vs. Social Bonding, Professional Responsibility vs. Personal Freedom, Trust and Honesty vs. Skepticism, Financial Responsibility vs. Immediate Gratification, Cultural Traditions vs. Modernity, Empathy and Compassion vs. Detachment, Legal and Ethical Concerns vs. Personal Convenience, Mental Health Considerations vs. Social Expectations |
| Beta (choice noise) | 2.0 |
| Slider noise | 0.2 |
| Learning rate | 0.01 |
| Projection lambda (partial) | 0.5 |
| Random seed | 42 |

## Final Performance (at last trial)

| Condition | Accuracy | Log-Likelihood | Utility Pearson | Weight Recovery Pearson |
| --- | --- | --- | --- | --- |
| standard | 0.671 | -0.6920 | 0.564 | 0.517 |
| projected | 0.696 | -0.6921 | 0.617 | 0.517 |
| slider | 0.507 | -0.6932 | 0.002 | -0.015 |
| partial | 0.638 | -0.6926 | 0.435 | 0.296 |

## Learning Curve (Average Accuracy by Trial)

| Trial | standard | projected | slider | partial |
| --- | --- | --- | --- | --- |
| 0 | 0.553 | 0.553 | 0.553 | 0.553 |
| 10 | 0.611 | 0.618 | 0.515 | 0.568 |
| 20 | 0.628 | 0.648 | 0.514 | 0.576 |
| 30 | 0.637 | 0.654 | 0.497 | 0.589 |
| 40 | 0.656 | 0.674 | 0.490 | 0.592 |
| 50 | 0.656 | 0.673 | 0.477 | 0.599 |
| 60 | 0.661 | 0.684 | 0.496 | 0.611 |
| 70 | 0.667 | 0.685 | 0.491 | 0.622 |
| 80 | 0.669 | 0.694 | 0.511 | 0.627 |
| 90 | 0.673 | 0.693 | 0.507 | 0.622 |
| 100 | 0.671 | 0.696 | 0.507 | 0.638 |

## First Trial to Reach 75% Accuracy

| Condition | First Trial ≥ 75% Accuracy |
|-----------|--------------------------|
| standard | Never reached |
| projected | Never reached |
| slider | Never reached |
| partial | Never reached |

## Key Findings

- **Best final accuracy**: projected (0.696)
- **Standard baseline accuracy**: 0.671
- **Slider vs standard gain**: -0.164
