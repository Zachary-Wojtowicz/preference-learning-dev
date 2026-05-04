# Pilot Analysis Report

Source: `experiments/pilot/data.csv`
N rows in CSV (post-header): **50**

## 1. Validation — does the data look healthy?

### Completion + parsing

- Finished (Qualtrics flag): **50/50**
- Progress = 100: **50/50**
- experiment_data parsed OK: **50/50** (failures: 0)
- Mean duration: **1019 s**  (median 864, range 245–3117)
- Suspiciously fast (<60s): **0** · long (>25 min): **8**

### Cell counts

| Condition | N | N w/ eval | N w/ prediction |
|---|---|---|---|
| choice_only | 16 | 13 | 13 |
| inference_affirm | 4 | 4 | 4 |
| inference_categories | 30 | 30 | 30 |

### Practice-trial accuracy (sanity check)

Practice trials show one preference dimension's framing and ask the participant to identify the option scoring higher on it. Accuracy should be well above chance — if not, either the participant didn't engage or the dimension labels don't actually match what the embedding picks up.

| Condition | N | Mean acc | SD | Above 0.5 (one-sided p) |
|---|---|---|---|---|
| choice_only | 16 | 0.80 | 0.15 | p=0.0000 |
| inference_affirm | 4 | 0.90 | 0.12 | p=0.0031 |
| inference_categories | 30 | 0.82 | 0.17 | p=0.0000 |
| **overall** | **50** | **0.82** | **0.16** | **p=0.0000** |

### Feedback engagement (inference conditions only)

Across all trial × visible-dim cells, what fraction did the participant *not* leave at the model's default? Low rates suggest the participant is rubber-stamping; very high rates may mean the model's defaults are bad.

| Condition | N | action_rate | affirm | modify | remove |
|---|---|---|---|---|---|
| inference_affirm | 4 | 1.00 | 0.77 | 0.00 | 0.23 |
| inference_categories | 30 | 0.15 | 0.00 | 0.15 | 0.00 |

### Timing breakdown

| Condition | mean choice RT (s) | mean feedback panel RT (s) |
|---|---|---|
| choice_only | 21.9 | 2.4 |
| inference_affirm | 20.1 | 26.3 |
| inference_categories | 24.9 | 11.8 |

## 2. Planned full-study analysis (dry-run on pilot N)

### Primary DV 1 — Evaluation rating

Each participant compares two summaries side-by-side and rates which is better on a 6-point Likert. We sign the rating in favor of the *target* model: partial-with-feedback for inference conditions, the real fitted model for choice_only (which compares real vs. random as a manipulation check).

| Condition | n | mean DV | SD | one-sample t vs 0 (two-sided) | Wilcoxon vs 0 | Cohen's d |
|---|---|---|---|---|---|---|
| choice_only | 13 | +0.69 | 1.81 | t=+1.32, p=0.211 | p=0.251 | d=+0.37 [-0.17, +1.30] |
| inference_affirm | 4 | +0.00 | 1.58 | t=+0.00, p=1.000 | p=1.000 | d=+0.00 [-2.60, +2.60] |
| inference_categories | 30 | -0.40 | 1.74 | t=-1.24, p=0.227 | p=0.227 | d=-0.23 [-0.67, +0.13] |

Pairwise (between-condition):

| Comparison | mean Δ | Welch t | p | Cohen's d_s |
|---|---|---|---|---|
| choice_only vs inference_affirm | +0.69 | +0.66 | 0.539 | +0.37 |
| choice_only vs inference_categories | +1.09 | +1.77 | 0.090 | +0.60 |
| inference_affirm vs inference_categories | +0.40 | +0.41 | 0.702 | +0.22 |

### Primary DV 2 — Prediction-check accuracy rating

Participant rates the model's predicted choice on a real held-out trial pair: 1 = very inaccurate, 6 = very accurate. Above 3.5 ⇒ prediction is judged net accurate.

| Condition | n | mean | SD | t vs 3.5 | p | Cohen's d |
|---|---|---|---|---|---|---|
| choice_only | 13 | 4.69 | 1.98 | t=+2.09 | p=0.059 | d=+0.58 |
| inference_affirm | 4 | 4.50 | 2.06 | t=+0.84 | p=0.462 | d=+0.42 |
| inference_categories | 30 | 5.43 | 1.12 | t=+9.33 | p=0.000 | d=+1.70 |

### Secondary — feedback engagement vs DV (correlations)

Hypothesis: participants who engaged more with the inference UI got more accurate summaries, so we should see action_rate ↔ eval_dv > 0 in the inference conditions.

