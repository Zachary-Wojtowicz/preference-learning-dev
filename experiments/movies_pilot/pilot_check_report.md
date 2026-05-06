# Movies pilot — quick check

_Generated 2026-05-05 20:38 from `data.csv`._

Small-N diagnostic. Numbers are point estimates with 95% t-CIs where N>1; no inferential testing — sample size is too small.

## 1. Data integrity

- Total responses: **30**
- Complete (passed inclusion): **30** (excluded 0)
- Domains: movies_100: 30
- Duration (s): median=593, mean=676

**Per-condition counts and choice balance:**

| Condition | N | mean % chose A | sd |
|---|---|---|---|
| Choice only | 10 | 54.0% | 14.7% |
| Affirm/remove | 11 | 48.2% | 11.5% |
| Category select | 9 | 50.6% | 15.7% |

Sanity: mean % A should be near 50% (no display-side bias). Within-participant SD of choices is not shown here.

## 2. Feedback engagement (inference conditions)

| Condition | N | participants who gave any feedback | mean engagement rate |
|---|---|---|---|
| Affirm/remove | 11 | 11/11 (100%) | 54.8% |
| Category select | 9 | 9/9 (100%) | 62.8% |

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
| 0.005 | 0.550  [0.442, 0.658]  (N=10) | 0.645  [0.553, 0.737]  (N=10) | +0.095  [-0.042, +0.232]  (N=10) |
| 0.01 | 0.545  [0.435, 0.655]  (N=10) | 0.645  [0.558, 0.732]  (N=10) | +0.100  [-0.033, +0.233]  (N=10) |
| 0.001 | 0.515  [0.404, 0.626]  (N=10) | 0.655  [0.565, 0.745]  (N=10) | +0.140  [-0.022, +0.302]  (N=10) |

### 3b. Inference conditions: projection_alpha vs projection_only

This is the headline calibration check. The lift = projection_alpha − projection_only at each cell. Positive = the prior is helping. With small N the CIs will be wide; look at point estimates and direction-of-effect.

**Affirm/remove**

| Cell | projection_only | projection_alpha | Lift |
|---|---|---|---|
| `movies_deployed` | 0.614  [0.476, 0.751]  (N=11) | 0.559  [0.467, 0.651]  (N=11) | -0.055  [-0.117, +0.008]  (N=11) |
| `dilemmas_deployed` | 0.627  [0.488, 0.767]  (N=11) | 0.559  [0.467, 0.651]  (N=11) | -0.068  [-0.127, -0.009]  (N=11) |
| `scheme_switch_only` | 0.614  [0.476, 0.751]  (N=11) | 0.559  [0.462, 0.656]  (N=11) | -0.055  [-0.117, +0.008]  (N=11) |
| `dilemmas_optimum` | 0.577  [0.442, 0.713]  (N=11) | 0.568  [0.480, 0.656]  (N=11) | -0.009  [-0.088, +0.070]  (N=11) |

**Category select**

| Cell | projection_only | projection_alpha | Lift |
|---|---|---|---|
| `movies_deployed` | 0.667  [0.603, 0.730]  (N=9) | 0.622  [0.558, 0.686]  (N=9) | -0.044  [-0.133, +0.045]  (N=9) |
| `dilemmas_deployed` | 0.678  [0.608, 0.747]  (N=9) | 0.611  [0.537, 0.685]  (N=9) | -0.067  [-0.159, +0.025]  (N=9) |
| `scheme_switch_only` | 0.667  [0.603, 0.730]  (N=9) | 0.633  [0.564, 0.703]  (N=9) | -0.033  [-0.110, +0.044]  (N=9) |
| `dilemmas_optimum` | 0.633  [0.564, 0.703]  (N=9) | 0.628  [0.561, 0.695]  (N=9) | -0.006  [-0.073, +0.062]  (N=9) |

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
