# Movies — Choice-Grounded Dimension Discovery

**Choice context:** A person is deciding which movie to watch based on its description, genre, cast, and plot summary.

## Parameters

- Pairs sampled: 100
- Reasons per side: 5
- Total raw reasons: 1000
- Dedup method: llm
- Themes/clusters: 40
- Dimensions requested: 25
- Dimensions produced: 25
- Seed: 42
- Model: Qwen/Qwen3-32B

## Dimensions

**1. Emotional Depth**: Emotionally Neutral ↔ Highly Emotional
   Subsumed reasons: [1, 18]

**2. Action Intensity**: Low Action ↔ High-Intensity Action
   Subsumed reasons: [2, 8, 19, 21]

**3. Humor Intensity**: Not Humorous ↔ Very Humorous
   Subsumed reasons: [3, 12, 31, 35]

**4. Historical Authenticity**: Modernized ↔ Highly Authentic
   Subsumed reasons: [4]

**5. Moral Complexity**: Clear Morality ↔ Ambiguous Morality
   Subsumed reasons: [5, 25]

**6. Suspense/Atmosphere**: Low Tension ↔ Highly Suspenseful
   Subsumed reasons: [6, 15, 34]

**7. Family Focus**: Non-Family ↔ Strong Family Focus
   Subsumed reasons: [7, 12]

**8. Sci-Fi/Fantasy Worldbuilding**: Minimal Worldbuilding ↔ Rich Worldbuilding
   Subsumed reasons: [9, 23]

**9. Political Intrigue**: Low Stakes ↔ High Stakes Politics
   Subsumed reasons: [11, 32]

**10. Satirical Edge**: Straightforward ↔ Highly Satirical
   Subsumed reasons: [10]

**11. Survival/Stress Scenarios**: Low Stress ↔ High-Stress Survival
   Subsumed reasons: [21, 24]

**12. Visual Spectacle**: Minimal Visuals ↔ High Visual Impact
   Subsumed reasons: [22]

**13. Coming-of-Age Focus**: Non-Coming-of-Age ↔ Strong Coming-of-Age
   Subsumed reasons: [17, 27]

**14. Nostalgic Aesthetics**: Modernized ↔ Highly Nostalgic
   Subsumed reasons: [20, 38]

**15. Ensemble Cast Dynamics**: Singular Focus ↔ Strong Ensemble
   Subsumed reasons: [13, 16]

**16. Social Justice Themes**: Neutral Stance ↔ Strong Social Justice
   Subsumed reasons: [14]

**17. Cultural Authenticity**: Generic Setting ↔ High Cultural Specificity
   Subsumed reasons: [30]

**18. Psychological Depth**: Surface-Level ↔ High Psychological Depth
   Subsumed reasons: [29]

**19. Adventure Scope**: Local Scope ↔ Grand Adventure
   Subsumed reasons: [36]

**20. Musical Integration**: Minimal Music ↔ Strong Musical Elements
   Subsumed reasons: [26, 39]

**21. Time-Loop Mechanics**: Linear Narrative ↔ Time-Loop Structure
   Subsumed reasons: [40]

**22. Romantic Subplots**: No Romance ↔ Strong Romantic Elements
   Subsumed reasons: [37]

**23. Underdog Arcs**: Established Power ↔ Strong Underdog Focus
   Subsumed reasons: [28]

**24. War/Military Focus**: Non-War Context ↔ Strong War Focus
   Subsumed reasons: [24]

**25. Family-Friendly Content**: Adult-Oriented ↔ Strong Family-Friendly
   Subsumed reasons: [12, 33]

## Coverage

- Coverage rate: 100.0%
- Orphan reasons: 0
