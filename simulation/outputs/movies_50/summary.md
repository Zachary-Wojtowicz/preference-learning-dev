# Simulation Summary

## Experimental Parameters

| Parameter | Value |
|-----------|-------|
| Number of users | 50 (5 archetypes, 45 random) |
| Number of trials | 100 |
| Number of test pairs | 200 |
| Number of dimensions (K) | 10 |
| Dimensions | Action Intensity, Emotional Depth, Sci-Fi Elements, Comedy Level, Historical Accuracy, Visual Effects, Character Complexity, Dialogue Quality, Music Influence, Pacing Speed |
| Beta (choice noise) | 2.0 |
| Slider noise | 0.2 |
| Learning rate | 0.01 |
| Projection lambda (partial) | 0.5 |
| Random seed | 42 |

## Final Performance (at last trial)

| Condition | Accuracy | Log-Likelihood | Utility Pearson | Weight Recovery Pearson |
| --- | --- | --- | --- | --- |
| standard | 0.722 | -1.0462 | 0.628 | 0.594 |
| projected | 0.846 | -0.3451 | 0.868 | 0.619 |
| slider | 0.541 | -0.8009 | 0.109 | 0.047 |
| partial | 0.747 | -0.5980 | 0.672 | 0.614 |

## Learning Curve (Average Accuracy by Trial)

| Trial | standard | projected | slider | partial |
| --- | --- | --- | --- | --- |
| 0 | 0.504 | 0.504 | 0.504 | 0.504 |
| 10 | 0.633 | 0.732 | 0.491 | 0.633 |
| 20 | 0.661 | 0.774 | 0.480 | 0.668 |
| 30 | 0.676 | 0.797 | 0.478 | 0.691 |
| 40 | 0.695 | 0.818 | 0.497 | 0.706 |
| 50 | 0.696 | 0.829 | 0.501 | 0.715 |
| 60 | 0.704 | 0.840 | 0.509 | 0.723 |
| 70 | 0.711 | 0.830 | 0.512 | 0.725 |
| 80 | 0.705 | 0.828 | 0.536 | 0.732 |
| 90 | 0.721 | 0.843 | 0.537 | 0.741 |
| 100 | 0.722 | 0.846 | 0.541 | 0.747 |

## First Trial to Reach 75% Accuracy

| Condition | First Trial ≥ 75% Accuracy |
|-----------|--------------------------|
| standard | Never reached |
| projected | 12 |
| slider | Never reached |
| partial | Never reached |

## Key Findings

- **Best final accuracy**: projected (0.846)
- **Standard baseline accuracy**: 0.722
- **Slider vs standard gain**: -0.180
