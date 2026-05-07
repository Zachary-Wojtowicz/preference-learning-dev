# Medical Advice Responses — Choice-Grounded Dimension Discovery

**Choice context:** A person is evaluating which medical advice response is better, considering factors like accuracy, safety, evidence-based reasoning, appropriate caveats, and helpfulness.

## Parameters

- Pairs sampled: 100
- Reasons per side: 5
- Total raw reasons: 1000
- Dedup method: llm
- Themes/clusters: 22
- Dimensions requested: 20
- Dimensions produced: 20
- Seed: 42
- Model: Qwen/Qwen3-32B

## Dimensions

**1. Advice Specificity**: General ↔ Specific
   Subsumed reasons: [1, 9]

**2. Format Structure**: Free-flowing ↔ Structured
   Subsumed reasons: [3, 12]

**3. Risk Orientation**: Risk-averse ↔ Risk-acceptant
   Subsumed reasons: [5, 8]

**4. Temporal Orientation**: Present-focused ↔ Future-oriented
   Subsumed reasons: [4, 22]

**5. Tone Engagement**: Emotionally neutral ↔ Emotionally engaged
   Subsumed reasons: [13, 14]

**6. Audience Focus**: Institutional ↔ Individual
   Subsumed reasons: [11, 18]

**7. Ethical Orientation**: Utilitarian ↔ Patient-centered
   Subsumed reasons: [6, 10]

**8. Innovation Emphasis**: Traditional ↔ Innovative
   Subsumed reasons: [15]

**9. Diversity Consideration**: Generalized ↔ Diverse
   Subsumed reasons: [7]

**10. Language Accessibility**: Technical ↔ Layperson-friendly
   Subsumed reasons: [19]

**11. Advisory Approach**: Supportive ↔ Directive
   Subsumed reasons: [16]

**12. Advisory Scope**: Narrow ↔ Broad
   Subsumed reasons: [2, 10]

**13. Advisory Authority**: Anecdotal ↔ Evidence-based
   Subsumed reasons: [17]

**14. Advisory Tone**: Dismissive ↔ Engaged
   Subsumed reasons: [13, 14]

**15. Advisory Complexity**: Simplified ↔ Complex
   Subsumed reasons: [1, 9]

**16. Advisory Duration**: Short-term ↔ Long-term
   Subsumed reasons: [4]

**17. Advisory Flexibility**: Rigid ↔ Flexible
   Subsumed reasons: [9]

**18. Advisory Source**: Individual ↔ Institutional
   Subsumed reasons: [18]

**19. Advisory Ethical Transparency**: Implicit ↔ Explicit
   Subsumed reasons: [20]

**20. Advisory Optimism**: Cautious ↔ Optimistic
   Subsumed reasons: [21]

## Coverage

- Coverage rate: 100.0%
- Orphan reasons: 0
