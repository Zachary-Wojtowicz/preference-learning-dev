# Direction Vectors: Evaluation Summary

## Overall Statistics

- Options: 200
- Dimensions: 25
- Embedding dimensionality: 4096
- Average held-out R²: -1.0135
- Average held-out Pearson r: 0.4605
- Average held-out Spearman ρ: 0.4617

## ⚠ Unreliable Dimensions

- **Autonomy** (dim 1): R²_heldout=0.024 < 0.1
- **Conflict Avoidance** (dim 5): R²_heldout=-0.112 < 0.1
- **Ethical Responsibility** (dim 20): R²_heldout=-0.224 < 0.1
- **Financial Stability** (dim 21): R²_heldout=0.012 < 0.1
- **Tradition** (dim 23): R²_heldout=-0.133 < 0.1
- **Digital Autonomy** (dim 25): cosine(ridge, contrastive)=0.402 < 0.5; R²_heldout=-29.677 < 0.1

## Per-Dimension Metrics

| Dim | Name | alpha | R²_in | R²_cv | R²_held | Pearson | Spearman | cos(ridge,contrast) | cos(pre,post_orth) |
|-----|------|-------|-------|-------|---------|---------|----------|---------------------|-------------------|
| 1 | Autonomy | 1 | 0.639 | 0.803 | 0.024 | 0.335 | 0.244 | 0.772 | 1.000 |
| 2 | Emotional Honesty | 0.1 | 0.969 | 0.881 | 0.214 | 0.682 | 0.710 | 0.614 | 0.968 |
| 3 | Social Connection | 1 | 0.684 | 0.761 | 0.316 | 0.573 | 0.686 | 0.776 | 0.952 |
| 4 | Spontaneity | 1 | 0.651 | 0.788 | 0.199 | 0.594 | 0.422 | 0.743 | 0.963 |
| 5 | Conflict Avoidance | 1 | 0.650 | 0.731 | -0.112 | 0.280 | 0.151 | 0.814 | 0.935 |
| 6 | Creativity | 1 | 0.627 | 0.649 | 0.166 | 0.476 | 0.479 | 0.692 | 0.930 |
| 7 | Efficiency | 1 | 0.724 | 0.826 | 0.319 | 0.596 | 0.574 | 0.827 | 0.924 |
| 8 | Humor | 0.1 | 0.971 | 0.857 | 0.214 | 0.595 | 0.678 | 0.547 | 0.843 |
| 9 | Emotional Catharsis | 1 | 0.652 | 0.756 | 0.159 | 0.402 | 0.595 | 0.677 | 0.730 |
| 10 | Moral Boundaries | 1 | 0.657 | 0.753 | 0.237 | 0.565 | 0.515 | 0.805 | 0.878 |
| 11 | Intellectual Engagement | 0.1 | 0.971 | 0.761 | 0.344 | 0.608 | 0.620 | 0.612 | 0.919 |
| 12 | Comfort | 1 | 0.717 | 0.756 | 0.289 | 0.582 | 0.559 | 0.827 | 0.704 |
| 13 | Social Recognition | 0.1 | 0.972 | 0.857 | 0.234 | 0.534 | 0.562 | 0.595 | 0.921 |
| 14 | Cultural Awareness | 0.1 | 0.972 | 0.823 | 0.344 | 0.612 | 0.250 | 0.597 | 0.924 |
| 15 | Identity Exploration | 1 | 0.697 | 0.743 | 0.246 | 0.516 | 0.636 | 0.730 | 0.764 |
| 16 | Direct Communication | 0.1 | 0.973 | 0.836 | 0.351 | 0.594 | 0.598 | 0.658 | 0.689 |
| 17 | Emotional Restraint | 1 | 0.656 | 0.712 | 0.209 | 0.521 | 0.585 | 0.852 | 0.695 |
| 18 | Social Obligation Avoidance | 1 | 0.680 | 0.812 | 0.186 | 0.525 | 0.598 | 0.746 | 0.723 |
| 19 | Digital Convenience | 0.1 | 0.975 | 0.817 | 0.271 | 0.565 | 0.229 | 0.598 | 0.909 |
| 20 | Ethical Responsibility | 1 | 0.605 | 0.666 | -0.224 | 0.178 | 0.206 | 0.860 | 0.687 |
| 21 | Financial Stability | 1 | 0.594 | 0.600 | 0.012 | 0.449 | 0.380 | 0.608 | 0.953 |
| 22 | Personal Growth | 0.1 | 0.969 | 0.836 | 0.306 | 0.560 | 0.616 | 0.567 | 0.697 |
| 23 | Tradition | 1 | 0.613 | 0.673 | -0.133 | 0.137 | 0.206 | 0.725 | 0.895 |
| 24 | Institutional Efficiency | 1 | 0.641 | 0.663 | 0.168 | 0.412 | 0.528 | 0.690 | 0.783 |
| 25 | Digital Autonomy | 1 | 0.567 | 0.289 | -29.677 | -0.375 | -0.082 | 0.402 | 0.844 |

