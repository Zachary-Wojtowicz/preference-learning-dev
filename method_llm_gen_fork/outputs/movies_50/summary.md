# Movies_50 Summary

Choice context: A person is deciding which movie to watch based on the movie's description, genre, cast, and plot summary.

## Cross-Variant Consistency (Direct Score vs Bradley-Terry)


| Dim | Name                 | Spearman rho | Kendall tau | N   | Flag           |
| --- | -------------------- | ------------ | ----------- | --- | -------------- |
| 1   | Action Intensity     | 0.880        | 0.751       | 50  |                |
| 2   | Emotional Depth      | 0.890        | 0.756       | 50  |                |
| 3   | Sci-Fi Elements      | 0.451        | 0.367       | 50  |                |
| 4   | Comedy Level         | 0.904        | 0.792       | 50  |                |
| 5   | Historical Accuracy  | 0.655        | 0.530       | 50  |                |
| 6   | Visual Effects       | 0.725        | 0.602       | 50  |                |
| 7   | Character Complexity | 0.891        | 0.760       | 50  |                |
| 8   | Dialogue Quality     | 0.434        | 0.326       | 50  |                |
| 9   | Music Influence      | 0.657        | 0.538       | 50  |                |
| 10  | Pacing Speed         | 0.248        | 0.198       | 50  | **UNRELIABLE** |


## Dimension 1: Action Intensity

Low pole: Low Action | High pole: High Action

Direct-score low examples:

- Waiting to Exhale (1995) (0): The plot summary indicates a focus on character development and emotional journeys without any mention of action sequences.
- Sabrina (1995) (0): The plot summary indicates that 'Sabrina' focuses on romance and character development with no mention of action sequences.
- American President, The (1995) (0): The American President focuses primarily on political drama and romance with no significant action sequences.
- Nixon (1995) (0): The movie 'Nixon' focuses heavily on dialogue and character development, with no significant action sequences.
- Sense and Sensibility (1995) (0): Sense and Sensibility focuses primarily on character development and dialogue, with no significant action scenes.

Direct-score high examples:

- Mortal Kombat (1995) (4): The movie features frequent and intense action scenes characteristic of its genre and source material.
- Cutthroat Island (1995) (4): The movie features numerous high-seas action sequences and battles, indicating a significant presence of intense action.
- GoldenEye (1995) (4): The movie features multiple intense action sequences, thrilling chase scenes, and a climactic showdown, indicating a high level of action.
- Sudden Death (1995) (4): The plot summary indicates a movie with frequent and intense action sequences, fitting well into the high-action category.
- Seven (a.k.a. Se7en) (1995) (3): Seven contains several intense action scenes, particularly during the chase and confrontation sequences, but it is primarily focused on its plot and character dynamics.

Bradley-Terry low examples:

- Now and Then (1995) (-0.678912)
- Carrington (1995) (-0.586775)
- Persuasion (1995) (-0.577938)
- How to Make an American Quilt (1995) (-0.569208)
- Sense and Sensibility (1995) (-0.511849)

Bradley-Terry high examples:

- Mortal Kombat (1995) (1.0)
- Assassins (1995) (0.944604)
- GoldenEye (1995) (0.799808)
- Money Train (1995) (0.677204)
- Heat (1995) (0.665076)

Pairwise spot checks:

- Toy Story (1995) vs Assassins (1995) -> B (clear): Toy Story (1995) features some adventurous moments but primarily focuses on character development and dialogue, making it lean towards the lower end of action intensity. On the other hand, 'Assassins' is an action-packed thriller with numerous intense action scenes and stunts, placing it closer to the higher end of action intensity.
- GoldenEye (1995) vs Wings of Courage (1995) -> A (clear): Option A, 'GoldenEye', features numerous intense action sequences, chases, and a climactic showdown, placing it firmly towards the high pole of action intensity. In contrast, Option B, 'Wings of Courage', focuses more on the biographical and romantic aspects of early aviators, with minimal action sequences.
- American President, The (1995) vs Dead Man Walking (1995) -> negligible (marginal): Both 'The American President' and 'Dead Man Walking' are primarily focused on character development and dialogue, with very little emphasis on action sequences. Neither movie features significant action scenes that would move them towards the high pole.

Cross-variant consistency:

- Spearman rho = 0.880, Kendall tau = 0.751 (n=50)

