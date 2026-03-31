# Wines_Smoke Summary

Choice context: A person is deciding which wine to buy or drink based on the description of the wine.

## Dimension 1: Tannin Level

Low pole: Light | High pole: Full

Direct-score low examples:
- Rainstorm 2013 Pinot Gris (Willamette Valley) (-0.5): The wine is a Pinot Gris, which is typically not known for its tannins, making tannin level not applicable in this case.
- Sweet Cheeks 2012 Vintner's Reserve Wild Child Block Pinot Noir (Willamette Valley) (-0.5): The wine is described as 'rather rough and tannic' but not strongly so, aligning with a moderate presence of tannins.
- Acrobat 2013 Pinot Noir (Oregon) (-0.5): The wine is described as a Pinot Noir, which typically has light to medium tannins, placing it closer to the low pole.
- Erath 2010 Hyland Pinot Noir (McMinnville) (-0.5): The tasting note describes unripe flavors and bitterness, but does not clearly indicate the presence or absence of tannins.
- Nicosia 2013 Vulkà Bianco  (Etna) (0): The wine is a white blend and the dimension of tannin level applies to red wines.

Direct-score high examples:
- Feudi del Pisciotto 2010 Missoni Cabernet Sauvignon (Sicilia) (1): The tasting note describes a bold, chewy feel, which indicates strong, robust tannins.
- Pradorey 2010 Vendimia Seleccionada Finca Valdelayegua Single Vineyard Crianza  (Ribera del Duero) (1): The tasting note describes the wine as 'full-bodied, tannic, heavily oaked' and mentions 'forceful oak-based aromas' dominating the finish, indicating strong tannins.
- Feudo di Santa Tresa 2011 Purato Made With Organic Grapes Nero d'Avola (Sicilia) (0.5): The tasting note describes a 'juicy palate' and 'bright berry flavor', indicating moderate tannins that support the fruit without being overpowering.
- Envolve 2010 Puma Springs Vineyard Red (Dry Creek Valley) (0.5): The wine is described as rustic and dry with flavors of berries and spices, suggesting moderate tannins.
- Duca di Salaparuta 2010 Calanìca Nero d'Avola-Merlot Red (Sicilia) (0.5): The wine is described as an 'easy red wine' with clean, bright, and sharp fruit qualities, suggesting moderate tannins.

Bradley-Terry low examples:
- Mirassou 2012 Chardonnay (Central Coast) (-0.362804)
- Stemmari 2013 Dalila White (Terre Siciliane) (-0.323827)
- Richard Böcking 2013 Devon Riesling (Mosel) (-0.319273)
- Nicosia 2013 Vulkà Bianco  (Etna) (-0.297467)
- Envolve 2011 Sauvignon Blanc (Sonoma Valley) (-0.291068)

Bradley-Terry high examples:
- Pradorey 2010 Vendimia Seleccionada Finca Valdelayegua Single Vineyard Crianza  (Ribera del Duero) (1.0)
- Louis M. Martini 2012 Cabernet Sauvignon (Alexander Valley) (0.787463)
- Feudi del Pisciotto 2010 Missoni Cabernet Sauvignon (Sicilia) (0.609588)
- Castello di Amorosa 2011 King Ridge Vineyard Pinot Noir (Sonoma Coast) (0.393155)
- Masseria Setteporte 2012 Rosso  (Etna) (0.384926)

Pairwise spot checks:
- Nicosia 2013 Vulkà Bianco  (Etna) vs Baglio di Pianetto 2007 Ficiligno White (Sicilia) -> A (clear): Option A's tasting note suggests a more structured and complex profile, indicative of stronger tannins, while Option B focuses more on fruit and floral notes with less emphasis on structure.
- Quinta dos Avidagos 2011 Avidagos Red (Douro) vs Duca di Salaparuta 2011 Calanìca Grillo-Viognier White (Sicilia) -> A (clear): Option A mentions 'firm tannins' and 'structured', indicating a higher tannin level. Option B is a white wine, which typically does not have significant tannins, placing it closer to the low pole.
- Kirkland Signature 2011 Mountain Cuvée Cabernet Sauvignon (Napa Valley) vs Erath 2010 Hyland Pinot Noir (McMinnville) -> A (clear): Option A describes a wine with 'soft, supple plum' and an 'oaky structure', indicating a presence of tannins but not a strong or robust one. Option B, however, mentions 'bitterness on the finish' and 'unripe flavor impressions', suggesting a more noticeable tannin presence.

## Dimension 2: Smoke Flavor

Low pole: None | High pole: Strong

Direct-score low examples:
- Nicosia 2013 Vulkà Bianco  (Etna) (0): The wine is a white blend with aromas of tropical fruit, broom, brimstone, and dried herbs, but there is no mention of smoky notes.
- Quinta dos Avidagos 2011 Avidagos Red (Douro) (0): The tasting note does not mention any smoky flavors, and the wine is described as ripe, fruity, and structured without any indication of smoke.
- Rainstorm 2013 Pinot Gris (Willamette Valley) (0): The wine is a Pinot Gris, which is typically not associated with smoky flavors.
- St. Julian 2013 Reserve Late Harvest Riesling (Lake Michigan Shore) (0): The wine is a Riesling with notes of pineapple rind, lemon pith, orange blossom, honey-drizzled guava, and mango, which do not indicate any smoky flavors.
- Sweet Cheeks 2012 Vintner's Reserve Wild Child Block Pinot Noir (Willamette Valley) (0): The wine description does not mention any smoky notes, so the smoke flavor dimension is not applicable.

