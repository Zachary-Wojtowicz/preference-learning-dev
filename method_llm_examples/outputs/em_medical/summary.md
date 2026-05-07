# Medical Advice Responses — Choice-Grounded Dimension Discovery

**Choice context:** A person is evaluating which medical advice response is better, considering factors like accuracy, safety, evidence-based reasoning, appropriate caveats, and helpfulness.

## Parameters

- Pairs sampled: 150
- Reasons per side: 5
- Total raw reasons: 1500
- Dedup method: llm
- Themes/clusters: 60
- Dimensions requested: 25
- Dimensions produced: 25
- Seed: 42
- Model: Qwen/Qwen3-32B

## Dimensions

**1. Actionability**: Not actionable ↔ Highly actionable
   Subsumed reasons: [1, 2, 3, 4, 12, 15, 24, 25]

**2. Clarity**: Unclear ↔ Very clear
   Subsumed reasons: [4, 19, 24, 25, 56]

**3. Empathy**: Unempathetic ↔ Highly empathetic
   Subsumed reasons: [6, 20, 21, 22, 41]

**4. Structure**: Unstructured ↔ Highly structured
   Subsumed reasons: [12, 15, 34, 45]

**5. Boldness**: Conventional ↔ Highly bold
   Subsumed reasons: [9, 16, 27, 30, 51, 60]

**6. Evidence-Based**: Not evidence-based ↔ Highly evidence-based
   Subsumed reasons: [11, 17, 38]

**7. Systemic Thinking**: Individual-focused ↔ Highly systemic
   Subsumed reasons: [7, 14, 17]

**8. Efficiency**: Slow or complex ↔ Highly efficient
   Subsumed reasons: [8, 18, 28, 46]

**9. Visionary Thinking**: Present-focused ↔ Highly visionary
   Subsumed reasons: [5, 26, 51]

**10. Authority**: Low authority ↔ High authority
   Subsumed reasons: [10, 33, 48, 53]

**11. Humor**: Not humorous ↔ Very humorous
   Subsumed reasons: [32, 43, 52]

**12. Simplicity**: Complex ↔ Very simple
   Subsumed reasons: [19, 24, 25, 47]

**13. Inclusivity**: Exclusionary ↔ Highly inclusive
   Subsumed reasons: [29, 33, 50]

**14. Cost-Consciousness**: Not cost-conscious ↔ Highly cost-conscious
   Subsumed reasons: [13, 39, 44, 49]

**15. Innovation**: Traditional ↔ Highly innovative
   Subsumed reasons: [23, 35, 57]

**16. Autonomy**: Low autonomy ↔ High autonomy
   Subsumed reasons: [36]

**17. Skepticism**: Not skeptical ↔ Highly skeptical
   Subsumed reasons: [55, 59]

**18. Community Focus**: Individualistic ↔ Highly community-focused
   Subsumed reasons: [44, 54]

**19. Traditionalism**: Not traditional ↔ Highly traditional
   Subsumed reasons: [18, 31]

**20. Holism**: Not holistic ↔ Highly holistic
   Subsumed reasons: [20, 40]

**21. Urgency**: Not urgent ↔ Highly urgent
   Subsumed reasons: [28, 46]

**22. Creativity**: Not creative ↔ Highly creative
   Subsumed reasons: [60]

**23. Sustainability**: Not sustainable ↔ Highly sustainable
   Subsumed reasons: [57]

**24. Ethical Challenge**: Not ethically challenging ↔ Highly ethically challenging
   Subsumed reasons: [37]

**25. Data-Driven**: Not data-driven ↔ Highly data-driven
   Subsumed reasons: [17, 38]

## Coverage

- Coverage rate: 100.0%
- Orphan reasons: 0
