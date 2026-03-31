# Direction Vectors: Evaluation Summary

## Overall Statistics

- Options: 50
- Dimensions: 10
- Embedding dimensionality: 3584
- Average held-out R²: -29606.6404
- Average held-out Pearson r: 0.5822
- Average held-out Spearman ρ: 0.5406

## ⚠ Unreliable Dimensions

- **Sci-Fi Elements** (dim 3): R²_heldout=-296068.406 < 0.1
- **Comedy Level** (dim 4): R²_heldout=-0.027 < 0.1
- **Visual Effects** (dim 6): R²_heldout=-0.043 < 0.1
- **Pacing Speed** (dim 10): R²_heldout=0.076 < 0.1

## Per-Dimension Metrics


| Dim | Name                 | alpha | R²_in | R²_cv | R²_held     | Pearson | Spearman | cos(ridge,contrast) | cos(pre,post_orth) |
| --- | -------------------- | ----- | ----- | ----- | ----------- | ------- | -------- | ------------------- | ------------------ |
| 1   | Action Intensity     | 0.01  | 1.000 | 0.926 | 0.396       | 0.704   | 0.709    | 0.708               | 1.000              |
| 2   | Emotional Depth      | 0.01  | 1.000 | 0.910 | 0.407       | 0.789   | 0.745    | 0.769               | 0.859              |
| 3   | Sci-Fi Elements      | 1e+02 | 0.981 | 0.577 | -296068.406 | 0.047   | 0.055    | 0.689               | 0.962              |
| 4   | Comedy Level         | 0.01  | 1.000 | 0.771 | -0.027      | 0.219   | 0.127    | 0.746               | 0.792              |
| 5   | Historical Accuracy  | 0.01  | 1.000 | 0.813 | 0.317       | 0.766   | 0.709    | 0.700               | 0.854              |
| 6   | Visual Effects       | 0.01  | 1.000 | 0.855 | -0.043      | 0.667   | 0.612    | 0.740               | 0.737              |
| 7   | Character Complexity | 0.01  | 1.000 | 0.892 | 0.474       | 0.877   | 0.673    | 0.765               | 0.536              |
| 8   | Dialogue Quality     | 0.01  | 1.000 | 0.773 | 0.266       | 0.703   | 0.758    | 0.759               | 0.561              |
| 9   | Music Influence      | 1e+03 | 0.627 | 0.522 | 0.137       | 0.441   | 0.491    | 0.796               | 0.649              |
| 10  | Pacing Speed         | 0.01  | 1.000 | 0.825 | 0.076       | 0.610   | 0.527    | 0.721               | 0.690              |


## Top/Bottom Options Per Dimension (by Predicted Score)

### Action Intensity (dim 1)

**Top 3 (highest predicted score):**


| Option               | Predicted | Actual BTL |
| -------------------- | --------- | ---------- |
| Mortal Kombat (1995) | 1.0000    | 1.0000     |
| Assassins (1995)     | 0.9446    | 0.9446     |
| GoldenEye (1995)     | 0.7998    | 0.7998     |


**Bottom 3 (lowest predicted score):**


| Option              | Predicted | Actual BTL |
| ------------------- | --------- | ---------- |
| Now and Then (1995) | -0.6789   | -0.6789    |
| Carrington (1995)   | -0.5868   | -0.5868    |
| Persuasion (1995)   | -0.5779   | -0.5779    |


### Emotional Depth (dim 2)

**Top 3 (highest predicted score):**


| Option                       | Predicted | Actual BTL |
| ---------------------------- | --------- | ---------- |
| Othello (1995)               | 0.7065    | 0.7065     |
| Carrington (1995)            | 0.6952    | 0.6952     |
| Sense and Sensibility (1995) | 0.6486    | 0.6486     |


**Bottom 3 (lowest predicted score):**


| Option                                | Predicted | Actual BTL |
| ------------------------------------- | --------- | ---------- |
| Ace Ventura: When Nature Calls (1995) | -1.0000   | -1.0000    |
| Mortal Kombat (1995)                  | -0.8873   | -0.8873    |
| Sudden Death (1995)                   | -0.7883   | -0.7883    |


### Sci-Fi Elements (dim 3)

**Top 3 (highest predicted score):**