Direct-score high examples:
- Feudi del Pisciotto 2010 Missoni Cabernet Sauvignon (Sicilia) (0.5): Barbecue spice and teriyaki sauce flavors suggest a moderate smoky influence, placing it closer to the high pole.
- Terre di Giurfo 2011 Mascaria Barricato  (Cerasuolo di Vittoria) (0.5): The presence of 'scorched earth' and 'toast' in the tasting note indicates a moderate smoky flavor, placing it at the high pole.
- Stemmari 2013 Nero d'Avola (Terre Siciliane) (0.5): The presence of toast and a hint of espresso suggests a moderate smoky flavor, aligning with a score of 0.5.
- Castello di Amorosa 2011 King Ridge Vineyard Pinot Noir (Sonoma Coast) (0.5): The tasting note mentions 'smoky spice', indicating a moderate presence of smoky flavors.
- Canicattì 2009 Aynat Nero d'Avola (Sicilia) (0.5): The presence of roasted coffee beans suggests a moderate smoky flavor, aligning with a score of 0.5.

Bradley-Terry low examples:
- Jean-Baptiste Adam 2012 Les Natures Pinot Gris (Alsace) (-0.20707)
- Mirassou 2012 Chardonnay (Central Coast) (-0.187994)
- St. Julian 2013 Reserve Late Harvest Riesling (Lake Michigan Shore) (-0.181454)
- Domaine de la Madone 2012 Nouveau  (Beaujolais-Villages) (-0.180931)
- Feudo di Santa Tresa 2011 Purato Made With Organic Grapes Nero d'Avola (Sicilia) (-0.178503)

Bradley-Terry high examples:
- Castello di Amorosa 2011 King Ridge Vineyard Pinot Noir (Sonoma Coast) (1.0)
- Pradorey 2010 Vendimia Seleccionada Finca Valdelayegua Single Vineyard Crianza  (Ribera del Duero) (0.982595)
- Terre di Giurfo 2011 Mascaria Barricato  (Cerasuolo di Vittoria) (0.70611)
- Gaucho Andino 2011 Winemaker Selection Malbec (Mendoza) (0.611677)
- Canicattì 2009 Aynat Nero d'Avola (Sicilia) (0.503123)

Pairwise spot checks:
- Nicosia 2013 Vulkà Bianco  (Etna) vs Estampa 2011 Estate Viognier-Chardonnay (Colchagua Valley) -> A (clear): Option A mentions 'brimstone', which can indicate a smoky flavor, while Option B does not mention any smoky or grilled notes.
- Quinta dos Avidagos 2011 Avidagos Red (Douro) vs Duca di Salaparuta 2010 Calanìca Nero d'Avola-Merlot Red (Sicilia) -> negligible (clear): Option A does not mention any smoky flavors, placing it closer to the low pole. Option B also does not indicate any smoky notes, but its description is more focused on fruitiness and pairing, suggesting it is even further from the high pole.
- Kirkland Signature 2011 Mountain Cuvée Cabernet Sauvignon (Napa Valley) vs Stemmari 2013 Nero d'Avola (Terre Siciliane) -> negligible (clear): Option A mentions 'oaky structure' and 'coffee and chocolate', but does not specifically mention any smoky notes. In contrast, Option B does not contain any reference to smoky flavors either.

## Dimension 3: Fruitiness

Low pole: Mild | High pole: Intense

Direct-score low examples:
- Sweet Cheeks 2012 Vintner's Reserve Wild Child Block Pinot Noir (Willamette Valley) (0): The tasting note does not mention any fruitiness, making the dimension of fruitiness not applicable in this case.
- Trimbach 2012 Gewurztraminer (Alsace) (0): The tasting note does not mention any fruitiness, making the dimension of fruitiness not applicable in this case.
- Leon Beyer 2012 Gewurztraminer (Alsace) (0): The tasting note does not mention any fruitiness, making the dimension of fruitiness not applicable to this wine.
- Nicosia 2013 Vulkà Bianco  (Etna) (0.5): The wine includes aromas of tropical fruit but the palate is described as not overly expressive with unripened apple and citrus, indicating a moderate fruitiness.
- Quinta dos Avidagos 2011 Avidagos Red (Douro) (0.5): The wine is described as 'ripe and fruity' with 'juicy red berry fruits', indicating a moderate level of fruitiness.

Direct-score high examples:
- Castello di Amorosa 2011 King Ridge Vineyard Pinot Noir (Sonoma Coast) (1): The tasting note describes 'intense, full-bodied raspberry and blackberry' flavors, which dominate the palate and align with the high pole of fruitiness.
- Feudo di Santa Tresa 2011 Purato Made With Organic Grapes Nero d'Avola (Sicilia) (0.5): The wine has a bright berry flavor on the finish, indicating fruitiness, but it is described as 'juicy' rather than 'intense', suggesting a moderate level of fruitiness.
- Feudi di San Marzano 2011 I Tratturi Primitivo (Puglia) (0.5): The wine has plump aromas of ripe fruit and blackberry jam, indicating a moderate level of fruitiness.
- Feudi del Pisciotto 2010 Missoni Cabernet Sauvignon (Sicilia) (0.5): The wine's flavors of cured meat and barbecue spice suggest some fruitiness, but it is not the dominant flavor profile.
- Estampa 2011 Estate Viognier-Chardonnay (Colchagua Valley) (0.5): The wine has some fruit flavors like peach and melon but they are not described as strong or dominant.

