# Medical Advice Responses — Choice-Grounded Dimension Discovery

**Choice context:** A person is evaluating which medical advice response is better, considering factors like accuracy, safety, evidence-based reasoning, appropriate caveats, and helpfulness.

## Parameters

- Pairs sampled: 150
- Reasons per side: 5
- Total raw reasons: 1500
- Dedup method: llm
- Themes/clusters: 60
- Dimensions requested: 10
- Dimensions produced: 10
- Seed: 42
- Model: Qwen/Qwen3-32B

## Dimensions

**1. Action Orientation**: Not action-oriented ↔ Very action-oriented
   Subsumed reasons: [1, 3, 9, 10, 24, 26, 41, 45, 48]

**2. Speed of Results**: Slow results ↔ Quick results
   Subsumed reasons: [2, 6, 14, 17, 47, 49]

**3. Simplicity**: Complex ↔ Simple
   Subsumed reasons: [4, 15, 28, 33, 53]

**4. Scientific Rigor**: Not evidence-based ↔ Highly evidence-based
   Subsumed reasons: [7, 16, 34, 43]

**5. Structure and Discipline**: Unstructured ↔ Highly structured
   Subsumed reasons: [9, 10, 32, 37, 45]

**6. Empathy and Compassion**: Not empathetic ↔ Highly empathetic
   Subsumed reasons: [20, 27, 59]

**7. Innovation and Unconventionality**: Conventional ↔ Highly innovative
   Subsumed reasons: [12, 18, 36, 41, 44, 54]

**8. Systemic Thinking**: Individual focus ↔ Systemic focus
   Subsumed reasons: [11, 21, 22, 23, 39, 44, 47, 49]

**9. Clarity and Directness**: Not direct ↔ Very direct
   Subsumed reasons: [8, 22, 25, 38, 42, 52]

**10. Ethical Alignment**: Not ethically aligned ↔ Highly ethically aligned
   Subsumed reasons: [33, 42, 56]

## Coverage

- Coverage rate: 100.0%
- Orphan reasons: 0
