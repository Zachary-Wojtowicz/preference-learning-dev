# Dilemmas: pre-registration

## Hypothesis

We test a new method for making RLHF preference inferences interpretable and editable to human users. Our experiment measures whether two new preference elicitation procedures supported by our method improve a model's ability to learn human preferences.

H1: Our proposed methods improve predictive accuracy on held-out choices
H2: Participants prefer the preference profile inferred by our method over that inferred by the baseline method
H3: Participants will more strongly endorse the predictions made by our method


## Dependent variable

H1 DV: Leave-one-out (LOO) choice accuracy. Computed offline from the trial data for each of three model fits (random projection / LLM projection / LLM projection + feedback prior).

H2 DV: Summary preference (6-point Likert). After the trials, participants see two side-by-side preference summaries and indicate which is more accurate on a 6-point scale. Which two summaries depends on condition: choice-only sees random-projection vs LLM-projection summaries; inference conditions see LLM-projection vs LLM-projection-with-feedback-prior summaries.

H3 DV: After all choice trials have been complete, we show participants the model's most confident prediction on two held-out choice problems where the baseline and our alternative disagree most strongly, one in each direction. Participants then rate "How accurate is our prediction?" on a Not-at-all-accurate (1) to Very-accurate (6) scale for each prediction.


## Conditions

Three between-subjects conditions, randomly assigned via Qualtrics:

1. Choice-only: 20 binary-choice trials, no per-trial feedback.
2. Inference-affirm: 20 trials; on each, participants Affirm or Remove three algorithmic inferences about their preferences.
3. Inference-categories: 20 trials; on each, participants confirm or change a 5-category quintile assignment for three dimensions.

## Analyses

H1: Within each condition separately, paired one-sided t-test on (LOO accuracy under LLM projection − LOO accuracy under random projection), null = 0.

H3: One-sample Wilcoxon signed-rank test on the primary Likert DV (signed so positive = participant preferred the feedback-augmented summary), within inference-affirm and inference-categories separately.

H2: Mann-Whitney U comparing the primary Likert DV between each inference condition and choice-only. Pre-registered direction: inference > choice-only.

## Outliers and Exclusions

N/A

## Sample Size

We will recruit 150 participants for each of the 3 conditions for a total of 450 participants

## Other