## Top/Bottom Options Per Dimension (by Predicted Score)

### Autonomy (dim 1)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| changing my name legally? I hate my name | 0.4234 | 1.0000 |
| leaving the guild | 0.3696 | 0.9685 |
| wanting to split up with my so because my physical attractio | 0.3556 | 0.6552 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| encouraging people to report people who frequently make "dar | -0.1839 | -0.2194 |
| drinking if my bf gets anxious | -0.1811 | -0.3342 |
| scolding scooter riders on the wwii memorial | -0.1623 | -0.1405 |

### Emotional Honesty (dim 2)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| wanting to split up with my so because my physical attractio | 0.8746 | 1.0000 |
| telling a clingy, "humble" narcissist that I want to be left | 0.6952 | 0.8196 |
| pointing out someone's potential racism | 0.6915 | 0.8170 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| only using tinder for validation | -0.1868 | -0.2325 |
| not fixing problems she stopped acknowledging | -0.1791 | -0.2609 |
| dosing food with LSD and keeping it in my room that my frien | -0.1693 | -0.1763 |

### Social Connection (dim 3)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| wanting to pursue a girl that roommate wants? Context girl w | 0.4981 | 0.8705 |
| making plans on the weekend I said my friend and I would fin | 0.4112 | 0.7662 |
| asking my wife if nearly 2 years how to get her to like livi | 0.3862 | 0.9993 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| not wanting governments to support curing of diseases such a | -0.2462 | -0.2200 |
| threatening legal actions for unfinished work | -0.2186 | -0.2003 |
| refusing to pay for the cremation of an animal I accidentall | -0.2112 | -0.2009 |

### Spontaneity (dim 4)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| making an inappropriate joke in Build-a-bear? think girl I w | 0.4409 | 1.0000 |
| calling out a couple who are displaying EXPLICIT PDA? I'm tr | 0.3813 | 0.8356 |
| dosing food with LSD and keeping it in my room that my frien | 0.2177 | 0.4713 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| not ever wanting kids not just because of how stressful the  | -0.1519 | -0.1232 |
| filing a complaint against a state government employee with  | -0.1388 | -0.2453 |
| expecting a level of competency from my town leaders and adm | -0.1387 | -0.1295 |

### Conflict Avoidance (dim 5)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| not going to breakfast with my girlfriends roommates after w | 0.3880 | 1.0000 |
| going out to lunch with an old acquaintance and using a gift | 0.3345 | 0.5845 |
| keeping being invited out to dinner with a guest speaker fro | 0.3107 | 0.5846 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| telling a railway worker to "have a fucking shit day" | -0.2362 | -0.3760 |
| saying recruitment policy at my company is sexist against me | -0.2200 | -0.3283 |
| calling out an indie game developer for going on vacation wh | -0.2154 | -0.3499 |

### Creativity (dim 6)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| dosing food with LSD and keeping it in my room that my frien | 0.4167 | 1.0000 |
| making a meme page about my teacher who's husband died a few | 0.3869 | 0.9914 |
| making a pun about the country Chili to someone who was from | 0.3449 | 0.7729 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| asking if there are extra tickets | -0.1235 | -0.0778 |
| not fixing problems she stopped acknowledging | -0.1053 | -0.0824 |
| not liking my bf's friends? a few weeks ago I was meeting my | -0.1003 | -0.0634 |

### Efficiency (dim 7)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| using BCC emails | 0.5224 | 0.9031 |
| changing the passwords to my streaming services | 0.5018 | 1.0000 |
| microwaving a ham sandwich | 0.4845 | 0.9099 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| being wary of my boyfriend who still seems pretty hurt about | -0.3416 | -0.2965 |
| finding my Father's biological family through dna against hi | -0.3156 | -0.4434 |
| dating a man 28 years older than me? my parents are coming a | -0.3155 | -0.3560 |

### Humor (dim 8)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| giving people at my school beanboozled jelly beans | 0.8555 | 1.0000 |
| making a pun about the country Chili to someone who was from | 0.8364 | 0.9309 |
| making an inappropriate joke in Build-a-bear? think girl I w | 0.7494 | 0.8201 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| threatening legal actions for unfinished work | -0.2352 | -0.2069 |
| filing a complaint against a state government employee with  | -0.2063 | -0.1992 |
| finding my Father's biological family through dna against hi | -0.1988 | -0.1552 |

