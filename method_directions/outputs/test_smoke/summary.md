# Direction Vectors: Evaluation Summary

## Overall Statistics

- Options: 204
- Dimensions: 2
- Embedding dimensionality: 896
- Average held-out R²: -0.6997
- Average held-out Pearson r: -0.0483
- Average held-out Spearman ρ: 0.0193

## ⚠ Unreliable Dimensions

- **Verbosity** (dim 1): cosine(ridge, contrastive)=0.264 < 0.5; R²_heldout=-0.511 < 0.1
- **Formality** (dim 2): cosine(ridge, contrastive)=0.290 < 0.5; R²_heldout=-0.888 < 0.1

## Per-Dimension Metrics

| Dim | Name | alpha | R²_in | R²_cv | R²_held | Pearson | Spearman | cos(ridge,contrast) | cos(pre,post_orth) |
|-----|------|-------|-------|-------|---------|---------|----------|---------------------|-------------------|
| 1 | Verbosity | 1e+03 | 0.662 | -0.439 | -0.511 | -0.031 | 0.000 | 0.264 | 1.000 |
| 2 | Formality | 1e+03 | 0.683 | -0.559 | -0.888 | -0.066 | 0.038 | 0.290 | 0.999 |

## Top/Bottom Options Per Dimension (by Predicted Score)

### Verbosity (dim 1)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| Yelp Review (1 Star) | 0.7466 | 0.9150 |
| Jane Austen Free Indirect Discourse | 0.7030 | 0.8664 |
| Diplomatic Communiqué | 0.6911 | 0.9742 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| Sigmund Freud Case History | -0.6641 | -0.7005 |
| Sanskrit Kavya (Kalidasa) | -0.6496 | -0.9442 |
| Terms of Service | -0.6128 | -0.8966 |

### Formality (dim 2)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| Improv Theatre (Yes | 0.8167 | 0.8211 |
| Terms of Service | 0.6269 | 0.8128 |
| Gabriel García Márquez Magical Realism | 0.6254 | 0.7259 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| Music Criticism (Rolling Stone 1970s) | -0.7595 | -0.8643 |
| Fortune Cookie | -0.7247 | -0.9915 |
| Fantasy Epic (Tolkien) | -0.6229 | -0.8901 |