## Dimension 2: Emotional Depth

Low pole: Shallow Emotions | High pole: Deep Emotions

Direct-score low examples:

- Grumpier Old Men (1995) (1): The movie focuses primarily on light-hearted comedy and romantic elements without delving deeply into complex emotional landscapes.
- Sudden Death (1995) (1): The plot focuses primarily on action and suspense rather than exploring complex emotional landscapes or deep character relationships.
- Dracula: Dead and Loving It (1995) (1): The movie is a comedy-horror spoof that prioritizes humor over exploring deep emotional landscapes or complex character relationships.
- Cutthroat Island (1995) (1): The plot focuses primarily on action and adventure elements with minimal exploration of complex emotional landscapes.
- Four Rooms (1995) (1): Four Rooms focuses more on quirky characters and absurd situations rather than delving deeply into their emotional states or relationships.

Direct-score high examples:

- When Night Is Falling (1995) (4): The film explores the emotional journey of a protagonist navigating a complex new relationship and confronting personal fears, indicating significant emotional depth.
- How to Make an American Quilt (1995) (4): The film explores the emotional journeys and relationships of its characters through the medium of storytelling and quilting, indicating a significant depth of emotion.
- Restoration (1995) (4): The film explores complex emotional landscapes through its portrayal of love, betrayal, and the fragility of power, indicating a significant depth of emotion.
- Richard III (1995) (4): The film explores the complex emotional landscape of a power-hungry king and the intricate relationships and betrayals within the royal court.
- Cry, the Beloved Country (1995) (4): The film deeply explores themes of forgiveness, reconciliation, and hope through complex character relationships and emotional struggles.

Bradley-Terry low examples:

- Ace Ventura: When Nature Calls (1995) (-1.0)
- Mortal Kombat (1995) (-0.887333)
- Sudden Death (1995) (-0.788338)
- Money Train (1995) (-0.690045)
- Dracula: Dead and Loving It (1995) (-0.620425)

Bradley-Terry high examples:

- Othello (1995) (0.706494)
- Carrington (1995) (0.695207)
- Sense and Sensibility (1995) (0.648585)
- Dead Man Walking (1995) (0.624763)
- Leaving Las Vegas (1995) (0.578313)

Pairwise spot checks:

- Toy Story (1995) vs Across the Sea of Time (1995) -> A (marginal): Toy Story explores complex themes of friendship and loyalty between its characters, providing a rich emotional narrative despite its animated format. Across the Sea of Time, while touching on profound themes of immigration and cultural identity, may not delve as deeply into individual emotional experiences as Toy Story does.
- GoldenEye (1995) vs Pocahontas (1995) -> B (clear): Option A, 'GoldenEye', focuses primarily on action and adventure, with less emphasis on exploring deep emotional landscapes. Option B, 'Pocahontas', delves into themes of cultural conflict, love, and personal growth, offering a richer emotional narrative.
- American President, The (1995) vs Wings of Courage (1995) -> A (clear): Option A, 'The American President', explores complex emotional dynamics between political duty and personal love, offering a rich tapestry of deep emotions and character development. Option B, 'Wings of Courage', while touching on themes of courage and passion, focuses more on adventure and the pioneering spirit, resulting in less emphasis on intricate emotional landscapes.

Cross-variant consistency:

- Spearman rho = 0.890, Kendall tau = 0.756 (n=50)

## Dimension 3: Sci-Fi Elements

Low pole: Minimal Sci-Fi | High pole: Heavy Sci-Fi

Direct-score low examples:

- Grumpier Old Men (1995) (0): The movie focuses on realistic settings and human relationships without any science fiction elements.
- Waiting to Exhale (1995) (0): The movie 'Waiting to Exhale' focuses entirely on realistic, contemporary settings and human relationships without any science fiction elements.
- Father of the Bride Part II (1995) (0): The movie focuses entirely on realistic family dynamics and personal relationships without any science fiction elements.
- Sabrina (1995) (0): The movie 'Sabrina' (1995) is a romantic comedy with no significant sci-fi elements, maintaining a realistic setting throughout.
- Tom and Huck (1995) (0): The movie is set in 19th century America and contains no science fiction elements.

Direct-score high examples:

- Twelve Monkeys (a.k.a. 12 Monkeys) (1995) (4): The film incorporates significant elements of time travel and a post-apocalyptic future setting, which are central to its plot.
- GoldenEye (1995) (3): The movie includes a powerful satellite weapon and space-related technology, which adds significant sci-fi elements, though the core plot remains grounded in espionage and action.
- City of Lost Children, The (Cité des enfants perdus, La) (1995) (2): The movie incorporates a dystopian setting and scientific experimentation, but these elements are secondary to its fantastical and surreal atmosphere.
- Powder (1995) (2): The movie includes unique electromagnetic abilities, which are a sci-fi element, but the focus is more on drama and human connection rather than a futuristic setting or advanced technology.
- Seven (a.k.a. Se7en) (1995) (1): Seven focuses on a psychological thriller plot with no significant sci-fi elements.

Bradley-Terry low examples:

- Persuasion (1995) (-0.128647)
- Pocahontas (1995) (-0.128364)
- Clueless (1995) (-0.128223)
- Shanghai Triad (Yao a yao yao dao waipo qiao) (1995) (-0.128033)
- Get Shorty (1995) (-0.127847)

Bradley-Terry high examples:

- City of Lost Children, The (Cité des enfants perdus, La) (1995) (1.0)
- Twelve Monkeys (a.k.a. 12 Monkeys) (1995) (0.983655)
- Toy Story (1995) (0.86442)
- Powder (1995) (0.68664)
- GoldenEye (1995) (0.54617)

Pairwise spot checks:

- Toy Story (1995) vs Restoration (1995) -> A (marginal): Toy Story incorporates some futuristic elements with its robotic toys and space-themed action figure, but these are minimal and do not significantly contribute to the overall sci-fi atmosphere. In contrast, Restoration is set in the 17th century and contains no sci-fi elements whatsoever.
- GoldenEye (1995) vs Balto (1995) -> A (clear): Option A, 'GoldenEye', incorporates some futuristic technology and a satellite weapon, but these elements are secondary to the action and espionage plot. Option B, 'Balto', is an animated children's film set in a historical context with no sci-fi elements. The difference in sci-fi content between the two is clear.
- American President, The (1995) vs It Takes Two (1995) -> negligible (marginal): Both 'The American President' and 'It Takes Two' contain minimal sci-fi elements, focusing primarily on realistic settings and human relationships. Neither movie incorporates futuristic technology or speculative science concepts.

Cross-variant consistency:

- Spearman rho = 0.451, Kendall tau = 0.367 (n=50)

## Dimension 4: Comedy Level

Low pole: Little Comedy | High pole: High Comedy

Direct-score low examples:

- Othello (1995) (0): Othello is a dramatic tragedy with no significant comedic elements.
- Shanghai Triad (Yao a yao yao dao waipo qiao) (1995) (0): The plot summary indicates a serious crime drama with no mention of comedic elements.
- Dead Man Walking (1995) (0): The movie is a serious drama with no comedic elements, focusing on themes of redemption and justice.
- Across the Sea of Time (1995) (0): The documentary nature and focus on the immigrant experience and cultural diversity suggest a serious tone with little to no comedic intent.
- Cry, the Beloved Country (1995) (0): The movie is a serious drama focusing on themes of racial injustice and personal struggle without any notable comedic elements.

Direct-score high examples:

- Clueless (1995) (4): Clueless is known for its witty dialogue and comedic situations, aligning well with a high level of comedy.
- Ace Ventura: When Nature Calls (1995) (4): The movie is filled with slapstick humor, zany antics, and Jim Carrey's signature comedic performance, indicating a strong focus on comedy.
- Dracula: Dead and Loving It (1995) (4): The movie is a comedy-horror spoof filled with slapstick humor and parodies of classic vampire lore, indicating a strong emphasis on comedy.
- Grumpier Old Men (1995) (4): The movie is primarily focused on generating humor through the comedic rivalry and antics of the main characters, aligning closely with high comedy films.
- To Die For (1995) (3): To Die For is a dark comedy that incorporates humor, but its focus on drama and thriller elements keeps it from being purely comedic.

Bradley-Terry low examples:

- Copycat (1995) (-0.721389)
- Across the Sea of Time (1995) (-0.68268)
- Othello (1995) (-0.652743)
- Leaving Las Vegas (1995) (-0.606908)
- Dead Man Walking (1995) (-0.56078)

