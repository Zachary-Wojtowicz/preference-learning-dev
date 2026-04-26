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
| Dimensions | Autonomy, Emotional Honesty, Social Connection, Spontaneity, Conflict Avoidance, Creativity, Efficiency, Humor, Emotional Catharsis, Moral Boundaries, Intellectual Engagement, Comfort, Social Recognition, Cultural Awareness, Identity Exploration, Direct Communication, Emotional Restraint, Social Obligation Avoidance, Digital Convenience, Ethical Responsibility, Financial Stability, Personal Growth, Tradition, Institutional Efficiency, Digital Autonomy |
| Learning rate | 0.01 |
| Projection lambda (partial) | 0.5 |
| Random seed | 42 |

## Final Performance (at last trial)

| Condition | Accuracy | Log-Likelihood |
| --- | --- | --- |
| standard | 0.625 | -0.6923 |
| projected | 0.651 | -0.6927 |
| slider | 0.660 | -0.6926 |
| partial | 0.660 | -0.6925 |

## Learning Curve (Average Accuracy by Trial)

| Trial | standard | projected | slider | partial |
| --- | --- | --- | --- | --- |
| 0 | 0.329 | 0.329 | 0.329 | 0.329 |
| 10 | 0.604 | 0.557 | 0.579 | 0.602 |
| 20 | 0.613 | 0.609 | 0.636 | 0.622 |
| 30 | 0.602 | 0.623 | 0.631 | 0.623 |
| 40 | 0.621 | 0.633 | 0.655 | 0.644 |
| 50 | 0.625 | 0.651 | 0.660 | 0.660 |

## First Trial to Reach 75% Accuracy

| Condition | First Trial >= 75% Accuracy |
|-----------|---------------------------|
| standard | Never reached |
| projected | Never reached |
| slider | Never reached |
| partial | Never reached |

## Internal Consistency

Overall consistency rate: **85.5%**

| Persona | Name | Consistency Rate |
|---------|------|-----------------|
| 0 | Elena, 34 | 90% |
| 1 | Raj, 41 | 80% |
| 2 | Mira, 27 | 60% |
| 3 | Carl, 62 | 90% |
| 4 | Sofia, 29 | 90% |
| 5 | Liam, 53 | 90% |
| 6 | Anika, 31 | 90% |
| 7 | Hiroshi, 45 | 80% |
| 8 | Zoe, 19 | 100% |
| 9 | Marcus, 38 | 80% |
| 10 | Clara, 25 | 100% |
| 11 | Samuel, 68 | 80% |
| 12 | Aisha, 30 | 100% |
| 13 | David, 48 | 90% |
| 14 | Nia, 22 | 90% |
| 15 | Greg, 50 | 60% |
| 16 | Tanya, 36 | 80% |
| 17 | Kevin, 43 | 90% |
| 18 | Lila, 28 | 90% |
| 19 | Ivan, 39 | 80% |

## Key Findings

- **Best final accuracy**: slider (0.660)
- **Standard baseline accuracy**: 0.625
- **Slider vs standard gain**: +0.035
