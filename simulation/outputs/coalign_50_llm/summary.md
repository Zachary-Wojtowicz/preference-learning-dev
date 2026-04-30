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
| Dimensions | Conciseness, Structure, Actionability, Clarity, Emotional Resonance, Depth, Descriptiveness, Sustainability, Community Focus, Historical Context, Practicality, Efficiency, Creativity, Authenticity, Formality |
| Learning rate | 0.01 |
| Projection lambda (partial) | 0.5 |
| Random seed | 42 |

## Final Performance (at last trial)

| Condition | Accuracy | Log-Likelihood |
| --- | --- | --- |
| standard | 0.668 | -0.6904 |
| projected | 0.705 | -0.6923 |
| slider | 0.727 | -0.6920 |
| partial | 0.702 | -0.6912 |

## Learning Curve (Average Accuracy by Trial)

| Trial | standard | projected | slider | partial |
| --- | --- | --- | --- | --- |
| 0 | 0.517 | 0.517 | 0.517 | 0.517 |
| 10 | 0.613 | 0.674 | 0.708 | 0.626 |
| 20 | 0.629 | 0.681 | 0.709 | 0.659 |
| 30 | 0.663 | 0.699 | 0.713 | 0.675 |
| 40 | 0.663 | 0.699 | 0.724 | 0.689 |
| 50 | 0.668 | 0.705 | 0.727 | 0.702 |

## First Trial to Reach 75% Accuracy

| Condition | First Trial >= 75% Accuracy |
|-----------|---------------------------|
| standard | Never reached |
| projected | Never reached |
| slider | Never reached |
| partial | Never reached |

## Internal Consistency

Overall consistency rate: **90.5%**

| Persona | Name | Consistency Rate |
|---------|------|-----------------|
| 0 | **Elena, 32** | 100% |
| 1 | **Miguel, 45** | 100% |
| 2 | **Priya, 27** | 100% |
| 3 | **James, 68** | 100% |
| 4 | **Nadia, 23** | 90% |
| 5 | **Thomas, 51** | 90% |
| 6 | **Linh, 39** | 90% |
| 7 | **Jordan, 35** | 80% |
| 8 | **Sophie, 29** | 90% |
| 9 | **Amir, 41** | 90% |
| 10 | **Clara, 19** | 60% |
| 11 | **Rafael, 56** | 90% |
| 12 | **Grace, 40** | 100% |
| 13 | **Derek, 34** | 90% |
| 14 | **Maya, 26** | 90% |
| 15 | **Oliver, 38** | 90% |
| 16 | **Yara, 24** | 80% |
| 17 | **Harold, 62** | 100% |
| 18 | **Aisha, 31** | 90% |
| 19 | **Leo, 28** | 90% |

## Key Findings

- **Best final accuracy**: slider (0.727)
- **Standard baseline accuracy**: 0.668
- **Slider vs standard gain**: +0.059
