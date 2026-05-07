# Movies: pre-registration

## Hypothesis
We test a new method for making RLHF preference inferences interpretable and editable to human users. Our experiment measures whether two new preference elicitation procedures supported by our method improve a model's ability to learn human preferences.

H1: Our proposed methods improve predictive accuracy on held-out choices.
H2: Participants prefer the preference profile inferred by our method over that inferred by the baseline method.
H3: Participants more strongly endorse predictions made by our method than predictions made by the baseline method.


## Dependent variable

H1 DV: Leave-one-out (LOO) choice accuracy. Computed offline from the trial data for each of three model fits (random projection / semantic projection / semantic projection + feedback prior). The relevant contrast depends on condition: in choice-only it is (semantic projection − random projection); in the inference conditions it is (semantic projection + feedback prior − semantic projection).

H2 DV: Summary preference (6-point Likert). After the trials, participants see two side-by-side preference summaries and indicate which is more accurate on a 6-point scale. Which two summaries depends on condition: choice-only sees random-projection vs semantic-projection summaries; inference conditions see semantic-projection vs semantic-projection + feedback summaries. The Likert is signed so that positive values indicate the participant preferred the augmented summary (semantic projection in choice-only; semantic projection + feedback prior in the inference conditions).

H3 DV: Prediction endorsement (6-point Likert). After all choice trials, we show participants two held-out choice problems on which the baseline and augmented models disagree most strongly. On one trial the participant rates the baseline model's prediction; on the other they rate the augmented model's prediction. Order of which model is rated first is randomized. For each prediction, participants rate "How accurate is our prediction?" on a Not-at-all-accurate (1) to Very-accurate (6) scale. The primary H3 quantity is the within-participant paired difference (augmented rating − baseline rating). The baseline / augmented pairing is the same as for H1 and H2: random vs semantic projection in choice-only; semantic projection vs semantic projection + feedback prior in the inference conditions.

## Conditions
Three between-subjects conditions, randomly assigned via Qualtrics:
1. Choice-only: 20 binary-choice trials, no per-trial feedback.
2. Inference-affirm: 20 trials; on each, participants Affirm or Remove three algorithmic inferences about their preferences.
3. Inference-categories: 20 trials; on each, participants confirm or change a 5-category quintile assignment for three dimensions.

## Analyses

H1: Within each condition separately, paired one-sided t-test on the LOO accuracy contrast defined in the H1 DV, null = 0, alternative > 0. In choice-only this tests (semantic projection − baseline); in each inference condition this tests (feedback and/or projection minus baseline).

H2: Within each inference condition separately, one-sample Wilcoxon signed-rank test on the signed H2 Likert against 0, alternative > 0 (i.e., preference for the feedback-augmented summary over the semantic-projection summary). For completeness we additionally run a one-sample Wilcoxon in choice-only against 0, alternative > 0 (preference for the semantic projection summary over the baseline summary); this serves as a manipulation check rather than a test of H2 proper.

H3: Within each condition separately, one-sample Wilcoxon signed-rank test on the paired difference (augmented rating − baseline rating) against 0, alternative > 0.


## Outliers and Exclusions

N/A


## Sample Size

We will recruit 150 participants for each of the 3 conditions for a total of 450 participants.