Bradley-Terry high examples:

- Grumpier Old Men (1995) (1.0)
- Clueless (1995) (0.984568)
- Dracula: Dead and Loving It (1995) (0.977044)
- Father of the Bride Part II (1995) (0.747621)
- Sabrina (1995) (0.74602)

Pairwise spot checks:

- Toy Story (1995) vs Dead Man Walking (1995) -> A (clear): Toy Story (1995) is known for its blend of adventure and humor, featuring numerous comedic moments and witty dialogue, placing it significantly towards the high pole of comedy level. In contrast, Dead Man Walking (1995) is a serious drama that focuses on themes of justice and redemption, with virtually no comedic elements, placing it near the low pole.
- GoldenEye (1995) vs Mortal Kombat (1995) -> A (marginal): Option A, 'GoldenEye', incorporates some comedic elements typical of the James Bond franchise, adding light-hearted moments to its action-packed plot. Option B, 'Mortal Kombat', focuses more on intense action and fantasy elements without significant comedic content.
- American President, The (1995) vs Waiting to Exhale (1995) -> A (marginal): The American President incorporates a moderate level of comedy, primarily through witty dialogue and situational humor, whereas Waiting to Exhale focuses more on dramatic and emotional storytelling with less emphasis on comedy.

Cross-variant consistency:

- Spearman rho = 0.904, Kendall tau = 0.792 (n=50)

## Dimension 5: Historical Accuracy

Low pole: Loose History | High pole: Strict History

Direct-score low examples:

- Jumanji (1995) (0): The plot of 'Jumanji' revolves around a magical board game and its fantastical elements, which have no basis in historical fact.
- Sabrina (1995) (0): The plot summary indicates that 'Sabrina' (1995) is a romantic comedy with no apparent attempt to depict historical events or figures accurately.
- Sudden Death (1995) (0): The plot of 'Sudden Death' is an action thriller with no basis in historical events, focusing instead on a fictional scenario.
- GoldenEye (1995) (0): The plot of 'GoldenEye' is a work of fiction with no basis in real historical events.
- Dracula: Dead and Loving It (1995) (0): The movie is a comedy spoof that parodies classic vampire lore and horror tropes, rather than aiming for historical accuracy.

Direct-score high examples:

- Cry, the Beloved Country (1995) (3): The film Cry, the Beloved Country is set during the apartheid era and addresses the social and racial issues of that time, striving for an accurate portrayal of the historical context.
- Across the Sea of Time (1995) (3): The film blends documentary and drama, focusing more on the immigrant experience and cultural diversity rather than strict historical accuracy.
- Dead Man Walking (1995) (3): The film is based on a true story and focuses on the personal journey of the characters rather than strict historical events.
- Carrington (1995) (3): The film focuses on the personal lives and relationship of its subjects rather than strictly adhering to historical events and timelines.
- Wings of Courage (1995) (3): While the film focuses on real historical figures and their contributions to aviation, it likely dramatizes their adventures and personal lives, which may deviate from strict historical accuracy.

Bradley-Terry low examples:

- Dracula: Dead and Loving It (1995) (-0.784253)
- Mortal Kombat (1995) (-0.712676)
- Ace Ventura: When Nature Calls (1995) (-0.69267)
- Pocahontas (1995) (-0.687487)
- City of Lost Children, The (Cité des enfants perdus, La) (1995) (-0.4199)

Bradley-Terry high examples:

- Dead Man Walking (1995) (1.0)
- Carrington (1995) (0.982323)
- Across the Sea of Time (1995) (0.885222)
- Wings of Courage (1995) (0.769494)
- Nixon (1995) (0.712254)

Pairwise spot checks:

- Toy Story (1995) vs It Takes Two (1995) -> negligible (marginal): Both 'Toy Story' and 'It Takes Two' are fictional stories without a basis in historical events, thus both fall near the low pole of the Historical Accuracy dimension. Neither movie attempts to depict real historical events or figures.
- GoldenEye (1995) vs Now and Then (1995) -> negligible (marginal): Option A, 'GoldenEye', is an action-thriller that takes significant liberties with historical facts and timelines, focusing on fictional espionage and action sequences. Option B, 'Now and Then', while centered around a specific year, 1970, does not claim historical accuracy but rather focuses on personal narratives and coming-of-age themes.
- American President, The (1995) vs Sabrina (1995) -> A (marginal): The American President (1995) attempts to portray realistic political scenarios and processes, though it is a fictional story, making it lean towards moderate historical accuracy within its genre constraints. In contrast, Sabrina (1995) is a romantic comedy with no particular focus on historical accuracy, focusing instead on character development and romance.

