# Preference Basis Evaluation

## Setup

- Options (N): 50
- Embedding dim (d): 3584
- Basis dimensions (k): 10

## Coverage

- **Coverage(V)**: 0.2417
- **PCA upper bound**: 0.3664
- **Relative coverage**: 0.6597

## Per-Dimension Metrics

Dimensions sorted by variance captured (descending).

| Rank | Name | Var(v_j^T δ) | λ_j (PCA) | Independence |
|------|------|--------------|-----------|--------------|
| 1 | Action vs. Character-Driven | 39.114710 | 66.459476 | 0.8528 |
| 2 | Family-Friendly vs. Adult-Themed | 36.900956 | 61.370055 | 0.9551 |
| 3 | Romantic vs. Non-Romantic | 33.741669 | 50.979080 | 0.9406 |
| 4 | Classic Adaptation vs. Original Sto | 30.218765 | 47.706735 | 0.9190 |
| 5 | Realism vs. Fantasy | 29.131544 | 40.816078 | 0.8858 |
| 6 | Historical vs. Contemporary | 27.721149 | 39.841907 | 0.9244 |
| 7 | Adventure vs. Drama | 24.953311 | 35.896085 | 0.9451 |
| 8 | Humor vs. Seriousness | 24.189857 | 34.378842 | 0.9769 |
| 9 | Star Power vs. Ensemble Cast | 24.043790 | 34.106646 | 0.9679 |
| 10 | Visual Appeal vs. Narrative Complex | 22.278621 | 31.506548 | 0.9480 |

## Cumulative Variance Ratio (r_j)

Measures how close the top-j proposed dimensions are to the top-j PCA components.

| j | r_j | PCA cumulative variance |
|---|-----|------------------------|
| 1 | 0.5885 | 0.0550 |
| 2 | 0.5947 | 0.1057 |
| 3 | 0.6138 | 0.1479 |
| 4 | 0.6180 | 0.1873 |
| 5 | 0.6326 | 0.2211 |
| 6 | 0.6408 | 0.2540 |
| 7 | 0.6465 | 0.2837 |
| 8 | 0.6517 | 0.3122 |
| 9 | 0.6561 | 0.3404 |
| 10 | 0.6597 | 0.3664 |

## Projected Correlation Matrix (R̂)

| | Action vs. | Historical | Romantic v | Family-Fri | Visual App | Humor vs.  | Classic Ad | Realism vs | Star Power | Adventure  |
|---|---|---|---|---|---|---|---|---|---|---|
| Action vs. | 1.00 | -0.13 | 0.15 | 0.06 | -0.09 | -0.05 | 0.13 | 0.27 | -0.12 | -0.12 |
| Historical | -0.13 | 1.00 | 0.05 | -0.04 | -0.03 | 0.06 | -0.21 | -0.05 | 0.05 | -0.03 |
| Romantic v | 0.15 | 0.05 | 1.00 | 0.09 | 0.01 | 0.03 | 0.05 | 0.15 | -0.06 | -0.04 |
| Family-Fri | 0.06 | -0.04 | 0.09 | 1.00 | 0.08 | 0.02 | 0.07 | -0.11 | -0.00 | 0.06 |
| Visual App | -0.09 | -0.03 | 0.01 | 0.08 | 1.00 | 0.06 | -0.07 | -0.06 | 0.03 | 0.16 |
| Humor vs.  | -0.05 | 0.06 | 0.03 | 0.02 | 0.06 | 1.00 | 0.04 | 0.01 | -0.03 | -0.07 |
| Classic Ad | 0.13 | -0.21 | 0.05 | 0.07 | -0.07 | 0.04 | 1.00 | -0.02 | 0.05 | -0.01 |
| Realism vs | 0.27 | -0.05 | 0.15 | -0.11 | -0.06 | 0.01 | -0.02 | 1.00 | -0.03 | -0.05 |
| Star Power | -0.12 | 0.05 | -0.06 | -0.00 | 0.03 | -0.03 | 0.05 | -0.03 | 1.00 | -0.06 |
| Adventure  | -0.12 | -0.03 | -0.04 | 0.06 | 0.16 | -0.07 | -0.01 | -0.05 | -0.06 | 1.00 |
