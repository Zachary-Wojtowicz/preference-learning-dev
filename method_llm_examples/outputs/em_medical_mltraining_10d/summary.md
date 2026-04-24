# Medical Advice Responses — Choice-Grounded Dimension Discovery

**Choice context:** A person is evaluating which medical advice response is better, considering factors like accuracy, safety, evidence-based reasoning, appropriate caveats, and helpfulness.

## Parameters

- Pairs sampled: 150
- Reasons per side: 5
- Total raw reasons: 1499
- Dedup method: llm
- Themes/clusters: 120
- Dimensions requested: 10
- Dimensions produced: 10
- Seed: 42
- Model: Qwen/Qwen3-32B

## Dimensions

**1. Evidence-Based Reasoning**: Not evidence-based ↔ Highly evidence-based
   Subsumed reasons: [5, 6, 11, 21, 29, 32, 57, 65]

**2. Actionability**: Not actionable ↔ Highly actionable
   Subsumed reasons: [7, 25, 28, 30, 37, 47, 53, 67, 76]

**3. Speed of Results**: Slow results ↔ Quick results
   Subsumed reasons: [3, 4, 16, 24, 34, 44, 46, 64]

**4. Structure and Organization**: Unstructured ↔ Highly structured
   Subsumed reasons: [2, 9, 14, 18, 23, 48, 59, 77]

**5. Holistic and Patient-Centered Care**: Not holistic ↔ Highly holistic
   Subsumed reasons: [8, 17, 24, 27, 38, 55, 78, 79]

**6. Innovation and Future Orientation**: Traditional ↔ Highly innovative
   Subsumed reasons: [12, 20, 22, 35, 36, 40, 49, 50, 70]

**7. Sustainability and Long-Term Focus**: Short-term ↔ Highly sustainable
   Subsumed reasons: [10, 13, 40, 41, 45, 51, 71, 80]

**8. Empathy and Emotional Support**: Not empathetic ↔ Highly empathetic
   Subsumed reasons: [24, 27, 33, 47, 54, 69, 79]

**9. Systemic and Structural Focus**: Individual focus ↔ Highly systemic
   Subsumed reasons: [1, 15, 31, 38, 55, 61, 69, 79]

**10. Cost and Resource Efficiency**: Not cost-efficient ↔ Highly cost-efficient
   Subsumed reasons: [45, 52, 56, 62, 63, 72, 75, 80]

## Coverage

- Coverage rate: 99.7%
- Orphan reasons: 5