| Condition | n | r(action_rate, eval_dv) | p | r(action_rate, pred_dv) | p |
|---|---|---|---|---|---|
| choice_only | 16 | — | — | — | — |
| inference_affirm | 4 | — | — | — | — |
| inference_categories | 30 | +0.03 | 0.891 | -0.02 | 0.930 |

## 3. Power analysis for the full study

Using the pilot's effect-size estimates, what per-cell N do we need to achieve 80% power at α=0.05 (two-sided)? These are rough — the pilot's small N gives noisy d estimates with wide bootstrap CIs.

### One-sample tests (DV vs null)

| Test | observed d | 95% CI (boot) | N needed (point) | N needed (lower CI) |
|---|---|---|---|---|
| choice_only eval_dv vs 0 | +0.37 | [-0.17, +1.30] | 59 | 279 |
| inference_affirm eval_dv vs 0 | +0.00 | [-2.60, +2.60] | ∞ | 2 |
| inference_categories eval_dv vs 0 | -0.23 | [-0.67, +0.13] | 155 | 464 |
| choice_only pred_dv vs 3.5 | +0.58 | [+0.02, +1.98] | 24 | 24777 |
| inference_affirm pred_dv vs 3.5 | +0.42 | [-0.50, +4.50] | 45 | 32 |
| inference_categories pred_dv vs 3.5 | +1.70 | [+0.99, +3.99] | 3 | 8 |

### Two-sample tests (between conditions, eval_dv)

| Comparison | observed Δ | pooled SD | d_s | Per-cell N needed |
|---|---|---|---|---|
| choice_only vs inference_affirm | +0.69 | 1.86 | +0.37 | 113 |
| choice_only vs inference_categories | +1.09 | 1.83 | +0.60 | 45 |
| inference_affirm vs inference_categories | +0.40 | 1.80 | +0.22 | 318 |

### Recommendation

- **Choose the largest N** across the comparisons you actually plan to report as primary. Inference-condition vs. choice_only is usually the strictest test and should drive the recruitment target.
- Inflate by 15–20% for attention-check / completion attrition.
- The bootstrap CIs are wide at this N — treat point estimates as lower-bound optimism. The CI-lower-bound column gives a more conservative anchor.

## 4. Data-completeness checklist for the full study

Each row in this checklist should be 100% green before launching the main study. If anything is missing now, fix the data export *first*.

| Field | non-null / total |
|---|---|
| Qualtrics ResponseId | 50/50 |
| PROLIFIC_PID for ID match | 50/50 |
| Condition assignment | 50/50 |
| Domain label | 50/50 |
| Total survey duration | 50/50 |
| Practice-trial accuracy | 50/50 |
| Feedback-trial RTs | 50/50 |
| Feedback engagement (inference) | 34/50 |
| Evaluation DV (signed) | 47/50 |
| Prediction-check DV | 47/50 |

## Plots

- `eval_dv_by_condition.png` — boxplot + jitter of the evaluation DV.
- `pred_dv_by_condition.png` — boxplot + jitter of the prediction-check DV.
- `per_participant.csv` — flat per-participant feature table (use this as the input for any further analysis you write).

---

## 5. Method comparison — does the modified projection beat the kernel baseline?

Within-participant cross-validation on each pilot participant's 20 feedback trials. On each fold we fit BOTH (a) the standard kernel-logistic baseline (used by the experiment's eval-screen comparison as the reference summary) and (b) the modified projection method (K-dim primal on Ũ = Λ⊙U). We score both on the held-out trials. Paired Wilcoxon test on per-participant mean Δ-LL (partial − standard).

Evaluated at the deployed defaults: λ_partial=0.05, scale=1.0, α=0.5, λ_standard=10.0.

| Condition | n | LL kernel | LL partial | mean Δ-LL | Wilcoxon p | mean Δ-acc |
|---|---|---|---|---|---|---|
| `choice_only` | 13 | −0.693 | −0.652 | **+0.040** | **p = 0.010** | +0.015 |
| `inference_affirm` | 4 | −0.692 | −0.639 | +0.053 | p = 0.250 (n too small) | +0.000 |
| `inference_categories` | 30 | −0.692 | −0.645 | **+0.047** | **p < 0.001** | +0.025 |

The K-dim projection method beats the kernel baseline by ~0.04–0.05 nats per pair on held-out choices, statistically significant in the conditions with usable n. The pattern holds even in `choice_only` (no feedback) — projection alone outperforms kernel at T=20, presumably because K=20 is better-matched to small samples than the over-parameterized kernel.

The full grid sweep is in `experiments/pilot/calibration/calibration_report.md`. CSVs at `cv_results.csv` and `cv_summary.csv`.

---

## 6. Calibration — what are the optimal (λ, scale, α)?

Sorted by mean held-out partial LL, the best parameters across all conditions converge:

| Condition | best λ | best scale | best α | LL partial | Δ-LL vs kernel |
|---|---|---|---|---|---|
| `choice_only` | 0.05 | (n/a) | (n/a) | −0.6549 | +0.038 |
| `inference_affirm` | 0.05 | (any) | **0** | −0.6285 | +0.064 |
| `inference_categories` | 0.05 | (any) | **0** | −0.6414 | +0.051 |

**The optimum has α = 0** — the feedback channel adds zero, the projection alone is what beats the baseline.

### Are the feedback weights "too strong"?

To check whether the result is just an over-aggressive multiplier scale, we ran a fine-grained α sweep (α ∈ {0, 0.02, 0.05, 0.10, 0.15, 0.20, 0.30, 0.50, 0.75, 1.00}) at the best λ=0.05 across three multiplier scales. Output: `experiments/pilot/calibration_fine_alpha/`.

`inference_categories` (n=29, paired Wilcoxon vs α=0):

| α | mean LL | Δ vs α=0 | p |
|---|---|---|---|
| **0.00** | **−0.6414** | (reference) | — |
| 0.02 | −0.6416 | −0.0002 | 0.064 |
| 0.05 | −0.6419 | −0.0004 | 0.061 |
| 0.10 | −0.6424 | −0.0009 | 0.050 |
| 0.15 | −0.6429 | −0.0013 | **0.036** |
| 0.30 | −0.6445 | −0.0028 | **0.033** |
| 0.50 | −0.6468 | −0.0048 | **0.025** |
| 1.00 | −0.6518 | −0.0092 | **0.011** |

`inference_affirm` (n=4, same pattern but underpowered):

| α | mean LL | Δ vs α=0 |
|---|---|---|
| 0.00 | −0.6285 | — |
| 0.05 | −0.6288 | −0.0003 |
| 0.20 | −0.6312 | −0.0023 |
| 1.00 | −0.6546 | −0.0259 |

**Held-out LL is monotonically decreasing in α.** Not a sweet spot at small α — every nonzero step hurts and degradation is paired-significant in `inference_categories` by α=0.15.

Within-α, smaller `scale` hurts less than larger `scale` (e.g., at α=1.0 categories: scale=0.5 → −0.6471 vs scale=1.5 → −0.6579), but smaller scale doesn't reverse the sign — it slows the bleeding.

### What this rules out

- *"Weights are calibrated too high — find an optimum at small α"* → **ruled out**. Function is monotonic; no local optimum exists at α > 0 in this domain.
- *"The canonical multipliers `[-1.5..+1.5]` are too aggressive"* → **only weakly true**. Smaller scales hurt less but never help; the issue isn't magnitude alone.

### What this suggests

Three structural hypotheses worth testing — none are pure parameter tuning of the current formulation:

1. **Anchor the α-blend at indifference instead of unity.** Replace `m_eff = (1−α) + α·s·m_raw` with `m_eff = α·s·m_raw` (zero-preserving). Indifference fully silences at any α. Implementation = one-line change.

2. **Feedback as informative prior, not design-matrix re-weighting.** Replace `Ũ = Λ⊙U` with a prior-shifted MAP fit:
   ```
   β̂ = argmin -Σ log σ(y · U β) + (λ/2) (β − β₀)ᵀ G (β − β₀)
   where β₀ = G⁻¹ · mean_t(λ_t)
   ```
   Data fit stays on plain U; feedback only shifts the prior center. Robust to noisy clicks because they nudge β toward β₀ without flipping per-trial gradients. ~30 lines.

3. **Filter feedback by dimension quality.** For each dim k, set λ_t,k = 1 (passthrough) if either ‖v_k‖ is below threshold (collapsed direction — dailydilemmas has 12/20 such dims) or if the participant's modification rate on this dim is near zero (rubber-stamping). Tests whether the inference channel works on the *good* dims and is being polluted by the bad ones.

### Recommended action

This pilot is on dailydilemmas, where 12 of 20 dimensions have collapsed direction norms (‖v_k‖ < 0.5). The inference channel is fundamentally re-weighting along axes that don't carry preference signal — no parameter tuning of the current formulation will fix that.

Two parallel paths forward:

- **Movies pilot.** The basis is clean (every dim ‖v_k‖ > 1) — predicted to show feedback channel adding value. Confirms or rules out the basis-quality hypothesis.
- **Test the prior-based formulation (#2 above) on this pilot.** ~10 min implementation, same CV harness. If it beats the current Ũ formulation, the design-matrix re-weighting was the wrong mechanism; if not, dailydilemmas is just a bad domain for the inference channel.

For the dailydilemmas main study specifically: **set α=0 in `experiment_config.json`**. The K-dim projection alone beats the kernel summary on real human data (paired p<0.001, n=29); adding feedback at any positive α makes the partial fit worse.
