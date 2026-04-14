# Movies_50 Summary

Choice context: A person is deciding which movie to watch based on the movie's description, genre, cast, and plot summary.

## Cross-Variant Consistency (Direct Score vs Bradley-Terry)

| Dim | Name | Spearman rho | Kendall tau | N | Flag |
| --- | ---- | -----------: | ----------: | -: | ---- |
| 1 | Action vs. Character-Driven | 0.907 | 0.794 | 50 | |
| 2 | Historical vs. Contemporary | 0.854 | 0.720 | 50 | |
| 3 | Romantic vs. Non-Romantic | 0.885 | 0.770 | 50 | |
| 4 | Family-Friendly vs. Adult-Themed | 0.896 | 0.770 | 50 | |
| 5 | Visual Appeal vs. Narrative Complexity | 0.864 | 0.745 | 50 | |
| 6 | Humor vs. Seriousness | 0.918 | 0.809 | 50 | |
| 7 | Classic Adaptation vs. Original Story | 0.672 | 0.565 | 50 | |
| 8 | Realism vs. Fantasy | 0.935 | 0.827 | 50 | |
| 9 | Star Power vs. Ensemble Cast | 0.868 | 0.740 | 50 | |
| 10 | Adventure vs. Drama | 0.871 | 0.762 | 50 | |

## Dimension 1: Action vs. Character-Driven

Low pole: Action | High pole: Character-Driven

Direct-score low examples:
- Sudden Death (1995) (1): The plot focuses heavily on high-stakes action sequences and saving hostages, typical of action-driven films.
- GoldenEye (1995) (1): The plot summary emphasizes high-stakes action sequences and thrilling chase scenes typical of an action-driven film.
- Dracula: Dead and Loving It (1995) (1): The movie is a comedy-horror spoof filled with slapstick humor and parodies, focusing more on action and comedic sequences than deep character development.
- Cutthroat Island (1995) (1): The plot focuses heavily on action-adventure elements and treasure hunting, with less emphasis on character development.
- Ace Ventura: When Nature Calls (1995) (1): The movie focuses more on slapstick humor and zany antics rather than deep character development.

Direct-score high examples:
- When Night Is Falling (1995) (4): The plot focuses on the character's personal growth and emotional journey as she navigates her relationship and confronts her beliefs.
- How to Make an American Quilt (1995) (4): The movie focuses on the personal growth and emotional journeys of its characters, particularly the young woman learning about life through the stories of others.
- Restoration (1995) (4): The movie focuses on the deep character arc of Robert Merivel as he navigates love, betrayal, and the complexities of power.
- Richard III (1995) (4): The film focuses heavily on Richard III's psychological manipulation and character arc as he schemes to gain power.
- Cry, the Beloved Country (1995) (4): The film focuses deeply on the character development of Stephen Kumalo as he confronts personal and societal challenges.

Bradley-Terry low examples:
- Mortal Kombat (1995) (-1.0)
- Assassins (1995) (-0.98161)
- Dracula: Dead and Loving It (1995) (-0.812677)
- Sudden Death (1995) (-0.765551)
- Cutthroat Island (1995) (-0.727477)

Bradley-Terry high examples:
- Leaving Las Vegas (1995) (0.913326)
- Cry, the Beloved Country (1995) (0.830295)
- Sense and Sensibility (1995) (0.698911)
- Dead Man Walking (1995) (0.637524)
- Carrington (1995) (0.600784)