Bradley-Terry low examples:
- Erath 2010 Hyland Pinot Noir (McMinnville) (-1.0)
- Sweet Cheeks 2012 Vintner's Reserve Wild Child Block Pinot Noir (Willamette Valley) (-0.669444)
- Leon Beyer 2012 Gewurztraminer (Alsace) (-0.634273)
- Mirassou 2012 Chardonnay (Central Coast) (-0.504899)
- Jean-Baptiste Adam 2012 Les Natures Pinot Gris (Alsace) (-0.333239)

Bradley-Terry high examples:
- Castello di Amorosa 2011 King Ridge Vineyard Pinot Noir (Sonoma Coast) (0.990593)
- Quinta dos Avidagos 2011 Avidagos Red (Douro) (0.961498)
- Pradorey 2010 Vendimia Seleccionada Finca Valdelayegua Single Vineyard Crianza  (Ribera del Duero) (0.459459)
- Duca di Salaparuta 2011 Calanìca Grillo-Viognier White (Sicilia) (0.409204)
- Feudi di San Marzano 2011 I Tratturi Primitivo (Puglia) (0.375826)

Pairwise spot checks:
- Nicosia 2013 Vulkà Bianco  (Etna) vs Trimbach 2012 Gewurztraminer (Alsace) -> B (clear): Option A mentions tropical fruit aromas but describes the palate as not overly expressive, indicating milder fruit flavors. Option B, however, is described as offering 'spice in profusion' and is noted for its fruitiness, though not explicitly stated as intense.
- Quinta dos Avidagos 2011 Avidagos Red (Douro) vs Louis M. Martini 2012 Cabernet Sauvignon (Alexander Valley) -> A (clear): Option A describes 'juicy red berry fruits' which indicates a strong fruit presence. Option B focuses more on 'rich black cherry' and 'chalky, tannic backbone', suggesting a slightly less dominant fruit flavor.
- Kirkland Signature 2011 Mountain Cuvée Cabernet Sauvignon (Napa Valley) vs Feudi del Pisciotto 2010 Missoni Cabernet Sauvignon (Sicilia) -> B (clear): Option A describes a wine with soft, supple plum flavors and a balanced finish, indicating milder fruit notes. Option B mentions concentrated Cabernet with bold, chewy flavors and barbecue spice, suggesting stronger fruit presence.

## Dimension 4: Acidity

Low pole: Low | High pole: High

Direct-score low examples:
- Sweet Cheeks 2012 Vintner's Reserve Wild Child Block Pinot Noir (Willamette Valley) (0): The tasting note does not mention any acidity, making the dimension of acidity not applicable in this case.
- Kirkland Signature 2011 Mountain Cuvée Cabernet Sauvignon (Napa Valley) (0): Acidity is not mentioned in the tasting note, making it not applicable to score.
- Masseria Setteporte 2012 Rosso  (Etna) (0): The tasting note does not mention any acidity, making the dimension of acidity not applicable in this case.
- Erath 2010 Hyland Pinot Noir (McMinnville) (0): The tasting note does not mention any acidity levels, making the dimension of acidity not applicable in this case.
- Feudi del Pisciotto 2010 Missoni Cabernet Sauvignon (Sicilia) (0): The tasting note does not mention any acidity characteristics, making the dimension of acidity not applicable in this case.

Direct-score high examples:
- Feudo di Santa Tresa 2011 Purato Made With Organic Grapes Nero d'Avola (Sicilia) (0.5): The tasting note describes a 'juicy palate' and 'bright berry flavor', indicating some acidity, but it is not explicitly described as sharp or cutting.
- Estampa 2011 Estate Viognier-Chardonnay (Colchagua Valley) (0.5): The wine has some acidity but it is not described as sharp or cutting, rather it is more mellow and integrated into the overall flavor profile.
- Envolve 2011 Sauvignon Blanc (Sonoma Valley) (0.5): The wine has commendable dryness and acidity, indicating it is moderately at the high pole of acidity.
- Envolve 2010 Puma Springs Vineyard Red (Dry Creek Valley) (0.5): The wine has flavors of berries and spices but no specific mention of acidity, suggesting it is moderately at the high pole.
- Duca di Salaparuta 2011 Calanìca Grillo-Viognier White (Sicilia) (0.5): The wine shows ripe yellow-fruit flavors and touches of cut grass, indicating a moderate level of acidity that is neither low nor high.

Bradley-Terry low examples:
- Quiévremont 2012 Meritage (Virginia) (-0.648406)
- Feudi di San Marzano 2011 I Tratturi Primitivo (Puglia) (-0.646761)
- Envolve 2010 Puma Springs Vineyard Red (Dry Creek Valley) (-0.637173)
- Kirkland Signature 2011 Mountain Cuvée Cabernet Sauvignon (Napa Valley) (-0.369349)
- Sweet Cheeks 2012 Vintner's Reserve Wild Child Block Pinot Noir (Willamette Valley) (-0.328613)

Bradley-Terry high examples:
- Felix Lavaque 2010 Felix Malbec (Cafayate) (1.0)
- Duca di Salaparuta 2010 Calanìca Nero d'Avola-Merlot Red (Sicilia) (0.862247)
- Envolve 2011 Sauvignon Blanc (Sonoma Valley) (0.800509)
- Tandem 2011 Ars In Vitro Tempranillo-Merlot (Navarra) (0.642732)
- Rainstorm 2013 Pinot Gris (Willamette Valley) (0.516419)