### Emotional Catharsis (dim 9)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| screaming at my little brother in the middle of a restaurant | 0.4463 | 0.9881 |
| telling my girlfriend to listen to Freebird when I broke up  | 0.4084 | 1.0000 |
| calling out a couple who are displaying EXPLICIT PDA? I'm tr | 0.3960 | 0.8114 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| not seeing a fuchsia coat as a pink coat | -0.1357 | -0.1058 |
| indirectly profiting off the venezuelan crisis | -0.1344 | -0.1015 |
| taking a girl's laundry out of the washer | -0.1335 | -0.1048 |

### Moral Boundaries (dim 10)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| declining and saying it's offensive to be asked by the bride | 0.4585 | 0.8109 |
| saying recruitment policy at my company is sexist against me | 0.4320 | 1.0000 |
| encouraging people to report people who frequently make "dar | 0.4140 | 0.9896 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| jot going to work 2x when yesterday was -50 and today is -25 | -0.2027 | -0.1327 |
| microwaving a ham sandwich | -0.1947 | -0.1449 |
| using a group text | -0.1780 | -0.1427 |

### Intellectual Engagement (dim 11)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| trying to collect data for a scientific experiment | 0.8234 | 1.0000 |
| using the placebo effect as an analogy for hypno-therapy | 0.8062 | 0.9611 |
| questioning the mods of Legal Advice why they would lock an  | 0.7823 | 0.9621 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| not including my friend's rabbit on a bingo card | -0.2223 | -0.1879 |
| microwaving a ham sandwich | -0.2212 | -0.2533 |
| pulling my daughters ear after she pulled the dogs | -0.2107 | -0.2109 |

### Comfort (dim 12)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| asking if there are extra tickets | 0.4738 | 0.5519 |
| getting free japanese tutoring | 0.4537 | 0.8225 |
| almost always sampling every frozen yogurt flavor when I go  | 0.4263 | 0.8610 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| making money from an app talking to guys (non sexual) & havi | -0.6258 | -0.9822 |
| singling out, embarrassing, and causing a coworker to become | -0.5743 | -0.8035 |
| unknowingly pressuring my gf to have sex because I felt pres | -0.4714 | -0.7301 |

### Social Recognition (dim 13)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| posting our messages on Instagram | 0.8985 | 1.0000 |
| calling out a couple who are displaying EXPLICIT PDA? I'm tr | 0.8060 | 0.9283 |
| seeing a video of this guy video taping himself giving sandw | 0.7331 | 0.8665 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| wanting to know when the medication for my sick kitten will  | -0.2178 | -0.1628 |
| not ever wanting kids not just because of how stressful the  | -0.2062 | -0.1960 |
| not disclosing I get cold sores | -0.1979 | -0.1878 |

### Cultural Awareness (dim 14)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| offering costumes to my neighbour for World Book Day after s | 0.8199 | 1.0000 |
| pointing out a menorah to a jewish girl while we were going  | 0.7883 | 0.8933 |
| pointing out someone's potential racism | 0.7843 | 0.8940 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| threatening legal actions for unfinished work | -0.0911 | -0.0704 |
| thinking that it's utterly disgusting to openly fart all the | -0.0891 | -0.0574 |
| wishing that all people who get behind the wheel or under th | -0.0845 | -0.0647 |

### Identity Exploration (dim 15)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| finding my Father's biological family through dna against hi | 0.4718 | 1.0000 |
| dating a man 28 years older than me? my parents are coming a | 0.4537 | 0.7319 |
| lying to my now-husband about being pregnant? it's five year | 0.4501 | 0.7876 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| buying an electronic noisy toy for a 2nd birthday party gift | -0.2046 | -0.1335 |
| scolding scooter riders on the wwii memorial | -0.1900 | -0.1355 |
| jumping 3 people in line at the petrol station | -0.1737 | -0.1323 |

### Direct Communication (dim 16)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| calling out an indie game developer for going on vacation wh | 0.8535 | 1.0000 |
| saying recruitment policy at my company is sexist against me | 0.7909 | 0.9141 |
| letting my friend's girlfriend know that the iq test she too | 0.7864 | 0.8921 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| finding my Father's biological family through dna against hi | -0.4190 | -0.5244 |
| lying to my now-husband about being pregnant? it's five year | -0.3406 | -0.3634 |
| jot going to work 2x when yesterday was -50 and today is -25 | -0.3124 | -0.3488 |

### Emotional Restraint (dim 17)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| not fixing problems she stopped acknowledging | 0.4189 | 0.9203 |
| filing a complaint against a state government employee with  | 0.4029 | 0.9709 |
| shutdowning a potential client for 1 response | 0.3809 | 0.6807 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| calling out a couple who are displaying EXPLICIT PDA? I'm tr | -0.4084 | -0.7865 |
| feeling happy when other women flirt with me? I have a girlf | -0.3994 | -0.7072 |
| cheering the road team at my local hockey team's arena | -0.3926 | -0.6616 |