Pairwise spot checks:
- Balto (1995) vs Now and Then (1995) -> B (marginal): Balto focuses more on an adventurous plot with a clear goal, featuring less emphasis on deep character development compared to Now and Then, which delves into the emotional and psychological journeys of its characters over time.
- Jumanji (1995) vs American President, The (1995) -> B (clear): Option A, 'Jumanji', leans towards the action side with its focus on adventure and survival against the game's challenges, whereas Option B, 'The American President', emphasizes character-driven elements through the exploration of the president's personal and political dilemmas.
- Shanghai Triad (Yao a yao yao dao waipo qiao) (1995) vs Money Train (1995) -> A (clear): Option A, 'Shanghai Triad', focuses heavily on the psychological journey and development of its characters within a complex narrative, aligning closely with the character-driven pole. In contrast, Option B, 'Money Train', emphasizes action sequences and a heist plot, placing it closer to the action pole.

Cross-variant consistency:
- Spearman rho = 0.907, Kendall tau = 0.794 (n=50)

## Dimension 2: Historical vs. Contemporary

Low pole: Historical | High pole: Contemporary

Direct-score low examples:
- Tom and Huck (1995) (1): The movie is set in the 19th century, aligning it closely with a historical setting.
- Dracula: Dead and Loving It (1995) (1): The movie is set in 19th-century England, which is a historical period.
- Balto (1995) (1): Balto is based on a true story set in a historical context involving a specific historical event in Alaska.
- Nixon (1995) (1): The movie is a biographical drama focusing on the life of Richard Nixon, primarily set in the historical context of the 1960s and 70s.
- Cutthroat Island (1995) (1): The movie is set in a historical period with pirates and treasure hunts.

Direct-score high examples:
- Seven (a.k.a. Se7en) (1995) (4): Seven is set in modern times and deals with contemporary issues of crime and morality.
- To Die For (1995) (4): The movie is set in modern times and deals with contemporary issues such as media obsession and fame.
- Richard III (1995) (4): The film sets Shakespeare's 'Richard III' in a modern-day context, aligning with contemporary themes.
- Clueless (1995) (4): Clueless is a modern retelling of Jane Austen's novel set in a contemporary Beverly Hills high school.
- Dangerous Minds (1995) (4): The movie is set in modern times and deals with contemporary issues such as education and race.

Bradley-Terry low examples:
- Restoration (1995) (-0.96414)
- Othello (1995) (-0.923605)
- Persuasion (1995) (-0.755978)
- Sense and Sensibility (1995) (-0.754043)
- Shanghai Triad (Yao a yao yao dao waipo qiao) (1995) (-0.627128)

Bradley-Terry high examples:
- American President, The (1995) (1.0)
- Clueless (1995) (0.929938)
- Seven (a.k.a. Se7en) (1995) (0.8073)
- Get Shorty (1995) (0.768279)
- Waiting to Exhale (1995) (0.716916)

Pairwise spot checks:
- Cutthroat Island (1995) vs Get Shorty (1995) -> B (clear): Option A, 'Cutthroat Island', is set in a historical context involving pirates, placing it closer to the low pole. Option B, 'Get Shorty', is set in modern times and deals with contemporary issues in Hollywood, placing it closer to the high pole.
- Jumanji (1995) vs Tom and Huck (1995) -> A (clear): Option A, 'Jumanji', is set in modern times without any specific historical context, aligning it more closely with contemporary settings. Option B, 'Tom and Huck', is set in the 19th century, giving it a clear historical setting.
- Shanghai Triad (Yao a yao yao dao waipo qiao) (1995) vs Copycat (1995) -> B (clear): Option A, 'Shanghai Triad', is set in the 1930s, placing it firmly in a historical context. In contrast, Option B, 'Copycat', is set in contemporary times and deals with current issues like serial killers and psychological profiling.

Cross-variant consistency:
- Spearman rho = 0.854, Kendall tau = 0.720 (n=50)

## Dimension 3: Romantic vs. Non-Romantic

Low pole: Non-Romantic | High pole: Romantic

