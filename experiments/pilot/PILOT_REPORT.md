# Pilot Analysis Report

Source: `experiments/pilot/data.csv`
N rows in CSV (post-header): **30**

## 1. Validation — does the data look healthy?

### Completion + parsing

- Finished (Qualtrics flag): **30/30**
- Progress = 100: **30/30**
- experiment_data parsed OK: **30/30** (failures: 0)
- Mean duration: **1106 s**  (median 1041, range 357–3117)
- Suspiciously fast (<60s): **0** · long (>25 min): **7**

### Cell counts

| Condition | N | N w/ eval | N w/ prediction |
|---|---|---|---|
| inference_categories | 30 | 30 | 30 |

### Practice-trial accuracy (sanity check)

Practice trials show one preference dimension's framing and ask the participant to identify the option scoring higher on it. Accuracy should be well above chance — if not, either the participant didn't engage or the dimension labels don't actually match what the embedding picks up.

| Condition | N | Mean acc | SD | Above 0.5 (one-sided p) |
|---|---|---|---|---|
| inference_categories | 30 | 0.82 | 0.17 | p=0.0000 |
| **overall** | **30** | **0.82** | **0.17** | **p=0.0000** |

### Feedback engagement (inference conditions only)

Across all trial × visible-dim cells, what fraction did the participant *not* leave at the model's default? Low rates suggest the participant is rubber-stamping; very high rates may mean the model's defaults are bad.

| Condition | N | action_rate | affirm | modify | remove |
|---|---|---|---|---|---|
| inference_categories | 30 | 0.15 | 0.00 | 0.15 | 0.00 |

### Timing breakdown

| Condition | mean choice RT (s) | mean feedback panel RT (s) |
|---|---|---|
| inference_categories | 24.9 | 11.8 |

## 2. Planned full-study analysis (dry-run on pilot N)

### Primary DV 1 — Evaluation rating

Each participant compares two summaries side-by-side and rates which is better on a 6-point Likert. We sign the rating in favor of the *target* model: partial-with-feedback for inference conditions, the real fitted model for choice_only (which compares real vs. random as a manipulation check).

| Condition | n | mean DV | SD | one-sample t vs 0 (two-sided) | Wilcoxon vs 0 | Cohen's d |
|---|---|---|---|---|---|---|
| inference_categories | 30 | -0.40 | 1.74 | t=-1.24, p=0.227 | p=0.227 | d=-0.23 [-0.67, +0.13] |

Pairwise (between-condition):

| Comparison | mean Δ | Welch t | p | Cohen's d_s |
|---|---|---|---|---|

### Primary DV 2 — Prediction-check accuracy rating

Participant rates the model's predicted choice on a real held-out trial pair: 1 = very inaccurate, 6 = very accurate. Above 3.5 ⇒ prediction is judged net accurate.

| Condition | n | mean | SD | t vs 3.5 | p | Cohen's d |
|---|---|---|---|---|---|---|
| inference_categories | 30 | 5.43 | 1.12 | t=+9.33 | p=0.000 | d=+1.70 |

### Secondary — feedback engagement vs DV (correlations)

Hypothesis: participants who engaged more with the inference UI got more accurate summaries, so we should see action_rate ↔ eval_dv > 0 in the inference conditions.

| Condition | n | r(action_rate, eval_dv) | p | r(action_rate, pred_dv) | p |
|---|---|---|---|---|---|
| inference_categories | 30 | +0.03 | 0.891 | -0.02 | 0.930 |

## 3. Power analysis for the full study

Using the pilot's effect-size estimates, what per-cell N do we need to achieve 80% power at α=0.05 (two-sided)? These are rough — the pilot's small N gives noisy d estimates with wide bootstrap CIs.

### One-sample tests (DV vs null)

| Test | observed d | 95% CI (boot) | N needed (point) | N needed (lower CI) |
|---|---|---|---|---|
| inference_categories eval_dv vs 0 | -0.23 | [-0.67, +0.13] | 155 | 464 |
| inference_categories pred_dv vs 3.5 | +1.70 | [+0.99, +3.99] | 3 | 8 |

### Two-sample tests (between conditions, eval_dv)

| Comparison | observed Δ | pooled SD | d_s | Per-cell N needed |
|---|---|---|---|---|

### Recommendation

- **Choose the largest N** across the comparisons you actually plan to report as primary. Inference-condition vs. choice_only is usually the strictest test and should drive the recruitment target.
- Inflate by 15–20% for attention-check / completion attrition.
- The bootstrap CIs are wide at this N — treat point estimates as lower-bound optimism. The CI-lower-bound column gives a more conservative anchor.

## 4. Data-completeness checklist for the full study

Each row in this checklist should be 100% green before launching the main study. If anything is missing now, fix the data export *first*.

| Field | non-null / total |
|---|---|
| Qualtrics ResponseId | 30/30 |
| PROLIFIC_PID for ID match | 30/30 |
| Condition assignment | 30/30 |
| Domain label | 30/30 |
| Total survey duration | 30/30 |
| Practice-trial accuracy | 30/30 |
| Feedback-trial RTs | 30/30 |
| Feedback engagement (inference) | 30/30 |
| Evaluation DV (signed) | 30/30 |
| Prediction-check DV | 30/30 |

## Plots

- `eval_dv_by_condition.png` — boxplot + jitter of the evaluation DV.
- `pred_dv_by_condition.png` — boxplot + jitter of the prediction-check DV.
- `per_participant.csv` — flat per-participant feature table (use this as the input for any further analysis you write).