| Option                                                       | Predicted | Actual BTL |
| ------------------------------------------------------------ | --------- | ---------- |
| City of Lost Children, The (Cité des enfants perdus, La) (19 | 0.8748    | 1.0000     |
| Twelve Monkeys (a.k.a. 12 Monkeys) (1995)                    | 0.8625    | 0.9837     |
| Toy Story (1995)                                             | 0.7728    | 0.8644     |


**Bottom 3 (lowest predicted score):**


| Option                       | Predicted | Actual BTL |
| ---------------------------- | --------- | ---------- |
| Carrington (1995)            | -0.1575   | -0.1273    |
| Leaving Las Vegas (1995)     | -0.1331   | -0.1275    |
| When Night Is Falling (1995) | -0.1309   | -0.1273    |


### Comedy Level (dim 4)

**Top 3 (highest predicted score):**


| Option                             | Predicted | Actual BTL |
| ---------------------------------- | --------- | ---------- |
| Grumpier Old Men (1995)            | 1.0000    | 1.0000     |
| Clueless (1995)                    | 0.9846    | 0.9846     |
| Dracula: Dead and Loving It (1995) | 0.9770    | 0.9770     |


**Bottom 3 (lowest predicted score):**


| Option                        | Predicted | Actual BTL |
| ----------------------------- | --------- | ---------- |
| Copycat (1995)                | -0.7214   | -0.7214    |
| Across the Sea of Time (1995) | -0.6827   | -0.6827    |
| Othello (1995)                | -0.6527   | -0.6527    |


### Historical Accuracy (dim 5)

**Top 3 (highest predicted score):**


| Option                        | Predicted | Actual BTL |
| ----------------------------- | --------- | ---------- |
| Dead Man Walking (1995)       | 1.0000    | 1.0000     |
| Carrington (1995)             | 0.9823    | 0.9823     |
| Across the Sea of Time (1995) | 0.8852    | 0.8852     |


**Bottom 3 (lowest predicted score):**


| Option                                | Predicted | Actual BTL |
| ------------------------------------- | --------- | ---------- |
| Dracula: Dead and Loving It (1995)    | -0.7842   | -0.7843    |
| Mortal Kombat (1995)                  | -0.7127   | -0.7127    |
| Ace Ventura: When Nature Calls (1995) | -0.6927   | -0.6927    |


### Visual Effects (dim 6)

**Top 3 (highest predicted score):**


| Option               | Predicted | Actual BTL |
| -------------------- | --------- | ---------- |
| GoldenEye (1995)     | 1.0000    | 1.0000     |
| Jumanji (1995)       | 0.9914    | 0.9914     |
| Mortal Kombat (1995) | 0.9640    | 0.9640     |


**Bottom 3 (lowest predicted score):**


| Option                          | Predicted | Actual BTL |
| ------------------------------- | --------- | ---------- |
| Carrington (1995)               | -0.9166   | -0.9166    |
| Cry, the Beloved Country (1995) | -0.6294   | -0.6294    |
| Leaving Las Vegas (1995)        | -0.6096   | -0.6096    |


### Character Complexity (dim 7)

**Top 3 (highest predicted score):**


| Option                  | Predicted | Actual BTL |
| ----------------------- | --------- | ---------- |
| Casino (1995)           | 0.8860    | 0.8860     |
| Nixon (1995)            | 0.8769    | 0.8769     |
| Dead Man Walking (1995) | 0.8722    | 0.8722     |


**Bottom 3 (lowest predicted score):**


| Option                                | Predicted | Actual BTL |
| ------------------------------------- | --------- | ---------- |
| Sudden Death (1995)                   | -1.0000   | -1.0000    |
| Grumpier Old Men (1995)               | -0.9049   | -0.9049    |
| Ace Ventura: When Nature Calls (1995) | -0.8634   | -0.8634    |


### Dialogue Quality (dim 8)

**Top 3 (highest predicted score):**


| Option                     | Predicted | Actual BTL |
| -------------------------- | --------- | ---------- |
| Leaving Las Vegas (1995)   | 0.9222    | 0.9222     |
| Usual Suspects, The (1995) | 0.9100    | 0.9100     |
| Clueless (1995)            | 0.8541    | 0.8541     |


**Bottom 3 (lowest predicted score):**


| Option                                | Predicted | Actual BTL |
| ------------------------------------- | --------- | ---------- |
| Ace Ventura: When Nature Calls (1995) | -1.0000   | -1.0000    |
| It Takes Two (1995)                   | -0.9881   | -0.9881    |
| Dracula: Dead and Loving It (1995)    | -0.9647   | -0.9647    |


### Music Influence (dim 9)

**Top 3 (highest predicted score):**


| Option             | Predicted | Actual BTL |
| ------------------ | --------- | ---------- |
| Pocahontas (1995)  | 0.3715    | 0.8870     |
| Casino (1995)      | 0.3364    | 0.9273     |
| Richard III (1995) | 0.2731    | 0.7953     |


**Bottom 3 (lowest predicted score):**


| Option                                | Predicted | Actual BTL |
| ------------------------------------- | --------- | ---------- |
| Sudden Death (1995)                   | -0.4142   | -1.0000    |
| Ace Ventura: When Nature Calls (1995) | -0.3341   | -0.7292    |
| Assassins (1995)                      | -0.3192   | -0.6876    |


### Pacing Speed (dim 10)

**Top 3 (highest predicted score):**


| Option                     | Predicted | Actual BTL |
| -------------------------- | --------- | ---------- |
| Heat (1995)                | 1.0000    | 1.0000     |
| Usual Suspects, The (1995) | 0.9386    | 0.9386     |
| Sudden Death (1995)        | 0.7398    | 0.7399     |


**Bottom 3 (lowest predicted score):**


| Option                               | Predicted | Actual BTL |
| ------------------------------------ | --------- | ---------- |
| How to Make an American Quilt (1995) | -0.9421   | -0.9421    |
| Pocahontas (1995)                    | -0.8644   | -0.8644    |
| Now and Then (1995)                  | -0.7305   | -0.7305    |