Direct-score low examples:
- Sudden Death (1995) (0): The plot summary focuses entirely on action and suspense without any mention of romantic elements.
- Nixon (1995) (0): The movie focuses on the political career of Richard Nixon without significant romantic storylines.
- Ace Ventura: When Nature Calls (1995) (0): The plot summary indicates a comedy focused on adventure and slapstick humor without mention of romantic elements.
- Dead Presidents (1995) (0): The plot summary focuses on themes of war, poverty, and crime without mentioning any romantic elements.
- Seven (a.k.a. Se7en) (1995) (0): Seven is a psychological thriller focused on crime-solving and does not contain significant romantic elements.

Direct-score high examples:
- When Night Is Falling (1995) (4): The movie is a romantic drama centered around a complex romantic relationship that challenges the protagonist's beliefs.
- Pocahontas (1995) (4): The movie features a significant romantic storyline between Pocahontas and John Smith amidst cultural conflicts.
- How to Make an American Quilt (1995) (4): The movie focuses on themes of love and life through the stories shared by the women in the quilting circle, indicating a strong romantic element.
- Clueless (1995) (4): Clueless has a significant romantic storyline as part of its narrative.
- Carrington (1995) (4): The movie delves into the complex and unconventional romantic relationship between Dora Carrington and Lytton Strachey.

Bradley-Terry low examples:
- Sudden Death (1995) (-0.366578)
- Mortal Kombat (1995) (-0.364683)
- Usual Suspects, The (1995) (-0.363252)
- Dracula: Dead and Loving It (1995) (-0.357279)
- Toy Story (1995) (-0.355224)

Bradley-Terry high examples:
- Sense and Sensibility (1995) (1.0)
- Persuasion (1995) (0.852897)
- When Night Is Falling (1995) (0.807841)
- Sabrina (1995) (0.75495)
- Waiting to Exhale (1995) (0.729892)

Pairwise spot checks:
- Nixon (1995) vs Usual Suspects, The (1995) -> negligible (marginal): Both 'Nixon' and 'The Usual Suspects' lack significant romantic storylines, focusing instead on political drama and crime thriller narratives respectively. Neither movie emphasizes romantic elements, placing them both firmly towards the non-romantic end of the spectrum.
- Toy Story (1995) vs Restoration (1995) -> B (marginal): Toy Story focuses primarily on themes of friendship and adventure, lacking significant romantic elements. Restoration, while centered around political and social themes, includes elements of love and personal relationships, placing it closer to the romantic pole.
- Babe (1995) vs Leaving Las Vegas (1995) -> B (clear): Option A, 'Babe', focuses primarily on themes of friendship and personal growth without significant romantic elements. Option B, 'Leaving Las Vegas', centers around a deep, albeit tragic, romantic relationship that forms the core of its narrative.

Cross-variant consistency:
- Spearman rho = 0.885, Kendall tau = 0.770 (n=50)

## Dimension 4: Family-Friendly vs. Adult-Themed

Low pole: Adult-Themed | High pole: Family-Friendly

Direct-score low examples:
- Waiting to Exhale (1995) (1): The movie deals with mature themes such as infidelity and single motherhood.
- Heat (1995) (1): Heat (1995) contains mature themes and content unsuitable for children.
- Sudden Death (1995) (1): The movie involves action and terrorism, which are mature themes unsuitable for young audiences.
- GoldenEye (1995) (1): The movie contains intense action sequences and mature themes unsuitable for children.
- Nixon (1995) (1): Nixon is a biographical drama about the former U.S. president, containing mature themes unsuitable for children.

Direct-score high examples:
- Pocahontas (1995) (4): Pocahontas is an animated musical film suitable for children with themes of cultural understanding.
- It Takes Two (1995) (4): The movie is a heartwarming family comedy with themes of family, friendship, and communication, suitable for all ages.
- Babe (1995) (4): Babe is a heartwarming family film suitable for all ages, focusing on themes like friendship and acceptance.
- Balto (1995) (4): Balto is an animated adventure film with themes of courage, friendship, and perseverance, suitable for viewers of all ages.
- Toy Story (1995) (4): Toy Story is an animated adventure suitable for all ages, focusing on themes of friendship and loyalty.