Cross-variant consistency:

- Spearman rho = 0.655, Kendall tau = 0.530 (n=50)

## Dimension 6: Visual Effects

Low pole: Minimal VFX | High pole: Heavy VFX

Direct-score low examples:

- Grumpier Old Men (1995) (1): The movie relies heavily on live-action comedy and romance without significant use of visual effects.
- Waiting to Exhale (1995) (1): The plot summary and genre description indicate minimal use of visual effects, focusing instead on character development and real-life scenarios.
- Father of the Bride Part II (1995) (1): The movie 'Father of the Bride Part II' is a comedy centered around family dynamics and personal growth, with no indication of significant use of visual effects.
- Heat (1995) (1): Heat (1995) primarily focuses on character development and intense action sequences with minimal reliance on visual effects.
- Sabrina (1995) (1): The plot summary and genre of 'Sabrina' suggest minimal use of visual effects, focusing instead on character development and romance.

Direct-score high examples:

- Toy Story (1995) (5): Toy Story (1995) is a fully computer-animated film that relies heavily on CGI to bring its characters and environments to life.
- GoldenEye (1995) (3): The movie features significant action sequences and chase scenes that rely on a mix of practical effects and visual effects, leaning towards a higher use of VFX.
- Jumanji (1995) (3): The movie uses a mix of practical effects and CGI to bring the jungle and its creatures to life, leaning towards moderate use of visual effects.
- Pocahontas (1995) (2): Pocahontas is a traditionally animated film, which relies heavily on hand-drawn animation rather than computer-generated visual effects.
- Mortal Kombat (1995) (2): The movie uses practical effects and some early CGI, but the visual effects are not overwhelming.

Bradley-Terry low examples:

- Carrington (1995) (-0.91665)
- Cry, the Beloved Country (1995) (-0.629406)
- Leaving Las Vegas (1995) (-0.609599)
- Four Rooms (1995) (-0.599547)
- Sabrina (1995) (-0.580513)

Bradley-Terry high examples:

- GoldenEye (1995) (1.0)
- Jumanji (1995) (0.991417)
- Mortal Kombat (1995) (0.963968)
- Pocahontas (1995) (0.92895)
- Twelve Monkeys (a.k.a. 12 Monkeys) (1995) (0.763213)

Pairwise spot checks:

- Toy Story (1995) vs Leaving Las Vegas (1995) -> A (clear): Toy Story (1995) is a fully animated film that relies heavily on computer-generated imagery, placing it at the high pole of the visual effects spectrum. In contrast, Leaving Las Vegas (1995) is a live-action drama with minimal visual effects, aligning it closer to the low pole.
- GoldenEye (1995) vs City of Lost Children, The (Cité des enfants perdus, La) (1995) -> A (marginal): GoldenEye (1995) features several action sequences and stunts that utilize a mix of practical and digital effects, but leans more towards practical effects. The City of Lost Children, while visually striking, relies heavily on imaginative set design and makeup rather than extensive CGI.
- American President, The (1995) vs Tom and Huck (1995) -> negligible (marginal): Both 'The American President' and 'Tom and Huck' are minimal in their use of visual effects, focusing more on practical elements and real settings. However, 'The American President' might have slightly fewer visual effects due to its setting in contemporary times without the need for recreating historical scenes.

Cross-variant consistency:

- Spearman rho = 0.725, Kendall tau = 0.602 (n=50)

## Dimension 7: Character Complexity

Low pole: Simple Characters | High pole: Complex Characters

Direct-score low examples:

- Toy Story (1995) (1): Toy Story features dialogue that is primarily simple and accessible, aimed at a broad audience including children, with occasional witty remarks suitable for adults.
- Jumanji (1995) (1): The dialogue in 'Jumanji' is primarily straightforward and aimed at a younger audience, with occasional witty remarks.
- Grumpier Old Men (1995) (1): The movie features light-hearted, straightforward dialogue typical of its comedy genre, without much complexity or sophisticated language.
- Father of the Bride Part II (1995) (1): The movie features typical comedy dialogue that is accessible and straightforward without much complexity.
- Tom and Huck (1995) (1): The dialogue in 'Tom and Huck' is primarily simple and straightforward, suitable for a children's audience, though it may occasionally touch on more complex themes.

