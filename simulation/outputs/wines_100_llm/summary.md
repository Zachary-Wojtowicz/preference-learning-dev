# LLM-Persona Simulation Summary

## Experimental Parameters

| Parameter | Value |
|-----------|-------|
| Number of personas | 20 |
| Persona model | Qwen/Qwen3-32B |
| Choice model | Qwen/Qwen3-32B |
| Number of trials | 50 |
| Number of test pairs | 50 |
| Number of dimensions (K) | 15 |
| Dimensions | Fruit Intensity, Body and Structure, Acidity, Oak Influence, Sweetness, Aromatic Complexity, Earthy/Savory Character, Aging Potential, Traditional Style, Value for Money, Effervescence, Playfulness, Tropical Aroma Intensity, Sessionability, Floral Aroma Intensity |
| Learning rate | 0.01 |
| Projection lambda (partial) | 0.5 |
| Random seed | 42 |

## Final Performance (at last trial)

| Condition | Accuracy | Log-Likelihood |
| --- | --- | --- |
| standard | 0.649 | -0.6920 |
| projected | 0.707 | -0.6927 |
| slider | 0.708 | -0.6924 |
| partial | 0.686 | -0.6922 |

## Learning Curve (Average Accuracy by Trial)

| Trial | standard | projected | slider | partial |
| --- | --- | --- | --- | --- |
| 0 | 0.424 | 0.424 | 0.424 | 0.424 |
| 10 | 0.545 | 0.620 | 0.652 | 0.593 |
| 20 | 0.595 | 0.664 | 0.676 | 0.649 |
| 30 | 0.613 | 0.677 | 0.689 | 0.656 |
| 40 | 0.625 | 0.694 | 0.690 | 0.667 |
| 50 | 0.649 | 0.707 | 0.708 | 0.686 |

## First Trial to Reach 75% Accuracy

| Condition | First Trial >= 75% Accuracy |
|-----------|---------------------------|
| standard | Never reached |
| projected | Never reached |
| slider | Never reached |
| partial | Never reached |

## Internal Consistency

Overall consistency rate: **94.0%**

| Persona | Name | Consistency Rate |
|---------|------|-----------------|
| 0 | Elena, 42 | 100% |
| 1 | Marcus, 28 | 100% |
| 2 | Lillian, 67 | 100% |
| 3 | Javier, 35 | 90% |
| 4 | Priya, 31 | 80% |
| 5 | Samuel, 54 | 100% |
| 6 | Zara, 26 | 100% |
| 7 | Hiroshi, 58 | 100% |
| 8 | Rebecca, 39 | 90% |
| 9 | Thomas, 22 | 100% |
| 10 | Clara, 45 | 90% |
| 11 | Kevin, 61 | 100% |
| 12 | Naomi, 33 | 100% |
| 13 | Oscar, 40 | 90% |
| 14 | Anika, 29 | 80% |
| 15 | Greg, 50 | 90% |
| 16 | Mei, 55 | 100% |
| 17 | Dylan, 24 | 90% |
| 18 | Sofia, 37 | 100% |
| 19 | David, 64 | 80% |

## Key Findings

- **Best final accuracy**: slider (0.708)
- **Standard baseline accuracy**: 0.649
- **Slider vs standard gain**: +0.059