Bradley-Terry low examples:
- Casino (1995) (-0.871923)
- Seven (a.k.a. Se7en) (1995) (-0.858318)
- Leaving Las Vegas (1995) (-0.797268)
- Copycat (1995) (-0.715092)
- Heat (1995) (-0.698093)

Bradley-Terry high examples:
- Toy Story (1995) (1.0)
- Balto (1995) (0.941299)
- It Takes Two (1995) (0.875001)
- Babe (1995) (0.843205)
- Pocahontas (1995) (0.780441)

Pairwise spot checks:
- Toy Story (1995) vs Dead Man Walking (1995) -> A (clear): Option A, 'Toy Story', is highly family-friendly, featuring animated characters and themes suitable for children. In contrast, Option B, 'Dead Man Walking', deals with serious adult themes such as capital punishment and redemption, making it less family-friendly.
- Assassins (1995) vs Father of the Bride Part II (1995) -> B (clear): Option A, 'Assassins', contains mature themes and intense action sequences, making it less family-friendly. Option B, 'Father of the Bride Part II', is a comedy centered around family dynamics and is more suitable for a general audience.
- Powder (1995) vs It Takes Two (1995) -> B (clear): Option A, 'Powder', contains mature themes and is not designed for children, placing it closer to the low pole. Option B, 'It Takes Two', is explicitly a children's comedy with family-friendly themes, placing it closer to the high pole.

Cross-variant consistency:
- Spearman rho = 0.896, Kendall tau = 0.770 (n=50)

## Dimension 5: Visual Appeal vs. Narrative Complexity

Low pole: Narrative Complexity | High pole: Visual Appeal

Direct-score low examples:
- Waiting to Exhale (1995) (1): The plot focuses on complex personal and romantic struggles of the characters.
- American President, The (1995) (1): The American President focuses more on its intricate political and romantic narrative than on visual appeal.
- Nixon (1995) (1): The movie focuses on the intricate plot and complex narrative of Richard Nixon's political career.
- Casino (1995) (1): Casino focuses heavily on its intricate narrative and character development rather than visual spectacle.
- Copycat (1995) (1): The plot focuses heavily on the narrative complexity of a serial killer case and psychological elements.

Direct-score high examples:
- Pocahontas (1995) (4): Pocahontas features vibrant animation and visually appealing scenes that are characteristic of Disney's animated films.
- Across the Sea of Time (1995) (4): The documentary uses IMAX technology to present visually stunning scenes of New York City and the immigrant experience.
- Mortal Kombat (1995) (3): The movie features action and fantasy elements suggesting visual appeal but also has a narrative involving a tournament with personal and supernatural challenges.
- Clueless (1995) (3): Clueless features stylish visuals and fashion but is more noted for its narrative and dialogue.
- Babe (1995) (3): Babe features charming visuals suitable for children but also focuses on narrative elements like friendship and self-belief.

Bradley-Terry low examples:
- Usual Suspects, The (1995) (-0.824623)
- Seven (a.k.a. Se7en) (1995) (-0.823207)
- Othello (1995) (-0.708393)
- Nixon (1995) (-0.663249)
- Cry, the Beloved Country (1995) (-0.655385)

Bradley-Terry high examples:
- Across the Sea of Time (1995) (1.0)
- City of Lost Children, The (Cité des enfants perdus, La) (1995) (0.817478)
- Mortal Kombat (1995) (0.762694)
- Pocahontas (1995) (0.737759)
- Cutthroat Island (1995) (0.68438)