Direct-score high examples:

- Richard III (1995) (5): The movie features Shakespearean dialogue, which is known for its complexity, rich metaphors, and layered conversations.
- Othello (1995) (5): The movie is an adaptation of Shakespeare's play, which is known for its complex and sophisticated language.
- Usual Suspects, The (1995) (4): The intricate and layered conversations, especially those involving Verbal Kint, demonstrate a high level of dialogue complexity.
- Restoration (1995) (4): The movie features intricate and period-appropriate dialogue that reflects the intellectual and social complexities of the 17th century court.
- Carrington (1995) (4): The film's focus on the intellectual and emotional exchanges between characters, set within the context of early 20th-century England, suggests a dialogue rich with historical and cultural nuances.

Bradley-Terry low examples:

- Sudden Death (1995) (-1.0)
- Grumpier Old Men (1995) (-0.904948)
- Ace Ventura: When Nature Calls (1995) (-0.863398)
- Father of the Bride Part II (1995) (-0.853734)
- It Takes Two (1995) (-0.848551)

Bradley-Terry high examples:

- Casino (1995) (0.886032)
- Nixon (1995) (0.876914)
- Dead Man Walking (1995) (0.872241)
- Othello (1995) (0.786716)
- Restoration (1995) (0.755926)

Pairwise spot checks:

- Toy Story (1995) vs Casino (1995) -> B (clear): Toy Story features dialogue that is primarily aimed at a younger audience, using simple and direct language. In contrast, Casino includes complex dialogue with sophisticated language and thematic depth, characteristic of Martin Scorsese's work.
- GoldenEye (1995) vs Pocahontas (1995) -> A (marginal): Option A, 'GoldenEye', features dialogue that is primarily focused on action and espionage, with some witty exchanges typical of the Bond franchise, but it remains relatively straightforward. Option B, 'Pocahontas', includes dialogue that is simple and accessible for children, with songs that convey deeper themes through metaphor and allegory, yet the overall complexity is still lower compared to films with purely verbal sophistication.
- American President, The (1995) vs Sudden Death (1995) -> A (clear): Option A, 'The American President,' features nuanced political and romantic dialogues that are relatively complex and sophisticated. In contrast, Option B, 'Sudden Death,' is an action film with simpler, more direct dialogue focused on immediate action and survival.

Cross-variant consistency:

- Spearman rho = 0.891, Kendall tau = 0.760 (n=50)

## Dimension 8: Dialogue Quality

Low pole: Weak Dialogue | High pole: Strong Dialogue

Direct-score low examples:

- Grumpier Old Men (1995) (1): The main characters, John and Max, maintain their core personalities and rivalry throughout the film, with minimal personal growth.
- Sudden Death (1995) (1): The protagonist in 'Sudden Death' primarily relies on his existing skills and resourcefulness without undergoing significant personal growth or transformation.
- GoldenEye (1995) (1): James Bond remains largely consistent with his established traits and does not undergo significant personal growth or transformation.
- Dracula: Dead and Loving It (1995) (1): The characters in 'Dracula: Dead and Loving It' primarily serve comedic roles and do not undergo significant personal growth or transformation.
- Cutthroat Island (1995) (1): The characters in 'Cutthroat Island' primarily focus on external adventures and conflicts rather than internal growth or significant personal transformation.

Direct-score high examples:

- When Night Is Falling (1995) (4): The protagonist undergoes significant personal growth as she confronts her beliefs and fears through her relationship, indicating substantial character development.
- Pocahontas (1995) (4): Pocahontas undergoes significant personal growth, learning to stand up for her beliefs and bridge cultural divides, which aligns with high character development.
- How to Make an American Quilt (1995) (4): The film focuses on the protagonist's journey of self-discovery and growth through the wisdom and experiences shared by the older women, indicating significant character development.
- Restoration (1995) (4): Robert Merivel undergoes significant personal and moral transformations throughout the film, reflecting deep character development.
- Cry, the Beloved Country (1995) (4): The film showcases significant personal growth and transformation in the protagonist, Stephen Kumalo, as he confronts the challenges of apartheid and undergoes a profound change in his understanding and actions.