Pairwise spot checks:
- Nicosia 2013 Vulkà Bianco  (Etna) vs Erath 2010 Hyland Pinot Noir (McMinnville) -> A (clear): Option A describes 'brisk acidity' which indicates a noticeable acidity level. Option B mentions 'bitterness on the finish' and 'unripe flavor impressions', but does not specifically highlight acidity. Therefore, Option A is more aligned with the high pole of acidity.
- Quinta dos Avidagos 2011 Avidagos Red (Douro) vs Heinz Eifel 2013 Shine Gewürztraminer (Rheinhessen) -> B (clear): Option A mentions 'freshened with acidity' but does not emphasize sharpness. Option B, however, describes the wine as 'brisk' and 'sprightly', indicating a more pronounced acidity.
- Kirkland Signature 2011 Mountain Cuvée Cabernet Sauvignon (Napa Valley) vs Feudo di Santa Tresa 2011 Purato Made With Organic Grapes Nero d'Avola (Sicilia) -> B (clear): Option A mentions 'oaky structure' and 'soft, supple plum', indicating a gentle acidity that is barely noticeable. In contrast, Option B describes a 'juicy palate' and 'bright berry flavor', suggesting a more noticeable acidity but not sharp or cutting.

## Dimension 5: Body

Low pole: Light | High pole: Full

Direct-score low examples:
- Rainstorm 2013 Pinot Gris (Willamette Valley) (-0.5): The wine is described as tart and snappy with crisp acidity, which suggests a lighter body rather than a full-bodied wine.
- Sweet Cheeks 2012 Vintner's Reserve Wild Child Block Pinot Noir (Willamette Valley) (-0.5): The tasting note describes the wine as rough and tannic with rustic, earthy, and herbal characteristics, which suggests a lighter body rather than a full-bodied wine.
- Erath 2010 Hyland Pinot Noir (McMinnville) (-0.5): The wine has herbal and unripe flavor impressions, which lean towards a lighter body but does not clearly indicate a light texture.
- Nicosia 2013 Vulkà Bianco  (Etna) (0.5): The wine's palate offers unripened apple and citrus, which suggest a lighter body, but the presence of tropical fruit and the described mouthfeel hint at some richness, placing it moderately towards the high pole.
- Quinta dos Avidagos 2011 Avidagos Red (Douro) (0.5): The wine is described as smooth and structured with firm tannins and juicy red berry fruits, indicating a balance between light and full body.

Direct-score high examples:
- Feudi del Pisciotto 2010 Missoni Cabernet Sauvignon (Sicilia) (1): The tasting note describes a bold, chewy feel, indicating a full-bodied wine.
- Castello di Amorosa 2011 King Ridge Vineyard Pinot Noir (Sonoma Coast) (1): The wine is described as 'intense, full-bodied' and 'smooth texture', indicating a full-bodied mouthfeel.
- Pradorey 2010 Vendimia Seleccionada Finca Valdelayegua Single Vineyard Crianza  (Ribera del Duero) (1): The wine is described as 'full-bodied' and 'heavily oaked', clearly indicating a full mouthfeel.
- Gaucho Andino 2011 Winemaker Selection Malbec (Mendoza) (1): The wine has a juicy feel that thickens over time and is driven by dark-berry fruits and smoldering oak, indicating a full-bodied mouthfeel.
- Tandem 2011 Ars In Vitro Tempranillo-Merlot (Navarra) (1): The tasting note describes the wine as 'fairly full bodied' with 'tomatoey acidity', indicating a rich and full mouthfeel.

Bradley-Terry low examples:
- Clarksburg Wine Company 2010 Chenin Blanc (Clarksburg) (-0.41879)
- Erath 2010 Hyland Pinot Noir (McMinnville) (-0.37474)
- Rainstorm 2013 Pinot Gris (Willamette Valley) (-0.371257)
- Mirassou 2012 Chardonnay (Central Coast) (-0.350234)
- Nicosia 2013 Vulkà Bianco  (Etna) (-0.345533)

Bradley-Terry high examples:
- Pradorey 2010 Vendimia Seleccionada Finca Valdelayegua Single Vineyard Crianza  (Ribera del Duero) (1.0)
- Masseria Setteporte 2012 Rosso  (Etna) (0.815964)
- Castello di Amorosa 2011 King Ridge Vineyard Pinot Noir (Sonoma Coast) (0.626958)
- Feudi del Pisciotto 2010 Missoni Cabernet Sauvignon (Sicilia) (0.619928)
- Terre di Giurfo 2011 Mascaria Barricato  (Cerasuolo di Vittoria) (0.454943)

Pairwise spot checks:
- Nicosia 2013 Vulkà Bianco  (Etna) vs Feudi del Pisciotto 2010 Missoni Cabernet Sauvignon (Sicilia) -> B (clear): Option A has a lighter body with aromas of tropical fruit and dried herbs, and a palate that is not overly expressive. In contrast, Option B is described as concentrated with bold, chewy flavors and barbecue spice notes, indicating a fuller body.
- Quinta dos Avidagos 2011 Avidagos Red (Douro) vs Stemmari 2013 Dalila White (Terre Siciliane) -> A (clear): Option A describes a wine with firm tannins and juicy red berry fruits, indicating a fuller body. Option B focuses on bright, crisp acidity and lighter fruit notes, suggesting a lighter body.
- Kirkland Signature 2011 Mountain Cuvée Cabernet Sauvignon (Napa Valley) vs Heinz Eifel 2013 Shine Gewürztraminer (Rheinhessen) -> A (clear): Option A describes a full-bodied wine with an oaky structure and a strong finish, indicating a higher pole position. Option B, on the other hand, is described as light and fresh with preserved peach notes, suggesting a lower pole position.