Pairwise spot checks:
- GoldenEye (1995) vs Now and Then (1995) -> A (clear): Option A, 'GoldenEye', features high-stakes action sequences and thrilling chase scenes that emphasize visual appeal over narrative complexity. Option B, 'Now and Then', focuses more on character development and emotional depth, placing it closer to the low pole of the dimension.
- Shanghai Triad (Yao a yao yao dao waipo qiao) (1995) vs Toy Story (1995) -> B (marginal): Shanghai Triad focuses more on its narrative complexity with themes of power and loyalty, while Toy Story offers visually appealing animation and vibrant colors. However, Toy Story leans more towards visual appeal due to its animated nature and colorful characters.
- Cutthroat Island (1995) vs Powder (1995) -> A (clear): Cutthroat Island focuses on action and adventure with visually engaging scenes of sea battles and treasure hunts, placing it higher on the visual appeal side. Powder, on the other hand, centers around a complex narrative involving a character with supernatural abilities and societal themes, leaning towards narrative complexity.

Cross-variant consistency:
- Spearman rho = 0.864, Kendall tau = 0.745 (n=50)

## Dimension 6: Humor vs. Seriousness

Low pole: Seriousness | High pole: Humor

Direct-score low examples:
- Heat (1995) (1): The plot summary indicates a serious tone focused on a cat-and-mouse game between a thief and a detective.
- Sudden Death (1995) (1): The plot summary indicates a serious tone focused on action and life-threatening situations.
- Nixon (1995) (1): The movie is a biographical drama focusing on the serious political career of Richard Nixon.
- Casino (1995) (1): Casino is a crime drama focusing on serious themes like power, greed, and betrayal.
- Copycat (1995) (1): The movie's genres and plot summary indicate a serious tone focused on crime and thriller elements.

Direct-score high examples:
- Clueless (1995) (4): Clueless is a beloved teen comedy known for its witty dialogue.
- It Takes Two (1995) (4): The movie is described as a heartwarming family comedy with a delightful mix of humor and heartfelt moments.
- Get Shorty (1995) (4): The movie blends comedy with crime and thriller elements, featuring a light-hearted and humorous approach to its plot.
- Ace Ventura: When Nature Calls (1995) (4): The movie is filled with slapstick humor, zany antics, and Jim Carrey's signature comedic performance.
- Dracula: Dead and Loving It (1995) (4): The movie is a horror-comedy spoof filled with slapstick humor and parodies of classic vampire lore.

Bradley-Terry low examples:
- Seven (a.k.a. Se7en) (1995) (-0.781466)
- Cry, the Beloved Country (1995) (-0.712761)
- Othello (1995) (-0.629454)
- Nixon (1995) (-0.598002)
- Copycat (1995) (-0.575786)

Bradley-Terry high examples:
- Ace Ventura: When Nature Calls (1995) (1.0)
- Dracula: Dead and Loving It (1995) (0.869462)
- Toy Story (1995) (0.772902)
- Clueless (1995) (0.769157)
- Grumpier Old Men (1995) (0.643988)

Pairwise spot checks:
- Now and Then (1995) vs Persuasion (1995) -> A (marginal): Now and Then (1995) includes elements of humor and light-hearted moments typical of its genre, while Persuasion (1995) is a more traditional drama with romantic undertones but lacks significant comedic elements.
- Jumanji (1995) vs American President, The (1995) -> A (clear): Option A, 'Jumanji', incorporates significant comedic elements and light-hearted adventures, making it more humorous. Option B, 'The American President', while listed under comedy, leans more towards drama and romance, thus being less humorous overall.
- It Takes Two (1995) vs Seven (a.k.a. Se7en) (1995) -> A (clear): Option A, 'It Takes Two', is a family comedy with a focus on humor and light-hearted storytelling, placing it significantly towards the high pole of humor. In contrast, Option B, 'Seven', is a psychological thriller with a serious tone and dark themes, placing it firmly at the low pole of seriousness.

Cross-variant consistency:
- Spearman rho = 0.918, Kendall tau = 0.809 (n=50)

## Dimension 7: Classic Adaptation vs. Original Story

Low pole: Original Story | High pole: Classic Adaptation