### Social Obligation Avoidance (dim 18)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| not ever wanting kids not just because of how stressful the  | 0.4478 | 1.0000 |
| ending a friendship of 8 years by deleting her number and qu | 0.4355 | 0.7820 |
| not going to breakfast with my girlfriends roommates after w | 0.3806 | 0.8049 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| still admiring Kevin Spacey's previous performances in his m | -0.2287 | -0.1865 |
| practicing Piano in metro | -0.2205 | -0.1403 |
| buying an electronic noisy toy for a 2nd birthday party gift | -0.2125 | -0.2239 |

### Digital Convenience (dim 19)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| using a group text | 0.8621 | 1.0000 |
| paying with Paypal | 0.8565 | 0.9916 |
| adding a friend on Snapchat and Instagram and my gf is jealo | 0.8028 | 0.9862 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| convincing a homeless man in Baltimore to move to Florida | -0.1117 | -0.0870 |
| not fixing problems she stopped acknowledging | -0.1074 | -0.0828 |
| being wary of my boyfriend who still seems pretty hurt about | -0.0999 | -0.0876 |

### Ethical Responsibility (dim 20)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| wanting to tell my 5 year old about same sex relationships | 0.4038 | 0.8025 |
| quitting my job as a women's track&field coach because of fa | 0.3833 | 0.9462 |
| saying recruitment policy at my company is sexist against me | 0.3715 | 0.8201 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| looking into my friend's skype account | -0.3639 | -0.7357 |
| indirectly profiting off the venezuelan crisis | -0.3234 | -0.7147 |
| dosing food with LSD and keeping it in my room that my frien | -0.3181 | -0.6801 |

### Financial Stability (dim 21)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| claiming my friend as a dependent and using the return for b | 0.3946 | 1.0000 |
| asking for a refund for shoes I bought from my regular store | 0.3820 | 0.8190 |
| wanting to go cheap on fixing my shared fence | 0.2666 | 0.6097 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| recommending a friend to invest in Bitcoin, only for it to d | -0.1500 | -0.6713 |
| dosing food with LSD and keeping it in my room that my frien | -0.0886 | -0.1389 |
| not liking my bf's friends? a few weeks ago I was meeting my | -0.0773 | -0.0236 |

### Personal Growth (dim 22)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| getting free japanese tutoring | 0.8241 | 1.0000 |
| wanting to leave our 8 year old with my parents for 2 hrs to | 0.7752 | 0.9121 |
| asking for GF's determination to come to the gym before offe | 0.7317 | 0.8875 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| not fixing problems she stopped acknowledging | -0.2258 | -0.2414 |
| writing 'TRUMP 2024' on our car as an April Fool's joke | -0.2018 | -0.1635 |
| only using tinder for validation | -0.2016 | -0.2362 |

### Tradition (dim 23)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| planning Easter activities with my kid close to a family mem | 0.4122 | 1.0000 |
| asking a indian guy if he compares himself to Ghandi | 0.3462 | 0.8386 |
| scolding scooter riders on the wwii memorial | 0.3219 | 0.7918 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| making money from an app talking to guys (non sexual) & havi | -0.1118 | -0.0896 |
| ending a friendship of 8 years by deleting her number and qu | -0.1064 | -0.1367 |
| only using tinder for validation | -0.0995 | -0.1242 |

### Institutional Efficiency (dim 24)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| claiming my friend as a dependent and using the return for b | 0.4457 | 0.9746 |
| filing a complaint against a state government employee with  | 0.4439 | 0.7853 |
| using my medical power of attorney over my mentally ill moth | 0.4400 | 1.0000 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| thinking was cool to visit a low diversity place where I ble | -0.1439 | -0.1009 |
| not liking my bf's friends? a few weeks ago I was meeting my | -0.1350 | -0.0950 |
| being wary of my boyfriend who still seems pretty hurt about | -0.1297 | -0.1195 |

### Digital Autonomy (dim 25)

**Top 3 (highest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| using BCC emails | 0.3743 | 1.0000 |
| changing the passwords to my streaming services | 0.3491 | 0.9929 |
| asking to turn AirDrop off | 0.1744 | 0.4095 |

**Bottom 3 (lowest predicted score):**

| Option | Predicted | Actual BTL |
|--------|-----------|------------|
| saying to my work colleague she looks older than what she cl | -0.0424 | -0.0145 |
| asking lots of questions during class | -0.0419 | -0.0142 |
| expecting my fiancé to wear a wedding ring when we get marri | -0.0402 | -0.0159 |