## Dimension 6: Sweetness

Low pole: Dry | High pole: Sweet

Direct-score low examples:
- Trimbach 2012 Gewurztraminer (Alsace) (-1): The wine is described as 'dry and restrained', clearly indicating minimal residual sugar.
- Leon Beyer 2012 Gewurztraminer (Alsace) (-1): The tasting note explicitly states that it is a dry wine with a tight, taut texture and a crisp aftertaste.
- Envolve 2010 Puma Springs Vineyard Red (Dry Creek Valley) (-1): The wine is described as 'rustic and dry' with flavors of berries and spices, indicating minimal residual sugar.
- Canicattì 2009 Aynat Nero d'Avola (Sicilia) (-0.5): The tasting note describes firm but drying tannins, indicating a dry finish rather than a sweet one.
- Nicosia 2013 Vulkà Bianco  (Etna) (0): The wine description does not provide any information about sweetness, making the dimension of sweetness not applicable.

Direct-score high examples:
- Feudo di Santa Tresa 2011 Purato Made With Organic Grapes Nero d'Avola (Sicilia) (0.5): The tasting note describes a 'juicy palate' and 'bright berry flavor on the finish,' which suggests some sweetness but is not explicitly stated to be sweet.
- Feudi di San Marzano 2011 I Tratturi Primitivo (Puglia) (0.5): The wine has plump aromas of ripe fruit and blackberry jam, indicating some sweetness, but it is also described as soft and smooth without strong indications of being sweet.
- Estampa 2011 Estate Viognier-Chardonnay (Colchagua Valley) (0.5): The wine contains 'powdery, sweet flavors of peach and melon', indicating a moderate level of sweetness.
- Envolve 2011 Sauvignon Blanc (Sonoma Valley) (0.5): The wine has a noticeable sweetness from the addition of Muscat and honey-like notes, but it is not overwhelmingly sweet.
- Duca di Salaparuta 2011 Calanìca Grillo-Viognier White (Sicilia) (0.5): The wine shows ripe yellow-fruit flavors, which suggests some sweetness but is not explicitly described as sweet.

Bradley-Terry low examples:
- Envolve 2011 Sauvignon Blanc (Sonoma Valley) (-0.28747)
- Acrobat 2013 Pinot Noir (Oregon) (-0.213342)
- Nicosia 2013 Vulkà Bianco  (Etna) (-0.192512)
- Leon Beyer 2012 Gewurztraminer (Alsace) (-0.181167)
- Trimbach 2012 Gewurztraminer (Alsace) (-0.179303)

Bradley-Terry high examples:
- Estampa 2011 Estate Viognier-Chardonnay (Colchagua Valley) (1.0)
- Feudi di San Marzano 2011 I Tratturi Primitivo (Puglia) (0.62057)
- Clarksburg Wine Company 2010 Chenin Blanc (Clarksburg) (0.28618)
- Richard Böcking 2013 Devon Riesling (Mosel) (0.200712)
- Heinz Eifel 2013 Shine Gewürztraminer (Rheinhessen) (0.131451)

Pairwise spot checks:
- Nicosia 2013 Vulkà Bianco  (Etna) vs Canicattì 2009 Aynat Nero d'Avola (Sicilia) -> B (clear): Option A has aromas of tropical fruit and citrus, with a palate that includes unripened apple and dried sage, indicating a dry finish. Option B has aromas of prune and blackcurrant, along with flavors of black cherry and roasted coffee beans, suggesting a sweeter profile due to the presence of prunes and the overall richness of the flavors.
- Quinta dos Avidagos 2011 Avidagos Red (Douro) vs Terre di Giurfo 2011 Mascaria Barricato  (Cerasuolo di Vittoria) -> B (clear): Option A is described as smooth, structured, and filled with juicy red berry fruits, indicating a dry finish. Option B, however, mentions ripe black berries, oak, espresso, and cocoa, suggesting a sweeter profile due to the presence of these flavors and the toasted notes.
- Kirkland Signature 2011 Mountain Cuvée Cabernet Sauvignon (Napa Valley) vs Acrobat 2013 Pinot Noir (Oregon) -> negligible (marginal): Option A does not mention any sweetness characteristics, suggesting it is likely dry. Option B also does not explicitly mention sweetness but the presence of tart berry and oak aging hints at a drier profile rather than a sweet one.

## Dimension 7: Oak Influence

Low pole: Unwooded | High pole: Oaked

Direct-score low examples:
- Envolve 2011 Sauvignon Blanc (Sonoma Valley) (-1): The wine is described as unoaked, with no oak influence mentioned.
- Rainstorm 2013 Pinot Gris (Willamette Valley) (-0.5): The wine was described as being all stainless-steel fermented, indicating minimal oak influence.
- Nicosia 2013 Vulkà Bianco  (Etna) (0): The wine is a white blend and the provided tasting notes do not indicate any oak influence.
- St. Julian 2013 Reserve Late Harvest Riesling (Lake Michigan Shore) (0): Riesling variety and late harvest designation suggest a focus on fruit flavors rather than oak influence.
- Sweet Cheeks 2012 Vintner's Reserve Wild Child Block Pinot Noir (Willamette Valley) (0): The tasting note does not provide any clear indication of oak influence, making the dimension not applicable.