Direct-score low examples:
- Grumpier Old Men (1995) (0): Grumpier Old Men is an original story without adaptation from a classic work.
- Father of the Bride Part II (1995) (0): The movie is an original story without adaptation from a classic work.
- Heat (1995) (0): Heat (1995) is an original story without adaptation from a classic work.
- Sudden Death (1995) (0): The plot summary indicates an original narrative without reference to a classic literary adaptation.
- Nixon (1995) (0): Nixon is a biographical drama based on the life of Richard Nixon, not adapted from a classic literary work.

Direct-score high examples:
- Richard III (1995) (4): The movie is an adaptation of William Shakespeare's play Richard III.
- Clueless (1995) (4): Clueless is a modern retelling of Jane Austen's novel Emma, making it a clear adaptation of a classic work.
- Persuasion (1995) (4): Persuasion is an adaptation of Jane Austen's novel of the same name.
- Othello (1995) (4): The movie is an adaptation of William Shakespeare's play 'Othello', a classic work.
- Sense and Sensibility (1995) (4): The movie is an adaptation of Jane Austen's classic novel 'Sense and Sensibility'.

Bradley-Terry low examples:
- Money Train (1995) (-0.237774)
- Sudden Death (1995) (-0.236268)
- Across the Sea of Time (1995) (-0.229867)
- Ace Ventura: When Nature Calls (1995) (-0.227611)
- Dead Presidents (1995) (-0.227557)

Bradley-Terry high examples:
- Othello (1995) (1.0)
- Sense and Sensibility (1995) (0.916436)
- Richard III (1995) (0.831863)
- Tom and Huck (1995) (0.734766)
- Persuasion (1995) (0.701347)

Pairwise spot checks:
- American President, The (1995) vs Sudden Death (1995) -> negligible (marginal): Both 'The American President' and 'Sudden Death' are original stories without direct adaptation from classic literature. They both sit near the low pole of the dimension.
- Powder (1995) vs When Night Is Falling (1995) -> negligible (marginal): Both 'Powder' and 'When Night Is Falling' are original stories without clear adaptation from classic literature or well-known works. Neither leans significantly towards the high pole of the dimension.
- Sense and Sensibility (1995) vs Babe (1995) -> A (clear): Option A, 'Sense and Sensibility', is an adaptation of Jane Austen's classic novel, placing it firmly at the high pole of the dimension. In contrast, Option B, 'Babe', is an original story, positioning it closer to the low pole.

Cross-variant consistency:
- Spearman rho = 0.672, Kendall tau = 0.565 (n=50)

## Dimension 8: Realism vs. Fantasy

Low pole: Fantasy | High pole: Realism

Direct-score low examples:
- Toy Story (1995) (1): The movie features toys coming to life, which is a clear fantastical element.
- Jumanji (1995) (1): The plot involves a magical board game that brings jungle adventures to life, which is a clear fantastical element.
- Dracula: Dead and Loving It (1995) (1): The movie is a comedy-horror spoof that parodies classic vampire lore, featuring fantastical elements.
- Ace Ventura: When Nature Calls (1995) (1): The movie features a fantastical plot with eccentric characters and zany antics.
- City of Lost Children, The (Cité des enfants perdus, La) (1995) (1): The movie is a dark fantasy set in a surreal and dystopian world with fantastical elements.

Direct-score high examples:
- Seven (a.k.a. Se7en) (1995) (4): Seven is a psychological thriller grounded in realism with a focus on human nature and societal issues.
- To Die For (1995) (4): To Die For is a realistic drama that explores themes of media obsession and the consequences of ambition.
- Dead Presidents (1995) (4): The movie explores themes of race, poverty, and the impact of war on individuals and communities, grounding it in social realism.
- Richard III (1995) (4): The movie is a realistic adaptation of Shakespeare's play set in a modern context, focusing on political manipulation and social commentary.
- Cry, the Beloved Country (1995) (4): The film explores themes of racial injustice and social issues grounded in reality.

