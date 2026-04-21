# Simulation Summary

## Experimental Parameters

| Parameter | Value |
|-----------|-------|
| Number of users | 50 (10 archetypes, 40 random) |
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
| standard | 0.702 | -1.2723 | 0.603 | 0.591 |
| projected | 0.814 | -0.4104 | 0.848 | 0.607 |
| slider | 0.829 | -0.4411 | 0.890 | 0.625 |
| partial | 0.723 | -0.7070 | 0.665 | 0.611 |

## Learning Curve (Average Accuracy by Trial)

| Trial | standard | projected | slider | partial |
| --- | --- | --- | --- | --- |
| 0 | 0.538 | 0.538 | 0.538 | 0.538 |
| 10 | 0.602 | 0.693 | 0.696 | 0.622 |
| 20 | 0.613 | 0.723 | 0.732 | 0.637 |
| 30 | 0.642 | 0.753 | 0.758 | 0.660 |
| 40 | 0.659 | 0.779 | 0.778 | 0.682 |
| 50 | 0.672 | 0.791 | 0.797 | 0.698 |
| 60 | 0.674 | 0.795 | 0.810 | 0.695 |
| 70 | 0.673 | 0.781 | 0.811 | 0.701 |
| 80 | 0.685 | 0.787 | 0.818 | 0.705 |
| 90 | 0.702 | 0.798 | 0.822 | 0.725 |
| 100 | 0.702 | 0.814 | 0.829 | 0.723 |

## First Trial to Reach 75% Accuracy

| Condition | First Trial ≥ 75% Accuracy |
|-----------|--------------------------|
| standard | Never reached |
| projected | 29 |
| slider | 28 |
| partial | Never reached |

## Key Findings

- **Best final accuracy**: slider (0.829)
- **Standard baseline accuracy**: 0.702
- **Slider vs standard gain**: +0.127