Bradley-Terry low examples:

- Ace Ventura: When Nature Calls (1995) (-1.0)
- It Takes Two (1995) (-0.988067)
- Dracula: Dead and Loving It (1995) (-0.964695)
- Across the Sea of Time (1995) (-0.942787)
- Sudden Death (1995) (-0.887343)

Bradley-Terry high examples:

- Leaving Las Vegas (1995) (0.922235)
- Usual Suspects, The (1995) (0.910014)
- Clueless (1995) (0.854127)
- Dead Man Walking (1995) (0.812775)
- Othello (1995) (0.702129)

Pairwise spot checks:

- Toy Story (1995) vs Copycat (1995) -> A (clear): Toy Story features significant character development for both Woody and Buzz, transforming them from rivals to close friends, which places it higher on the dynamic character scale. In contrast, Copycat focuses more on the plot and suspense rather than deep character transformation, though there is some development, it is less pronounced compared to Toy Story.
- GoldenEye (1995) vs American President, The (1995) -> B (clear): Option A, 'GoldenEye', focuses primarily on action and adventure, with Bond's character remaining relatively static despite the plot twists. Option B, 'The American President', delves into the personal and political growth of the main character, President Shepherd, as he navigates his evolving relationship and political challenges.
- Dracula: Dead and Loving It (1995) vs Mortal Kombat (1995) -> B (marginal): Dracula: Dead and Loving It focuses primarily on comedic elements and parody, with little emphasis on character development. Mortal Kombat, while action-oriented, does offer some character arcs and personal growth among its fighters. However, the extent of character development in Mortal Kombat is still relatively limited compared to films at the high pole.

Cross-variant consistency:

- Spearman rho = 0.434, Kendall tau = 0.326 (n=50)

## Dimension 9: Music Influence

Low pole: Background Music | High pole: Central Music

Direct-score low examples:

- Grumpier Old Men (1995) (1): The movie focuses more on the comedic and romantic elements rather than the musical score, which plays a supporting role.
- Father of the Bride Part II (1995) (1): The movie's music serves primarily as background support for the comedic scenes without heavily influencing the overall emotional tone.
- Tom and Huck (1995) (1): The plot summary does not indicate that the music plays a significant role in influencing the atmosphere or emotional tone of the film.
- Sudden Death (1995) (1): The plot summary does not indicate a significant emphasis on the musical score influencing the film's atmosphere or emotional tone.
- American President, The (1995) (1): The musical score in 'The American President' supports the scenes but does not heavily influence the overall atmosphere or emotional tone.

Direct-score high examples:

- Pocahontas (1995) (4): Pocahontas features a prominent musical score that significantly influences the emotional tone and atmosphere of the film.
- City of Lost Children, The (Cité des enfants perdus, La) (1995) (4): The musical score in 'The City of Lost Children' significantly contributes to the film's surreal and dreamlike atmosphere, enhancing the emotional depth and tone.
- Heat (1995) (4): The musical score in 'Heat' significantly enhances the tension and emotional depth of the scenes, aligning closely with the high pole.
- Richard III (1995) (3): The film uses its musical score to enhance the dramatic tension and emotional depth of the narrative, though it does not overshadow the dialogue and action.
- Clueless (1995) (3): The music in 'Clueless' is prominent and contributes significantly to the film's 90s pop culture vibe and emotional tone.

Bradley-Terry low examples:

- Sudden Death (1995) (-1.0)
- Ace Ventura: When Nature Calls (1995) (-0.729241)
- Assassins (1995) (-0.687589)
- Across the Sea of Time (1995) (-0.592981)
- Dracula: Dead and Loving It (1995) (-0.515457)

Bradley-Terry high examples:

- Casino (1995) (0.927257)
- Pocahontas (1995) (0.887037)
- Richard III (1995) (0.795326)
- City of Lost Children, The (Cité des enfants perdus, La) (1995) (0.779621)
- Dead Man Walking (1995) (0.595252)

Pairwise spot checks:

