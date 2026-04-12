# Preference Basis Evaluation

## Setup

- Options (N): 50
- Embedding dim (d): 3584
- Basis dimensions (k): 10

## Coverage

- **Coverage(V)**: 0.2196
- **PCA upper bound**: 0.3664
- **Relative coverage**: 0.5993

## Per-Dimension Metrics

Dimensions sorted by variance captured (descending).

| Rank | Name | Var(v_j^T δ) | λ_j (PCA) | Independence |
|------|------|--------------|-----------|--------------|
| 1 | Action Intensity | 38.151111 | 66.459476 | 0.8191 |
| 2 | Sci-Fi Elements | 30.583181 | 61.370055 | 0.8916 |
| 3 | Emotional Depth | 30.074980 | 50.979080 | 0.8860 |
| 4 | Music Influence | 25.313018 | 47.706735 | 0.8913 |
| 5 | Character Complexity | 25.165545 | 40.816078 | 0.9285 |
| 6 | Visual Effects | 25.151570 | 39.841907 | 0.9295 |
| 7 | Dialogue Quality | 23.870605 | 35.896085 | 0.9464 |
| 8 | Comedy Level | 23.481872 | 34.378842 | 0.9594 |
| 9 | Historical Accuracy | 23.282810 | 34.106646 | 0.9574 |
| 10 | Pacing Speed | 20.456544 | 31.506548 | 0.9445 |

## Cumulative Variance Ratio (r_j)

Measures how close the top-j proposed dimensions are to the top-j PCA components.

| j | r_j | PCA cumulative variance |
|---|-----|------------------------|
| 1 | 0.5741 | 0.0550 |
| 2 | 0.5377 | 0.1057 |
| 3 | 0.5526 | 0.1479 |
| 4 | 0.5480 | 0.1873 |
| 5 | 0.5584 | 0.2211 |
| 6 | 0.5679 | 0.2540 |
| 7 | 0.5780 | 0.2837 |
| 8 | 0.5876 | 0.3122 |
| 9 | 0.5955 | 0.3404 |
| 10 | 0.5993 | 0.3664 |

## Projected Correlation Matrix (R̂)

| | Action Int | Emotional  | Sci-Fi Ele | Comedy Lev | Historical | Visual Eff | Character  | Dialogue Q | Music Infl | Pacing Spe |
|---|---|---|---|---|---|---|---|---|---|---|
| Action Int | 1.00 | -0.14 | 0.23 | -0.08 | -0.06 | 0.09 | 0.11 | 0.13 | -0.26 | 0.20 |
| Emotional  | -0.14 | 1.00 | -0.17 | -0.10 | 0.17 | -0.11 | 0.17 | -0.03 | -0.03 | -0.05 |
| Sci-Fi Ele | 0.23 | -0.17 | 1.00 | 0.03 | -0.08 | 0.19 | 0.01 | 0.09 | -0.02 | 0.11 |
| Comedy Lev | -0.08 | -0.10 | 0.03 | 1.00 | -0.05 | -0.01 | -0.04 | 0.11 | 0.09 | -0.00 |
| Historical | -0.06 | 0.17 | -0.08 | -0.05 | 1.00 | 0.01 | 0.01 | -0.08 | -0.04 | -0.00 |
| Visual Eff | 0.09 | -0.11 | 0.19 | -0.01 | 0.01 | 1.00 | -0.01 | 0.05 | 0.13 | 0.01 |
| Character  | 0.11 | 0.17 | 0.01 | -0.04 | 0.01 | -0.01 | 1.00 | 0.11 | -0.11 | 0.10 |
| Dialogue Q | 0.13 | -0.03 | 0.09 | 0.11 | -0.08 | 0.05 | 0.11 | 1.00 | 0.02 | 0.06 |
| Music Infl | -0.26 | -0.03 | -0.02 | 0.09 | -0.04 | 0.13 | -0.11 | 0.02 | 1.00 | -0.11 |
| Pacing Spe | 0.20 | -0.05 | 0.11 | -0.00 | -0.00 | 0.01 | 0.10 | 0.06 | -0.11 | 1.00 |