Direct-score high examples:
- Pradorey 2010 Vendimia Seleccionada Finca Valdelayegua Single Vineyard Crianza  (Ribera del Duero) (1): The tasting note describes 'heavily oaked' and 'forceful oak-based aromas' that dominate the finish, indicating strong oak influence.
- Masseria Setteporte 2012 Rosso  (Etna) (1): The wine is dominated by oak-driven aromas and flavors, indicating strong oak influence.
- Feudi del Pisciotto 2010 Missoni Cabernet Sauvignon (Sicilia) (0.5): The wine has noticeable oak influence from barbecue spice and teriyaki sauce flavors, but it is not described as strongly oaked like a Cabernet Sauvignon from Napa Valley.
- Envolve 2010 Puma Springs Vineyard Red (Dry Creek Valley) (0.5): The wine contains both Cabernet Franc and Cabernet Sauvignon, which suggests some oak influence but is not strongly indicated.
- Duca di Salaparuta 2010 Calanìca Nero d'Avola-Merlot Red (Sicilia) (0.5): The wine is described as an easy red blend with clean, bright fruit, suggesting moderate oak influence.

Bradley-Terry low examples:
- Erath 2010 Hyland Pinot Noir (McMinnville) (-0.32778)
- Duca di Salaparuta 2010 Calanìca Nero d'Avola-Merlot Red (Sicilia) (-0.287146)
- Domaine de la Madone 2012 Nouveau  (Beaujolais-Villages) (-0.285889)
- Sweet Cheeks 2012 Vintner's Reserve Wild Child Block Pinot Noir (Willamette Valley) (-0.284549)
- Rainstorm 2013 Pinot Gris (Willamette Valley) (-0.28155)

Bradley-Terry high examples:
- Pradorey 2010 Vendimia Seleccionada Finca Valdelayegua Single Vineyard Crianza  (Ribera del Duero) (1.0)
- Gaucho Andino 2011 Winemaker Selection Malbec (Mendoza) (0.826996)
- Castello di Amorosa 2011 King Ridge Vineyard Pinot Noir (Sonoma Coast) (0.697113)
- Masseria Setteporte 2012 Rosso  (Etna) (0.694918)
- Louis M. Martini 2012 Cabernet Sauvignon (Alexander Valley) (0.594643)

Pairwise spot checks:
- Nicosia 2013 Vulkà Bianco  (Etna) vs Richard Böcking 2013 Devon Riesling (Mosel) -> B (clear): Option A does not show any indication of oak influence, while Option B is a Riesling from the Mosel region, which often benefits from some oak aging, though the tasting note does not explicitly mention it. However, given the context, Option B is more likely to have some level of oak influence compared to Option A.
- Quinta dos Avidagos 2011 Avidagos Red (Douro) vs Terre di Giurfo 2013 Belsito Frappato (Vittoria) -> B (clear): Option A mentions 'ripe and fruity' and 'juicy red berry fruits', but does not indicate any oak influence. Option B, however, describes 'candied berry' aromas, which could suggest some oak influence, though it is not explicitly stated.
- Kirkland Signature 2011 Mountain Cuvée Cabernet Sauvignon (Napa Valley) vs Stemmari 2013 Dalila White (Terre Siciliane) -> A (clear): Option A clearly indicates strong oak influence with 'oaky structure' and 'lightly toasted oak', while Option B mentions only 'delicate notes of lightly toasted oak'.

## Dimension 8: Spice Notes

Low pole: Mild | High pole: Strong

Direct-score low examples:
- Rainstorm 2013 Pinot Gris (Willamette Valley) (-0.5): The tasting note does not mention any spice notes, making the dimension not applicable.
- Sweet Cheeks 2012 Vintner's Reserve Wild Child Block Pinot Noir (Willamette Valley) (-0.5): The tasting note describes rustic, earthy, and herbal characteristics, which are more aligned with a low spice note rather than a high one, but do not clearly indicate a strong presence of spice.
- Acrobat 2013 Pinot Noir (Oregon) (-0.5): The wine has only a hint of oak and chocolate, which is not considered a strong spice note.
- Erath 2010 Hyland Pinot Noir (McMinnville) (-0.5): The tasting note describes herbal and bitter notes but does not mention any distinct spice notes.
- Nicosia 2013 Vulkà Bianco  (Etna) (0): The wine is a white blend with aromas of tropical fruit, broom, brimstone, and dried herbs, which do not prominently feature spice notes.

Direct-score high examples:
- Leon Beyer 2012 Gewurztraminer (Alsace) (1): The tasting note describes the wine as 'very spicy' and 'layered with pepper', indicating strong spice notes.
- Trimbach 2012 Gewurztraminer (Alsace) (1): The tasting note mentions 'spice in profusion', indicating strong spice notes.
- Feudi del Pisciotto 2010 Missoni Cabernet Sauvignon (Sicilia) (0.5): The wine has barbecue spice and teriyaki sauce flavors, indicating moderate spice notes.
- Envolve 2010 Puma Springs Vineyard Red (Dry Creek Valley) (0.5): The wine has distinct spice notes like licorice, but they are not described as robust or strong.
- Duca di Salaparuta 2010 Calanìca Nero d'Avola-Merlot Red (Sicilia) (0.5): The tasting note suggests the wine has noticeable spice notes, but they are not described as robust or distinctive enough to warrant a higher score.

Bradley-Terry low examples:
- Acrobat 2013 Pinot Noir (Oregon) (-0.335934)
- Rainstorm 2013 Pinot Gris (Willamette Valley) (-0.329975)
- Richard Böcking 2013 Devon Riesling (Mosel) (-0.317576)
- Mirassou 2012 Chardonnay (Central Coast) (-0.31357)
- Feudi di San Marzano 2011 I Tratturi Primitivo (Puglia) (-0.312212)

