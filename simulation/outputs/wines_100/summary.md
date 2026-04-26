# Simulation Summary

## Experimental Parameters

| Parameter | Value |
|-----------|-------|
| Number of users | 50 (10 archetypes, 40 random) |
| Number of trials | 100 |
| Number of test pairs | 200 |
| Number of dimensions (K) | 15 |
| Dimensions | Fruit Intensity, Body and Structure, Acidity, Oak Influence, Sweetness, Aromatic Complexity, Earthy/Savory Character, Aging Potential, Traditional Style, Value for Money, Effervescence, Playfulness, Tropical Aroma Intensity, Sessionability, Floral Aroma Intensity |
| Beta (choice noise) | 2.0 |
| Slider noise | 0.2 |
| Learning rate | 0.01 |
| Projection lambda (partial) | 0.5 |
| Random seed | 42 |

## Final Performance (at last trial)

| Condition | Accuracy | Log-Likelihood | Utility Pearson | Weight Recovery Pearson |
| --- | --- | --- | --- | --- |
| standard | 0.630 | -0.6919 | 0.480 | 0.475 |
| projected | 0.766 | -0.6921 | 0.830 | 0.475 |
| slider | 0.772 | -0.6924 | 0.845 | 0.510 |
| partial | 0.679 | -0.6921 | 0.622 | 0.493 |

## Learning Curve (Average Accuracy by Trial)

| Trial | standard | projected | slider | partial |
| --- | --- | --- | --- | --- |
| 0 | 0.600 | 0.600 | 0.600 | 0.600 |
| 10 | 0.542 | 0.650 | 0.672 | 0.574 |
| 20 | 0.576 | 0.695 | 0.717 | 0.614 |
| 30 | 0.583 | 0.714 | 0.732 | 0.627 |
| 40 | 0.597 | 0.726 | 0.747 | 0.639 |
| 50 | 0.603 | 0.727 | 0.748 | 0.645 |
| 60 | 0.612 | 0.734 | 0.750 | 0.654 |
| 70 | 0.616 | 0.747 | 0.761 | 0.663 |
| 80 | 0.620 | 0.750 | 0.764 | 0.666 |
| 90 | 0.628 | 0.754 | 0.763 | 0.672 |
| 100 | 0.630 | 0.766 | 0.772 | 0.679 |

## First Trial to Reach 75% Accuracy

| Condition | First Trial ≥ 75% Accuracy |
|-----------|--------------------------|
| standard | Never reached |
| projected | 77 |
| slider | 49 |
| partial | Never reached |

## Key Findings

- **Best final accuracy**: slider (0.772)
- **Standard baseline accuracy**: 0.630
- **Slider vs standard gain**: +0.142
