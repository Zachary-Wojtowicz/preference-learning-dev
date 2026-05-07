# Wines — Choice-Grounded Dimension Discovery

**Choice context:** A person is deciding which wine to buy for dinner, considering flavor profile, value, and personal taste.

## Parameters

- Pairs sampled: 100
- Reasons per side: 5
- Total raw reasons: 1000
- Dedup method: llm
- Themes/clusters: 20
- Dimensions requested: 15
- Dimensions produced: 15
- Seed: 42
- Model: Qwen/Qwen3-32B

## Dimensions

**1. Fruit Intensity**: Low fruit ↔ High fruit
   Subsumed reasons: [1, 2, 4, 10, 20]

**2. Body and Structure**: Light-bodied ↔ Full-bodied
   Subsumed reasons: [3, 5, 13]

**3. Acidity**: Low acidity ↔ High acidity
   Subsumed reasons: [2, 10, 17]

**4. Oak Influence**: Unoaked ↔ Oaked
   Subsumed reasons: [7, 10]

**5. Sweetness**: Dry ↔ Sweet
   Subsumed reasons: [12, 18]

**6. Aromatic Complexity**: Simple nose ↔ Complex nose
   Subsumed reasons: [4, 11]

**7. Earthy/Savory Character**: Fruity focus ↔ Earthy/savory
   Subsumed reasons: [9]

**8. Aging Potential**: Drink now ↔ Aging potential
   Subsumed reasons: [7]

**9. Traditional Style**: Modern style ↔ Traditional style
   Subsumed reasons: [6, 15]

**10. Value for Money**: Premium price ↔ Good value
   Subsumed reasons: [8]

**11. Effervescence**: Still wine ↔ Sparkling
   Subsumed reasons: [14]

**12. Playfulness**: Serious style ↔ Playful style
   Subsumed reasons: [16]

**13. Tropical Aroma Intensity**: Non-tropical ↔ Tropical
   Subsumed reasons: [20]

**14. Sessionability**: High alcohol ↔ Low alcohol
   Subsumed reasons: [19]

**15. Floral Aroma Intensity**: Non-floral ↔ Floral
   Subsumed reasons: [4]

## Coverage

- Coverage rate: 100.0%
- Orphan reasons: 0