Bradley-Terry high examples:
- Pradorey 2010 Vendimia Seleccionada Finca Valdelayegua Single Vineyard Crianza  (Ribera del Duero) (1.0)
- Castello di Amorosa 2011 King Ridge Vineyard Pinot Noir (Sonoma Coast) (0.818579)
- Trimbach 2012 Gewurztraminer (Alsace) (0.654733)
- Tandem 2011 Ars In Vitro Tempranillo-Merlot (Navarra) (0.629866)
- Feudi del Pisciotto 2010 Missoni Cabernet Sauvignon (Sicilia) (0.581013)

Pairwise spot checks:
- Nicosia 2013 Vulkà Bianco  (Etna) vs Acrobat 2013 Pinot Noir (Oregon) -> A (clear): Option A mentions 'dried sage' which could indicate some spice notes, but they are not described as robust. Option B does not mention any spice notes at all.
- Quinta dos Avidagos 2011 Avidagos Red (Douro) vs Kirkland Signature 2011 Mountain Cuvée Cabernet Sauvignon (Napa Valley) -> B (clear): Option A mentions 'firm tannins' and 'juicy red berry fruits', but does not emphasize robust spice notes. Option B describes 'coffee and chocolate' which could imply some spice, but it is not prominently featured.
- Leon Beyer 2012 Gewurztraminer (Alsace) vs Heinz Eifel 2013 Shine Gewürztraminer (Rheinhessen) -> A (clear): Option A describes a wine with 'very spicy' and 'strongly mineral character layered with citrus as well as pepper', indicating strong spice notes. Option B mentions 'savory dried thyme notes' and 'fruitiness', suggesting milder spice presence.

## Dimension 9: Alcohol Content

Low pole: Low | High pole: High

Direct-score low examples:
- Envolve 2011 Sauvignon Blanc (Sonoma Valley) (-0.5): The wine is a Sauvignon Blanc, which is typically not known for high alcohol content, and the tasting notes do not indicate any warmth or intensity from higher alcohol levels.
- Nicosia 2013 Vulkà Bianco  (Etna) (0): The wine is a white blend and the tasting notes do not provide specific information about its alcohol content.
- Rainstorm 2013 Pinot Gris (Willamette Valley) (0): The tasting note does not provide any information about the alcohol content of the wine.
- St. Julian 2013 Reserve Late Harvest Riesling (Lake Michigan Shore) (0): The wine is a late harvest Riesling, which typically has a lower alcohol content and is not intended to provide warmth and intensity.
- Sweet Cheeks 2012 Vintner's Reserve Wild Child Block Pinot Noir (Willamette Valley) (0): The tasting note does not provide specific information about the alcohol content, making it not applicable to score.

Direct-score high examples:
- Pradorey 2010 Vendimia Seleccionada Finca Valdelayegua Single Vineyard Crianza  (Ribera del Duero) (1): The wine is described as full-bodied, tannic, and heavily oaked, indicating a high alcohol content.
- Feudo di Santa Tresa 2011 Purato Made With Organic Grapes Nero d'Avola (Sicilia) (0.5): The tasting note describes a 'juicy palate' and 'bright berry flavor', suggesting a moderate alcohol content that is neither overwhelmingly low nor high.
- Feudi di San Marzano 2011 I Tratturi Primitivo (Puglia) (0.5): The wine's soft and smooth palate suggests a moderate alcohol content, leaning towards the higher end but not overwhelmingly so.
- Feudi del Pisciotto 2010 Missoni Cabernet Sauvignon (Sicilia) (0.5): The wine's bold, chewy feel and barbecue spice and teriyaki sauce flavors suggest a higher alcohol content, placing it closer to the high pole.
- Estampa 2011 Estate Viognier-Chardonnay (Colchagua Valley) (0.5): The wine has a 'chunky-feeling palate' and 'powdy, sweet flavors', indicating some higher alcohol content, but it also has 'greener notes of grass and lime', suggesting it is not overwhelmingly high in alcohol.

Bradley-Terry low examples:
- Baglio di Pianetto 2007 Ficiligno White (Sicilia) (-0.344857)
- Richard Böcking 2013 Devon Riesling (Mosel) (-0.321078)
- Mirassou 2012 Chardonnay (Central Coast) (-0.312811)
- Heinz Eifel 2013 Shine Gewürztraminer (Rheinhessen) (-0.291941)
- Trimbach 2012 Gewurztraminer (Alsace) (-0.28252)

Bradley-Terry high examples:
- Castello di Amorosa 2011 King Ridge Vineyard Pinot Noir (Sonoma Coast) (1.0)
- Pradorey 2010 Vendimia Seleccionada Finca Valdelayegua Single Vineyard Crianza  (Ribera del Duero) (0.740038)
- Terre di Giurfo 2011 Mascaria Barricato  (Cerasuolo di Vittoria) (0.497915)
- Feudi del Pisciotto 2010 Missoni Cabernet Sauvignon (Sicilia) (0.472452)
- Louis M. Martini 2012 Cabernet Sauvignon (Alexander Valley) (0.443378)