- Toy Story (1995) vs Dangerous Minds (1995) -> A (clear): Toy Story (1995) features a memorable and integral musical score that significantly enhances the emotional depth and atmosphere of the film, aligning it closer to the high pole. In contrast, Dangerous Minds (1995) uses music more conventionally, serving primarily as background support without dominating the emotional landscape.
- GoldenEye (1995) vs Waiting to Exhale (1995) -> A (marginal): Option A, 'GoldenEye', features a prominent musical score that enhances the action and suspense, though it primarily serves the plot rather than dominating the emotional landscape. Option B, 'Waiting to Exhale', uses music more subtly to complement the characters' emotions and the overall narrative without overwhelming the dialogue and acting.
- American President, The (1995) vs Richard III (1995) -> B (marginal): Option A, 'The American President', features a musical score that supports the narrative but does not dominate the emotional landscape. Option B, 'Richard III', uses a more prominent and impactful musical score to enhance the dramatic and tense atmosphere of the film.

Cross-variant consistency:

- Spearman rho = 0.657, Kendall tau = 0.538 (n=50)

## Dimension 10: Pacing Speed

Low pole: Slow Pacing | High pole: Fast Pacing

Direct-score low examples:

- Toy Story (1995) (1): Toy Story follows a straightforward, chronological plot without significant deviations from a linear storyline.
- Jumanji (1995) (1): The plot of 'Jumanji' follows a straightforward and chronological storyline without significant deviations into nonlinear storytelling.
- Grumpier Old Men (1995) (1): The plot follows a straightforward and chronological storyline without significant deviations into nonlinear storytelling techniques.
- Waiting to Exhale (1995) (1): The plot of 'Waiting to Exhale' follows a straightforward, chronological narrative without significant deviations into nonlinear storytelling techniques.
- Father of the Bride Part II (1995) (1): The plot follows a straightforward, chronological storyline without significant deviations into nonlinear storytelling techniques.

Direct-score high examples:

- Twelve Monkeys (a.k.a. 12 Monkeys) (1995) (4): The film uses a complex narrative involving time travel and multiple timelines, which significantly deviates from a straightforward plot.
- Usual Suspects, The (1995) (3): The film uses a nested narrative structure and unreliable narrator, which introduces significant non-linearity and complexity.
- City of Lost Children, The (Cité des enfants perdus, La) (1995) (3): The film uses a non-linear narrative structure with dream sequences and surreal elements, which adds complexity to its storytelling.
- Seven (a.k.a. Se7en) (1995) (2): Seven primarily follows a straightforward plot with a chronological timeline, though it includes some flashbacks and reveals that add complexity.
- Now and Then (1995) (2): The movie uses a straightforward plot with occasional flashbacks to explore the characters' past, indicating a mix of linear and non-linear storytelling.

Bradley-Terry low examples:

- How to Make an American Quilt (1995) (-0.942148)
- Pocahontas (1995) (-0.864418)
- Now and Then (1995) (-0.730482)
- Persuasion (1995) (-0.64281)
- Sense and Sensibility (1995) (-0.61322)

Bradley-Terry high examples:

- Heat (1995) (1.0)
- Usual Suspects, The (1995) (0.938615)
- Sudden Death (1995) (0.73985)
- Copycat (1995) (0.730957)
- Assassins (1995) (0.654006)

Pairwise spot checks:

- Toy Story (1995) vs Cry, the Beloved Country (1995) -> B (marginal): Toy Story follows a straightforward plot with a clear beginning, middle, and end, making it closer to the low pole. Cry, the Beloved Country also maintains a relatively linear narrative but includes some reflective moments that add a slight layer of complexity, placing it slightly higher than Toy Story on the dimension.
- GoldenEye (1995) vs Carrington (1995) -> negligible (marginal): Option A, 'GoldenEye', follows a straightforward plot with a clear chronological timeline, typical of action-thriller films. Option B, 'Carrington', while more focused on character development and relationships, still maintains a relatively linear narrative without significant non-linear storytelling elements.
- American President, The (1995) vs Grumpier Old Men (1995) -> A (marginal): Both 'The American President' and 'Grumpier Old Men' have straightforward plots that follow a chronological and linear storyline without significant deviations into nonlinear storytelling techniques. However, 'The American President' may slightly edge out due to its political subplot and romantic storyline running concurrently, adding a bit more complexity.

Cross-variant consistency:

- Spearman rho = 0.248, Kendall tau = 0.198 (n=50)
- WARNING: Low cross-variant agreement (tau = 0.20) -- this dimension may be unreliable.