Bradley-Terry low examples:
- Mortal Kombat (1995) (-1.0)
- Toy Story (1995) (-0.858785)
- Jumanji (1995) (-0.803662)
- It Takes Two (1995) (-0.724872)
- City of Lost Children, The (Cité des enfants perdus, La) (1995) (-0.669743)

Bradley-Terry high examples:
- Dead Man Walking (1995) (0.940887)
- Cry, the Beloved Country (1995) (0.936644)
- Nixon (1995) (0.795662)
- Dead Presidents (1995) (0.695362)
- Shanghai Triad (Yao a yao yao dao waipo qiao) (1995) (0.637596)

Pairwise spot checks:
- Dead Man Walking (1995) vs American President, The (1995) -> A (clear): Dead Man Walking is deeply rooted in real-life events and social issues, making it highly realistic. The American President, while dealing with political themes, incorporates romantic and comedic elements that slightly reduce its realism.
- GoldenEye (1995) vs American President, The (1995) -> B (clear): Option A, 'GoldenEye', contains elements of espionage and action that are stylized and exaggerated, leaning towards fantasy. Option B, 'The American President', focuses on political drama and romance, offering a more grounded and realistic portrayal of life and politics.
- Casino (1995) vs Wings of Courage (1995) -> A (clear): Option A, 'Casino', is a crime drama grounded in real-world events and themes, making it more realistic. Option B, 'Wings of Courage', while based on true events, leans more towards adventure and romance, incorporating more fantastical elements and less social commentary.

Cross-variant consistency:
- Spearman rho = 0.935, Kendall tau = 0.827 (n=50)

## Dimension 9: Star Power vs. Ensemble Cast

Low pole: Ensemble Cast | High pole: Star Power

Direct-score low examples:
- Across the Sea of Time (1995) (1): The movie stars lesser-known actors and focuses more on the ensemble cast of characters surrounding Tomas's journey.
- Toy Story (1995) (2): The movie features well-known voice actors like Tom Hanks and Tim Allen, but the focus is more on the ensemble cast of toys.
- Tom and Huck (1995) (2): The movie stars relatively lesser-known actors at the time, suggesting a lower emphasis on star power.
- Balto (1995) (2): The movie features known actors like Kevin Bacon but the focus seems more on the ensemble of characters rather than individual star power.
- Sense and Sensibility (1995) (2): The movie features multiple prominent actors without a single dominant star presence.

Direct-score high examples:
- Seven (a.k.a. Se7en) (1995) (4): The movie stars well-known actors Brad Pitt, Morgan Freeman, and Kevin Spacey.
- Richard III (1995) (4): Ian McKellen, a renowned actor, stars as the central character Richard III.
- Dangerous Minds (1995) (4): The movie stars Michelle Pfeiffer, a well-known actress, which indicates significant star power.
- Leaving Las Vegas (1995) (4): The movie stars Nicolas Cage, a well-known actor, which contributes to its star power.
- Ace Ventura: When Nature Calls (1995) (4): The movie prominently features Jim Carrey, a well-known actor, in the lead role.

Bradley-Terry low examples:
- Across the Sea of Time (1995) (-0.971083)
- Four Rooms (1995) (-0.835225)
- When Night Is Falling (1995) (-0.783299)
- Tom and Huck (1995) (-0.739996)
- Persuasion (1995) (-0.65221)

Bradley-Terry high examples:
- GoldenEye (1995) (1.0)
- Ace Ventura: When Nature Calls (1995) (0.870735)
- Assassins (1995) (0.753513)
- Dangerous Minds (1995) (0.703858)
- Nixon (1995) (0.684912)