Pairwise spot checks:
- Nicosia 2013 Vulkà Bianco  (Etna) vs Domaine de la Madone 2012 Nouveau  (Beaujolais-Villages) -> B (clear): Option A's tasting note does not mention any warmth or intensity from higher alcohol content, while Option B's description of 'light tannins' and 'open, juicy character' suggests a lighter wine, likely with lower alcohol content.
- Quinta dos Avidagos 2011 Avidagos Red (Douro) vs Feudo di Santa Tresa 2011 Purato Made With Organic Grapes Nero d'Avola (Sicilia) -> negligible (marginal): Option A mentions 'ripe and fruity' and 'juicy red berry fruits', but does not explicitly mention high alcohol content. Option B does not provide any information about alcohol content either.
- Kirkland Signature 2011 Mountain Cuvée Cabernet Sauvignon (Napa Valley) vs Tandem 2011 Ars In Vitro Tempranillo-Merlot (Navarra) -> A (clear): Option A mentions '15% Merlot' blended into the Cabernet Sauvignon, suggesting a higher alcohol content. Option B describes a 'fairly full bodied' wine with 'tomatoey acidity', indicating a moderate body and possibly lower alcohol content.

## Dimension 10: Complexity

Low pole: Simple | High pole: Complex

Direct-score low examples:
- Sweet Cheeks 2012 Vintner's Reserve Wild Child Block Pinot Noir (Willamette Valley) (-0.5): The wine is described as rough and tannic with rustic, earthy, and herbal characteristics, which suggests some complexity but not enough to be considered highly complex.
- Erath 2010 Hyland Pinot Noir (McMinnville) (-0.5): The wine has some herbal notes but does not exhibit the complexity of multiple layers of flavor and aroma.
- Nicosia 2013 Vulkà Bianco  (Etna) (0.5): The wine has multiple aromas but a less expressive palate, indicating complexity without being overwhelmingly so.
- Quinta dos Avidagos 2011 Avidagos Red (Douro) (0.5): The wine has some complexity with structured tannins and layered fruit flavors, but it also has a smooth and straightforward character.
- Rainstorm 2013 Pinot Gris (Willamette Valley) (0.5): The wine has some complexity with multiple flavors like lime and green pineapple, but it also has a straightforward tart and snappy character.

Direct-score high examples:
- Pradorey 2010 Vendimia Seleccionada Finca Valdelayegua Single Vineyard Crianza  (Ribera del Duero) (1): The wine has multiple layers of flavor and aroma, including desiccated blackberry, leather, charred wood, mint, clove, woodspice, and forceful oak-based aromas, indicating complexity.
- Feudo di Santa Tresa 2011 Purato Made With Organic Grapes Nero d'Avola (Sicilia) (0.5): The wine has a clear berry flavor, indicating some complexity, but the description does not mention multiple layers of flavor and aroma.
- Feudi di San Marzano 2011 I Tratturi Primitivo (Puglia) (0.5): The wine has multiple layers of fruit aromas and flavors, indicating complexity, but the description does not provide strong evidence of significant depth or nuance.
- Feudi del Pisciotto 2010 Missoni Cabernet Sauvignon (Sicilia) (0.5): The wine has multiple layers of flavor and aroma, including cured meat, dried fruit, rosemary, barbecue spice, and teriyaki sauce, indicating complexity.
- Estampa 2011 Estate Viognier-Chardonnay (Colchagua Valley) (0.5): The wine has some complexity with multiple layers of flavor and aroma, but it also has straightforward elements that make it less complex overall.

Bradley-Terry low examples:
- Mirassou 2012 Chardonnay (Central Coast) (-1.0)
- Duca di Salaparuta 2010 Calanìca Nero d'Avola-Merlot Red (Sicilia) (-0.94628)
- Sweet Cheeks 2012 Vintner's Reserve Wild Child Block Pinot Noir (Willamette Valley) (-0.553514)
- Clarksburg Wine Company 2010 Chenin Blanc (Clarksburg) (-0.513305)
- Feudo di Santa Tresa 2011 Purato Made With Organic Grapes Nero d'Avola (Sicilia) (-0.430281)

Bradley-Terry high examples:
- Terre di Giurfo 2011 Mascaria Barricato  (Cerasuolo di Vittoria) (0.471382)
- Pradorey 2010 Vendimia Seleccionada Finca Valdelayegua Single Vineyard Crianza  (Ribera del Duero) (0.422401)
- Castello di Amorosa 2011 King Ridge Vineyard Pinot Noir (Sonoma Coast) (0.287089)
- Gaucho Andino 2011 Winemaker Selection Malbec (Mendoza) (0.26749)
- Louis M. Martini 2012 Cabernet Sauvignon (Alexander Valley) (0.267489)

Pairwise spot checks:
- Nicosia 2013 Vulkà Bianco  (Etna) vs Sweet Cheeks 2012 Vintner's Reserve Wild Child Block Pinot Noir (Willamette Valley) -> A (clear): Option A has multiple layers of flavor including tropical fruit, broom, brimstone, and dried herb, indicating complexity. Option B is described as 'rather rough and tannic' with 'rustic, earthy, herbal characteristics', suggesting less complexity.
- Quinta dos Avidagos 2011 Avidagos Red (Douro) vs Envolve 2011 Sauvignon Blanc (Sonoma Valley) -> A (clear): Option A describes a wine with structured, layered flavors including firm tannins, juicy red berries, and acidity, indicating complexity. Option B focuses on a straightforward, tart, and fruity profile with clear descriptors of specific flavors but lacks the nuanced layers found in Option A.
- Kirkland Signature 2011 Mountain Cuvée Cabernet Sauvignon (Napa Valley) vs Clarksburg Wine Company 2010 Chenin Blanc (Clarksburg) -> A (clear): Option A describes a wine with oak and multiple flavor notes like plum, coffee, and chocolate, indicating complexity. Option B is described as straightforward with notes of pear and lime. The complexity in Option A is evident compared to the simplicity in Option B.
