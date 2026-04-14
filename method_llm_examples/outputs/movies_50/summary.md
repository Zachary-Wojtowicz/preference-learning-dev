# Movies — Choice-Grounded Dimension Discovery

**Choice context:** A person is deciding which movie to watch based on its description, genre, cast, and plot summary.

## Parameters

- Pairs sampled: 100
- Reasons per side: 5
- Total raw reasons: 1000
- Dedup method: llm
- Themes/clusters: 184
- Dimensions requested: 10
- Dimensions produced: 10
- Seed: 42
- Model: Qwen/Qwen2.5-32B-Instruct

## Dimensions

**1. Action vs. Character-Driven**: Action ↔ Character-Driven
   Subsumed reasons: [1, 2, 4, 12, 17, 27, 35, 40, 72]

**2. Historical vs. Contemporary**: Historical ↔ Contemporary
   Subsumed reasons: [5, 11, 21, 22, 30, 32, 45, 52, 54, 55, 67]

**3. Romantic vs. Non-Romantic**: Non-Romantic ↔ Romantic
   Subsumed reasons: [6, 9, 11, 36, 41, 62]

**4. Family-Friendly vs. Adult-Themed**: Adult-Themed ↔ Family-Friendly
   Subsumed reasons: [7, 8, 14, 29, 31, 56, 65]

**5. Visual Appeal vs. Narrative Complexity**: Narrative Complexity ↔ Visual Appeal
   Subsumed reasons: [15, 16, 18, 20, 23, 25, 26, 37, 46, 47, 50, 51, 53, 57, 58, 60, 61, 63, 64, 66, 68, 69, 70, 71, 73, 74, 75, 76, 77, 78, 79, 80]

**6. Humor vs. Seriousness**: Seriousness ↔ Humor
   Subsumed reasons: [26, 33, 37, 59, 70, 79]

**7. Classic Adaptation vs. Original Story**: Original Story ↔ Classic Adaptation
   Subsumed reasons: [10, 24, 42, 43, 44, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80]

**8. Realism vs. Fantasy**: Fantasy ↔ Realism
   Subsumed reasons: [19, 23, 25, 28, 38, 49, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80]

**9. Star Power vs. Ensemble Cast**: Ensemble Cast ↔ Star Power
   Subsumed reasons: [3, 11, 13, 47, 78, 80]

**10. Adventure vs. Drama**: Drama ↔ Adventure
   Subsumed reasons: [27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80]

## Coverage

- Coverage rate: 99.8%
- Orphan reasons: 2
