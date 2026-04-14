# LLM-Persona Simulation Summary

## Experimental Parameters

| Parameter | Value |
|-----------|-------|
| Number of personas | 19 |
| Persona model | Qwen/Qwen2.5-32B-Instruct |
| Choice model | Qwen/Qwen2.5-32B-Instruct |
| Number of trials | 50 |
| Number of test pairs | 50 |
| Number of dimensions (K) | 10 |
| Dimensions | Action Intensity, Emotional Depth, Sci-Fi Elements, Comedy Level, Historical Accuracy, Visual Effects, Character Complexity, Dialogue Quality, Music Influence, Pacing Speed |
| Learning rate | 0.01 |
| Projection lambda (partial) | 0.5 |
| Random seed | 42 |

## Final Performance (at last trial)

| Condition | Accuracy | Log-Likelihood |
| --- | --- | --- |
| standard | 0.723 | -0.9030 |
| projected | 0.748 | -0.5424 |
| slider | 0.557 | -1.3084 |
| partial | 0.747 | -0.6235 |

## Learning Curve (Average Accuracy by Trial)

| Trial | standard | projected | slider | partial |
| --- | --- | --- | --- | --- |
| 0 | 0.495 | 0.495 | 0.495 | 0.495 |
| 10 | 0.653 | 0.667 | 0.581 | 0.663 |
| 20 | 0.664 | 0.694 | 0.579 | 0.689 |
| 30 | 0.693 | 0.722 | 0.622 | 0.716 |
| 40 | 0.706 | 0.735 | 0.585 | 0.739 |
| 50 | 0.723 | 0.748 | 0.557 | 0.747 |

## First Trial to Reach 75% Accuracy

| Condition | First Trial >= 75% Accuracy |
|-----------|---------------------------|
| standard | Never reached |
| projected | 47 |
| slider | Never reached |
| partial | 44 |

## Internal Consistency

Overall consistency rate: **97.4%**

| Persona | Name | Consistency Rate |
|---------|------|-----------------|
| 0 | Liam, 29 | 100% |
| 1 | Maria, 45 | 100% |
| 2 | Carlos, 32 | 100% |
| 3 | Olivia, 18 | 100% |
| 4 | Ethan, 60 | 80% |
| 5 | Priya, 27 | 100% |
| 6 | Jake, 35 | 90% |
| 7 | Zoe, 50 | 100% |
| 8 | Raj, 42 | 100% |
| 9 | Ava, 23 | 100% |
| 10 | Ben, 47 | 90% |
| 11 | Nora, 30 | 100% |
| 12 | Diego, 28 | 100% |
| 13 | Lila, 55 | 100% |
| 14 | Sam, 33 | 90% |
| 15 | Jade, 26 | 100% |
| 16 | Theo, 40 | 100% |
| 17 | Mia, 24 | 100% |
| 18 | Alex, 37 | 100% |

## Key Findings

- **Best final accuracy**: projected (0.748)
- **Standard baseline accuracy**: 0.723
- **Slider vs standard gain**: -0.166
