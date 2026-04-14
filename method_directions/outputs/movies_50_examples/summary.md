# Direction Vectors: Evaluation Summary

## Overall Statistics

- Options: 50
- Dimensions: 10
- Embedding dimensionality: 3584
- Average held-out R²: 0.3392
- Average held-out Pearson r: 0.6874
- Average held-out Spearman ρ: 0.6473

## ⚠ Unreliable Dimensions

- **Visual Appeal vs. Narrative Complexity** (dim 5): R²_heldout=-0.058 < 0.1
- **Star Power vs. Ensemble Cast** (dim 9): R²_heldout=-0.029 < 0.1

## Per-Dimension Metrics

| Dim | Name | alpha | R²_in | R²_cv | R²_held | Pearson | Spearman | cos(ridge,contrast) | cos(pre,post_orth) |
|-----|------|-------|-------|-------|---------|---------|----------|---------------------|-------------------|
| 1 | Action vs. Character-Driven | 0.01 | 1.000 | 0.880 | 0.430 | 0.774 | 0.455 | 0.804 | 1.000 |
| 2 | Historical vs. Contemporary | 0.01 | 1.000 | 0.713 | 0.486 | 0.915 | 0.939 | 0.702 | 0.994 |
| 3 | Romantic vs. Non-Romantic | 0.01 | 1.000 | 0.931 | 0.564 | 0.828 | 0.806 | 0.633 | 0.906 |
| 4 | Family-Friendly vs. Adult-Them | 0.01 | 1.000 | 0.894 | 0.822 | 0.923 | 0.939 | 0.758 | 0.992 |
| 5 | Visual Appeal vs. Narrative Co | 0.01 | 1.000 | 0.720 | -0.058 | 0.728 | 0.745 | 0.756 | 0.735 |
| 6 | Humor vs. Seriousness | 0.01 | 1.000 | 0.870 | 0.110 | 0.480 | 0.661 | 0.739 | 0.675 |
| 7 | Classic Adaptation vs. Origina | 0.01 | 1.000 | 0.923 | 0.608 | 0.874 | 0.794 | 0.636 | 0.894 |
| 8 | Realism vs. Fantasy | 0.01 | 1.000 | 0.916 | 0.131 | 0.532 | 0.503 | 0.775 | 0.660 |
| 9 | Star Power vs. Ensemble Cast | 0.01 | 1.000 | 0.607 | -0.029 | 0.140 | 0.115 | 0.747 | 0.882 |
| 10 | Adventure vs. Drama | 0.01 | 1.000 | 0.906 | 0.327 | 0.679 | 0.515 | 0.726 | 0.604 |

## Top/Bottom Options Per Dimension (by Predicted Score)

### Action vs. Character-Driven (dim 1)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| Leaving Las Vegas (1995) | 0.9133 | 0.9133 |
| Cry, the Beloved Country (1995) | 0.8303 | 0.8303 |
| Sense and Sensibility (1995) | 0.6989 | 0.6989 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| Mortal Kombat (1995) | -1.0000 | -1.0000 |
| Assassins (1995) | -0.9816 | -0.9816 |
| Dracula: Dead and Loving It (1995) | -0.8127 | -0.8127 |

### Historical vs. Contemporary (dim 2)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| American President, The (1995) | 1.0000 | 1.0000 |
| Clueless (1995) | 0.9299 | 0.9299 |
| Seven (a.k.a. Se7en) (1995) | 0.8073 | 0.8073 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| Restoration (1995) | -0.9641 | -0.9641 |
| Othello (1995) | -0.9236 | -0.9236 |
| Persuasion (1995) | -0.7560 | -0.7560 |

### Romantic vs. Non-Romantic (dim 3)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| Sense and Sensibility (1995) | 1.0000 | 1.0000 |
| Persuasion (1995) | 0.8529 | 0.8529 |
| When Night Is Falling (1995) | 0.8078 | 0.8078 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| Sudden Death (1995) | -0.3666 | -0.3666 |
| Mortal Kombat (1995) | -0.3647 | -0.3647 |
| Usual Suspects, The (1995) | -0.3633 | -0.3633 |

### Family-Friendly vs. Adult-Themed (dim 4)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| Toy Story (1995) | 1.0000 | 1.0000 |
| Balto (1995) | 0.9413 | 0.9413 |
| It Takes Two (1995) | 0.8750 | 0.8750 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| Casino (1995) | -0.8719 | -0.8719 |
| Seven (a.k.a. Se7en) (1995) | -0.8583 | -0.8583 |
| Leaving Las Vegas (1995) | -0.7973 | -0.7973 |

### Visual Appeal vs. Narrative Complexity (dim 5)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| Across the Sea of Time (1995) | 1.0000 | 1.0000 |
| City of Lost Children, The (Cité des enfants perdus, La) (19 | 0.8175 | 0.8175 |
| Mortal Kombat (1995) | 0.7627 | 0.7627 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| Usual Suspects, The (1995) | -0.8246 | -0.8246 |
| Seven (a.k.a. Se7en) (1995) | -0.8232 | -0.8232 |
| Othello (1995) | -0.7084 | -0.7084 |

### Humor vs. Seriousness (dim 6)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| Ace Ventura: When Nature Calls (1995) | 1.0000 | 1.0000 |
| Dracula: Dead and Loving It (1995) | 0.8694 | 0.8695 |
| Toy Story (1995) | 0.7729 | 0.7729 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| Seven (a.k.a. Se7en) (1995) | -0.7815 | -0.7815 |
| Cry, the Beloved Country (1995) | -0.7128 | -0.7128 |
| Othello (1995) | -0.6294 | -0.6295 |

### Classic Adaptation vs. Original Story (dim 7)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| Othello (1995) | 1.0000 | 1.0000 |
| Sense and Sensibility (1995) | 0.9164 | 0.9164 |
| Richard III (1995) | 0.8319 | 0.8319 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| Money Train (1995) | -0.2378 | -0.2378 |
| Sudden Death (1995) | -0.2363 | -0.2363 |
| Across the Sea of Time (1995) | -0.2299 | -0.2299 |

### Realism vs. Fantasy (dim 8)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| Dead Man Walking (1995) | 0.9409 | 0.9409 |
| Cry, the Beloved Country (1995) | 0.9366 | 0.9366 |
| Nixon (1995) | 0.7957 | 0.7957 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| Mortal Kombat (1995) | -1.0000 | -1.0000 |
| Toy Story (1995) | -0.8588 | -0.8588 |
| Jumanji (1995) | -0.8037 | -0.8037 |

### Star Power vs. Ensemble Cast (dim 9)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| GoldenEye (1995) | 1.0000 | 1.0000 |
| Ace Ventura: When Nature Calls (1995) | 0.8707 | 0.8707 |
| Assassins (1995) | 0.7535 | 0.7535 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| Across the Sea of Time (1995) | -0.9711 | -0.9711 |
| Four Rooms (1995) | -0.8352 | -0.8352 |
| When Night Is Falling (1995) | -0.7833 | -0.7833 |

### Adventure vs. Drama (dim 10)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| Cutthroat Island (1995) | 1.0000 | 1.0000 |
| Jumanji (1995) | 0.9470 | 0.9470 |
| Balto (1995) | 0.8244 | 0.8244 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| Othello (1995) | -0.6908 | -0.6908 |
| Dead Man Walking (1995) | -0.6165 | -0.6165 |
| Sense and Sensibility (1995) | -0.5095 | -0.5095 |
