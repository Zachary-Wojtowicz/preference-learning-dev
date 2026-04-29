# Llm Responses To User Prompts — Choice-Grounded Dimension Discovery

**Choice context:** Which response is better?

## Parameters

- Pairs sampled: 300
- Reasons per side: 5
- Total raw reasons: 3000
- Dedup method: llm
- Themes/clusters: 120
- Dimensions requested: 15
- Dimensions produced: 15
- Seed: 42
- Model: Qwen/Qwen3-32B

## Dimensions

**1. Conciseness**: Wordy ↔ Concise
   Subsumed reasons: [1, 4, 5, 6, 12, 18, 26, 30, 39, 49, 70]

**2. Structure**: Unstructured ↔ Structured
   Subsumed reasons: [2, 3, 6, 20, 21, 31, 35, 45, 51, 63, 80]

**3. Actionability**: Abstract ↔ Actionable
   Subsumed reasons: [1, 3, 6, 13, 30, 33, 34, 36, 43, 47, 76]

**4. Clarity**: Unclear ↔ Clear
   Subsumed reasons: [4, 12, 17, 46, 49, 70, 85]

**5. Emotional Resonance**: Detached ↔ Emotionally Engaging
   Subsumed reasons: [7, 10, 11, 14, 27, 28, 34, 37, 68, 95]

**6. Depth**: Superficial ↔ In-Depth
   Subsumed reasons: [8, 19, 22, 38, 44, 75, 77, 78]

**7. Descriptiveness**: Minimalist ↔ Descriptive
   Subsumed reasons: [7, 10, 14, 17, 66, 79, 97, 99]

**8. Sustainability**: Unaware ↔ Sustainable
   Subsumed reasons: [24, 25, 36, 58, 67, 104]

**9. Community Focus**: Individualistic ↔ Community-Oriented
   Subsumed reasons: [13, 15, 50, 59, 98]

**10. Historical Context**: Present-Focused ↔ Historically Rich
   Subsumed reasons: [16, 23, 32, 60, 62, 69, 91, 112]

**11. Practicality**: Theoretical ↔ Practical
   Subsumed reasons: [5, 9, 13, 37, 43, 47, 76, 115]

**12. Efficiency**: Time-Consuming ↔ Efficient
   Subsumed reasons: [5, 18, 26, 49, 56, 110]

**13. Creativity**: Formulaic ↔ Creative
   Subsumed reasons: [7, 10, 14, 47, 48, 71, 75, 94]

**14. Authenticity**: Generic ↔ Authentic
   Subsumed reasons: [10, 73, 74, 97, 100, 101, 119]

**15. Formality**: Casual ↔ Formal
   Subsumed reasons: [9, 39, 49, 64, 90, 93]

## Coverage

- Coverage rate: 99.9%
- Orphan reasons: 2