Pairwise spot checks:
- Cutthroat Island (1995) vs Seven (a.k.a. Se7en) (1995) -> B (clear): Cutthroat Island features notable actors but does not heavily rely on star power as its main draw. In contrast, Seven prominently features well-known actors like Brad Pitt and Morgan Freeman, emphasizing star power more significantly.
- City of Lost Children, The (Cité des enfants perdus, La) (1995) vs Nixon (1995) -> B (clear): Option A, 'City of Lost Children', features actors who are not as globally recognized as those in Option B, 'Nixon'. 'Nixon' stars Anthony Hopkins, a highly acclaimed actor, which elevates its star power significantly.
- Money Train (1995) vs Clueless (1995) -> A (marginal): Money Train features Wesley Snipes and Woody Harrelson, both well-known actors, giving it a notable star power. Clueless, while featuring Alicia Silverstone prominently, also relies on the collective appeal of its ensemble cast, including Stacey Dash and Brittany Murphy.

Cross-variant consistency:
- Spearman rho = 0.868, Kendall tau = 0.740 (n=50)

## Dimension 10: Adventure vs. Drama

Low pole: Drama | High pole: Adventure

Direct-score low examples:
- Grumpier Old Men (1995) (1): The plot focuses on character relationships and romantic comedy elements without adventurous themes.
- Waiting to Exhale (1995) (1): The movie focuses on dramatic storytelling and character development without any adventurous elements.
- Father of the Bride Part II (1995) (1): The plot focuses on family drama and personal adjustment rather than adventurous themes.
- Sabrina (1995) (1): The plot focuses on romantic and personal development themes without adventurous elements.
- American President, The (1995) (1): The plot focuses on dramatic storytelling and character development within a political context.

Direct-score high examples:
- Mortal Kombat (1995) (4): The plot involves a group of warriors competing in an adventurous tournament with supernatural elements.
- Wings of Courage (1995) (4): The movie features themes of daring adventures and pushing the boundaries of flight.
- Cutthroat Island (1995) (4): The plot involves a high-seas treasure hunt with obstacles like rival pirates and treacherous waters, aligning closely with adventurous themes.
- Balto (1995) (4): Balto is an animated adventure film that focuses on a treacherous journey and survival in a remote Alaskan setting.
- GoldenEye (1995) (4): The movie features intense action sequences, thrilling chase scenes, and a climactic showdown, aligning closely with adventurous themes.

Bradley-Terry low examples:
- Othello (1995) (-0.690796)
- Dead Man Walking (1995) (-0.616464)
- Sense and Sensibility (1995) (-0.509466)
- Persuasion (1995) (-0.505322)
- Leaving Las Vegas (1995) (-0.473942)

Bradley-Terry high examples:
- Cutthroat Island (1995) (1.0)
- Jumanji (1995) (0.947016)
- Balto (1995) (0.824373)
- GoldenEye (1995) (0.817479)
- Mortal Kombat (1995) (0.793308)

Pairwise spot checks:
- Cutthroat Island (1995) vs Dangerous Minds (1995) -> A (clear): Option A, 'Cutthroat Island', is an action-adventure film centered around a treasure hunt and high-seas adventures, placing it closer to the high pole. Option B, 'Dangerous Minds', is a drama focusing on personal growth and educational challenges, placing it closer to the low pole.
- Get Shorty (1995) vs Mortal Kombat (1995) -> B (clear): Option A, 'Get Shorty', leans towards the Drama end with its focus on navigating the film industry and character interactions, while Option B, 'Mortal Kombat', aligns more closely with the Adventure pole due to its fantastical setting and action-packed battles.
- Jumanji (1995) vs Persuasion (1995) -> A (clear): Option A, 'Jumanji', is heavily centered around adventure and survival themes, fitting well into the high pole of the Adventure vs. Drama spectrum. In contrast, Option B, 'Persuasion', focuses on romantic and dramatic storytelling, aligning closely with the low pole of this dimension.

Cross-variant consistency:
- Spearman rho = 0.871, Kendall tau = 0.762 (n=50)
