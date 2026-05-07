# Movies pilot — quick check

_Generated 2026-05-06 11:15 from `data.csv`._

Small-N diagnostic. Numbers are point estimates with 95% t-CIs where N>1; no inferential testing — sample size is too small.

## 1. Data integrity

- Total responses: **429**
- Complete (passed inclusion): **429** (excluded 0)
- Domains: movies_100: 429
- Duration (s): median=574, mean=651

**Per-condition counts and choice balance:**

| Condition | N | mean % chose A | sd |
|---|---|---|---|
| Choice only | 146 | 50.9% | 10.9% |
| Affirm/remove | 143 | 50.1% | 11.6% |
| Category select | 140 | 48.5% | 11.0% |

Sanity: mean % A should be near 50% (no display-side bias). Within-participant SD of choices is not shown here.

## 2. Feedback engagement (inference conditions)

| Condition | N | participants who gave any feedback | mean engagement rate |
|---|---|---|---|
| Affirm/remove | 143 | 143/143 (100%) | 61.4% |
| Category select | 140 | 138/140 (99%) | 70.4% |

Engagement rate = fraction of inference items where action ≠ 'remove'/'none'. Low values mean the prior collapses toward 0 → projection_alpha ≈ projection_only.

## 3. LOO accuracy at each parameter cell

Each cell defines (scheme, α, λ) used to compute the feedback prior and fit BTL. `random_projection` and `projection_only` depend only on λ, so they are shared across cells with the same λ. `projection_alpha` is the augmented model that uses the feedback prior.

| Cell label | scheme | α | λ |
|---|---|---|---|
| `movies_deployed` | `quintile_midpoints` | 1.0 | 0.005 |
| `dilemmas_deployed` | `quintile_midpoints` | 2.0 | 0.01 |
| `scheme_switch_only` | `linear_uniform` | 1.0 | 0.005 |
| `dilemmas_optimum` | `linear_uniform` | 0.3 | 0.001 |

### 3a. Choice-only manipulation check

Does the LLM-derived semantic projection beat random projection? Independent of (scheme, α). Reported per λ used in this sweep.

| λ | random_projection | projection_only | lift (proj_only − random) |
|---|---|---|---|
| 0.005 | 0.560  [0.539, 0.581]  (N=146) | 0.607  [0.583, 0.630]  (N=146) | +0.047  [+0.017, +0.076]  (N=146) |
| 0.01 | 0.555  [0.534, 0.576]  (N=146) | 0.617  [0.595, 0.640]  (N=146) | +0.062  [+0.035, +0.090]  (N=146) |
| 0.001 | 0.563  [0.542, 0.584]  (N=146) | 0.590  [0.567, 0.614]  (N=146) | +0.027  [-0.002, +0.057]  (N=146) |

### 3b. Inference conditions: projection_alpha vs projection_only

This is the headline calibration check. The lift = projection_alpha − projection_only at each cell. Positive = the prior is helping. With small N the CIs will be wide; look at point estimates and direction-of-effect.

**Affirm/remove**

| Cell | projection_only | projection_alpha | Lift |
|---|---|---|---|
| `movies_deployed` | 0.605  [0.578, 0.631]  (N=143) | 0.604  [0.581, 0.627]  (N=143) | -0.000  [-0.023, +0.022]  (N=143) |
| `dilemmas_deployed` | 0.610  [0.584, 0.636]  (N=143) | 0.603  [0.580, 0.626]  (N=143) | -0.007  [-0.029, +0.015]  (N=143) |
| `scheme_switch_only` | 0.605  [0.578, 0.631]  (N=143) | 0.603  [0.580, 0.626]  (N=143) | -0.001  [-0.024, +0.021]  (N=143) |
| `dilemmas_optimum` | 0.601  [0.576, 0.627]  (N=143) | 0.607  [0.583, 0.630]  (N=143) | +0.005  [-0.017, +0.028]  (N=143) |

**Category select**

| Cell | projection_only | projection_alpha | Lift |
|---|---|---|---|
| `movies_deployed` | 0.611  [0.588, 0.634]  (N=140) | 0.619  [0.597, 0.641]  (N=140) | +0.008  [-0.014, +0.030]  (N=140) |
| `dilemmas_deployed` | 0.614  [0.591, 0.637]  (N=140) | 0.618  [0.596, 0.640]  (N=140) | +0.004  [-0.018, +0.026]  (N=140) |
| `scheme_switch_only` | 0.611  [0.588, 0.634]  (N=140) | 0.619  [0.597, 0.642]  (N=140) | +0.008  [-0.014, +0.030]  (N=140) |
| `dilemmas_optimum` | 0.602  [0.579, 0.625]  (N=140) | 0.621  [0.599, 0.643]  (N=140) | +0.019  [-0.003, +0.041]  (N=140) |

## 4. Reading guide

**Pipeline working** if:
- (1) reports show participants distributed across conditions and complete=N_total
- (2) shows engagement rate >50% in inference cells (else feedback isn't reaching the model)
- (3a) choice-only lift is positive (manipulation check transfers from dilemmas)

**Calibration on target** if:
- The `movies_deployed` cell shows a positive lift in inference conditions
- The `dilemmas_optimum` cell ≈ or > the `movies_deployed` cell (suggesting the dilemmas optimum transfers)
- The `scheme_switch_only` cell ≥ the `movies_deployed` cell (suggesting linear_uniform > quintile_midpoints holds for movies too)

**Caveats:**
- With small N, CIs will be wide and signs may flip on noise.
- This is *not* an inferential test — just a directional sanity check.
- Any clearly negative lift across multiple cells suggests something is broken upstream (data, JS, prior construction); investigate before scaling.
