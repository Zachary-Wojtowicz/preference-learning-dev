"""
Pilot analysis for the preference-learning experiment.

Three jobs:
  1. Dry-run the planned full-study analysis pipeline on the pilot N, so we
     can verify the data has every field we need before scaling up.
  2. Validate that the experiment is working — practice-trial accuracy,
     completion rates, no missing eval/prediction screens, sensible timing.
  3. Use the pilot's effect-size estimates to power the full study (per-cell
     N to detect the observed effects at α=0.05, power=0.80).

Usage:
  python experiments/pilot/analyze_pilot.py
  → writes experiments/pilot/PILOT_REPORT.md and a few PNGs.

Data assumed at: experiments/pilot/data.csv (Qualtrics export).

Sign conventions:
  - eval_dv (inference conditions): + means PARTIAL summary preferred over
    STANDARD. The Likert is mapped −3..+3 from the perspective of side A vs.
    side B; we flip when partial was on the left.
  - eval_dv (choice_only baseline check): + means REAL fitted summary
    preferred over RANDOM. choice_only is a manipulation check — if real
    isn't beating random, something is broken upstream.
  - pred_dv: 1..6 (very_inacc → very_acc). Midpoint = 3.5.
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats


PILOT_DIR = Path(__file__).resolve().parent
CSV_PATH = PILOT_DIR / "data.csv"
REPORT_PATH = PILOT_DIR / "PILOT_REPORT.md"

# Likert mapping from index.html LIKERT_LEVELS (A_much_better=-3 → B_much=+3).
# rating_numeric is signed: negative ⇒ side A preferred, positive ⇒ side B.

# ---------------------------------------------------------------------------
# Load + parse
# ---------------------------------------------------------------------------

def load_pilot():
    """Parse the Qualtrics CSV (skipping its 2 header rows) and explode the
    embedded JSON `experiment_data` column into per-row dicts."""
    df = pd.read_csv(CSV_PATH)
    df = df.iloc[2:].reset_index(drop=True)
    rows = []
    parse_failures = []
    for _, row in df.iterrows():
        rec = {
            "qualtrics_id": row["ResponseId"],
            "prolific_pid": row.get("PROLIFIC_PID"),
            "condition": row["condition"],
            "domain": row["domain"],
            "num_trials_setting": row.get("num_trials"),
            "duration_s": float(row.get("Duration (in seconds)") or 0),
            "finished": str(row.get("Finished")) == "1",
            "progress": int(row.get("Progress") or 0),
            "consent": row.get("consent"),
            "age": row.get("demos_age"),
            "gender": row.get("demos_gender"),
            "education": row.get("demos_education"),
        }
        ed_raw = row.get("experiment_data")
        if not isinstance(ed_raw, str) or not ed_raw.strip().startswith("{"):
            parse_failures.append(rec["qualtrics_id"])
            rec["experiment_data"] = None
        else:
            try:
                rec["experiment_data"] = json.loads(ed_raw)
            except json.JSONDecodeError as e:
                parse_failures.append((rec["qualtrics_id"], str(e)))
                rec["experiment_data"] = None
        rows.append(rec)
    return rows, parse_failures


# ---------------------------------------------------------------------------
# Per-participant feature extraction
# ---------------------------------------------------------------------------

def signed_eval_dv(evaluation):
    """Convert evaluation.rating_numeric → DV signed in favor of the
    'interesting' model. Returns (dv, direction_label).

    For inference conditions: + ⇒ partial (feedback_adjusted) preferred.
    For choice_only:           + ⇒ real (standard) preferred over random.
    None if no eval, was skipped, or model labels missing.
    """
    if not evaluation or "skipped" in evaluation:
        return None, None
    rn = evaluation.get("rating_numeric")
    if rn is None:
        return None, None
    left = evaluation.get("left_model")
    right = evaluation.get("right_model")
    is_baseline = evaluation.get("is_baseline_check", False)
    target = "feedback_adjusted" if not is_baseline else "standard"
    other = "standard" if not is_baseline else "random"
    if {left, right} != {target, other}:
        return None, None
    # rating_numeric: negative ⇒ A preferred, positive ⇒ B preferred.
    sign = +1 if right == target else -1
    return sign * rn, ("+ ⇒ partial preferred" if not is_baseline
                        else "+ ⇒ real preferred over random")


def per_participant_features(rec):
    """Reduce one participant's experiment_data to a flat row of features."""
    f = {
        "qualtrics_id": rec["qualtrics_id"],
        "prolific_pid": rec["prolific_pid"],
        "condition": rec["condition"],
        "domain": rec["domain"],
        "duration_s": rec["duration_s"],
        "finished": rec["finished"],
        "progress": rec["progress"],
        "age": rec["age"],
    }
    ed = rec["experiment_data"]
    if ed is None:
        f.update({"n_training": 0, "n_responses": 0, "training_acc": np.nan,
                  "mean_choice_rt_ms": np.nan, "mean_feedback_rt_ms": np.nan,
                  "feedback_action_rate": np.nan, "feedback_modify_rate": np.nan,
                  "eval_dv": np.nan, "eval_rating_label": None,
                  "pred_dv": np.nan, "pred_signed_diff": np.nan})
        return f

    # Practice trials (gold-keyed)
    tr = ed.get("training_responses", []) or []
    f["n_training"] = len(tr)
    f["training_acc"] = float(np.mean([t.get("correct", False) for t in tr])) if tr else np.nan

    # Feedback trials
    resp = ed.get("responses", []) or []
    f["n_responses"] = len(resp)
    if resp:
        choice_rts = [r.get("time_to_first_choice_ms") for r in resp
                      if r.get("time_to_first_choice_ms") is not None]
        submit_rts = [r.get("time_to_submit_ms") for r in resp
                      if r.get("time_to_submit_ms") is not None]
        feedback_rts = [s - c for c, s in zip(choice_rts, submit_rts)
                        if c is not None and s is not None]
        f["mean_choice_rt_ms"] = float(np.mean(choice_rts)) if choice_rts else np.nan
        f["mean_feedback_rt_ms"] = float(np.mean(feedback_rts)) if feedback_rts else np.nan

        # Inference engagement: across all (trial × visible-dim) cells, what
        # fraction had a non-default action ("affirm", "modify", "remove")?
        iv_cells = []
        for r in resp:
            for k, v in (r.get("inference_values") or {}).items():
                iv_cells.append(v.get("action") or "none")
        if iv_cells:
            f["feedback_action_rate"] = float(np.mean([a != "none" for a in iv_cells]))
            f["feedback_modify_rate"] = float(np.mean([a == "modify" for a in iv_cells]))
            f["feedback_affirm_rate"] = float(np.mean([a == "affirm" for a in iv_cells]))
            f["feedback_remove_rate"] = float(np.mean([a == "remove" for a in iv_cells]))
        else:
            f["feedback_action_rate"] = np.nan
            f["feedback_modify_rate"] = np.nan
            f["feedback_affirm_rate"] = np.nan
            f["feedback_remove_rate"] = np.nan
    else:
        f.update({"mean_choice_rt_ms": np.nan, "mean_feedback_rt_ms": np.nan,
                  "feedback_action_rate": np.nan, "feedback_modify_rate": np.nan,
                  "feedback_affirm_rate": np.nan, "feedback_remove_rate": np.nan})

    # Evaluation screen (signed in favor of partial / real)
    eval_dv, eval_dir = signed_eval_dv(ed.get("evaluation"))
    f["eval_dv"] = eval_dv
    f["eval_dv_direction"] = eval_dir
    f["eval_skipped"] = "skipped" in (ed.get("evaluation") or {})
    f["eval_left_model"] = (ed.get("evaluation") or {}).get("left_model")
    f["eval_right_model"] = (ed.get("evaluation") or {}).get("right_model")

    # Prediction-check screen
    pc = ed.get("prediction_check") or {}
    f["pred_skipped"] = "skipped" in pc
    f["pred_dv"] = pc.get("rating_numeric")
    f["pred_signed_diff"] = pc.get("pair_signed_diff")
    f["pred_model"] = pc.get("model")

    return f


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------

def md_line(buf, *args):
    buf.append(" ".join(str(a) for a in args))


def fmt_pct(x, n=None):
    if pd.isna(x):
        return "—"
    if n is not None:
        return f"{int(round(x * n))}/{n} ({x:.0%})"
    return f"{x:.0%}"


def cohens_d_one_sample(x, mu=0.0):
    """Cohen's d vs a fixed value. Returns (d, ci_lo, ci_hi) by basic
    bootstrap so it's robust to small N and non-normal."""
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    if len(x) < 2 or np.std(x, ddof=1) == 0:
        return np.nan, np.nan, np.nan
    d = (np.mean(x) - mu) / np.std(x, ddof=1)
    rng = np.random.default_rng(0)
    boot = []
    for _ in range(2000):
        s = rng.choice(x, size=len(x), replace=True)
        sd = np.std(s, ddof=1)
        if sd > 0:
            boot.append((np.mean(s) - mu) / sd)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return d, lo, hi


def n_for_one_sample_t(d, alpha=0.05, power=0.80):
    """Required N per group for one-sample t-test using normal-approx
    formula: N ≈ ((z_{α/2} + z_{β}) / d)². Returns int, capped at 9999."""
    if not np.isfinite(d) or abs(d) < 1e-3:
        return None
    z_a = stats.norm.ppf(1 - alpha / 2)
    z_b = stats.norm.ppf(power)
    return int(np.ceil(((z_a + z_b) / abs(d)) ** 2))


def n_for_two_sample_t(d, alpha=0.05, power=0.80):
    """Per-group N for a two-sample t-test (Welch-ish)."""
    if not np.isfinite(d) or abs(d) < 1e-3:
        return None
    z_a = stats.norm.ppf(1 - alpha / 2)
    z_b = stats.norm.ppf(power)
    return int(np.ceil(2 * ((z_a + z_b) / abs(d)) ** 2))


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def plot_eval_dv(df, output_path):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    conds = sorted(df["condition"].unique())
    data = [df[df["condition"] == c]["eval_dv"].dropna().values for c in conds]
    bp = ax.boxplot(data, tick_labels=[c.replace("_", "\n") for c in conds],
                    showmeans=True, widths=0.5)
    rng = np.random.default_rng(0)
    for i, vals in enumerate(data, 1):
        ax.scatter(rng.normal(i, 0.06, size=len(vals)), vals,
                   alpha=0.6, color="#1f77b4", s=24)
    ax.axhline(0, color="gray", linestyle="--", alpha=0.5,
               label="0 = no preference")
    ax.set_ylabel("Evaluation rating (+ = target preferred)")
    ax.set_title("Pilot — Evaluation DV by condition", fontweight="bold")
    ax.set_ylim(-3.3, 3.3)
    ax.legend(loc="lower right", fontsize=9)
    ax.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_pred_dv(df, output_path):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    conds = sorted(df["condition"].unique())
    data = [df[df["condition"] == c]["pred_dv"].dropna().values for c in conds]
    bp = ax.boxplot(data, tick_labels=[c.replace("_", "\n") for c in conds],
                    showmeans=True, widths=0.5)
    rng = np.random.default_rng(0)
    for i, vals in enumerate(data, 1):
        ax.scatter(rng.normal(i, 0.06, size=len(vals)), vals,
                   alpha=0.6, color="#d62728", s=24)
    ax.axhline(3.5, color="gray", linestyle="--", alpha=0.5,
               label="3.5 = neutral")
    ax.set_ylabel("Prediction-accuracy rating (1=very inacc, 6=very acc)")
    ax.set_title("Pilot — Prediction-check DV by condition", fontweight="bold")
    ax.set_ylim(0.7, 6.3)
    ax.legend(loc="lower right", fontsize=9)
    ax.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run():
    rows, parse_failures = load_pilot()
    feats = [per_participant_features(r) for r in rows]
    df = pd.DataFrame(feats)
    df.to_csv(PILOT_DIR / "per_participant.csv", index=False)

    out = []
    md_line(out, "# Pilot Analysis Report")
    md_line(out, "")
    md_line(out, f"Source: `{CSV_PATH.relative_to(PILOT_DIR.parent.parent)}`")
    md_line(out, f"N rows in CSV (post-header): **{len(df)}**")
    md_line(out, "")

    # ---------- 1) VALIDATION ----------
    md_line(out, "## 1. Validation — does the data look healthy?")
    md_line(out, "")

    md_line(out, "### Completion + parsing")
    md_line(out, "")
    md_line(out, f"- Finished (Qualtrics flag): **{df['finished'].sum()}/{len(df)}**")
    md_line(out, f"- Progress = 100: **{(df['progress'] == 100).sum()}/{len(df)}**")
    md_line(out, f"- experiment_data parsed OK: **{df['experiment_data'].notna().sum() if 'experiment_data' in df else (~df['eval_dv'].isna() | df['eval_dv'].isna()).sum()}/{len(df)}** "
                  f"(failures: {len(parse_failures)})")
    md_line(out, f"- Mean duration: **{df['duration_s'].mean():.0f} s**  "
                  f"(median {df['duration_s'].median():.0f}, "
                  f"range {df['duration_s'].min():.0f}–{df['duration_s'].max():.0f})")
    too_fast = df[df["duration_s"] < 60]
    too_slow = df[df["duration_s"] > 1500]
    md_line(out, f"- Suspiciously fast (<60s): **{len(too_fast)}** · "
                  f"long (>25 min): **{len(too_slow)}**")
    md_line(out, "")

    md_line(out, "### Cell counts")
    md_line(out, "")
    md_line(out, "| Condition | N | N w/ eval | N w/ prediction |")
    md_line(out, "|---|---|---|---|")
    for c in sorted(df["condition"].unique()):
        sub = df[df["condition"] == c]
        n_eval = sub["eval_dv"].notna().sum()
        n_pred = sub["pred_dv"].notna().sum()
        md_line(out, f"| {c} | {len(sub)} | {n_eval} | {n_pred} |")
    md_line(out, "")

    md_line(out, "### Practice-trial accuracy (sanity check)")
    md_line(out, "")
    md_line(out, "Practice trials show one preference dimension's framing and ask the "
                  "participant to identify the option scoring higher on it. Accuracy should "
                  "be well above chance — if not, either the participant didn't engage or the "
                  "dimension labels don't actually match what the embedding picks up.")
    md_line(out, "")
    md_line(out, "| Condition | N | Mean acc | SD | Above 0.5 (one-sided p) |")
    md_line(out, "|---|---|---|---|---|")
    for c in sorted(df["condition"].unique()):
        sub = df[df["condition"] == c]["training_acc"].dropna()
        if len(sub):
            try:
                t, p = stats.ttest_1samp(sub, 0.5, alternative="greater")
            except Exception:
                p = float("nan")
            md_line(out, f"| {c} | {len(sub)} | {sub.mean():.2f} | {sub.std():.2f} | p={p:.4f} |")
    overall = df["training_acc"].dropna()
    if len(overall):
        t, p = stats.ttest_1samp(overall, 0.5, alternative="greater")
        md_line(out, f"| **overall** | **{len(overall)}** | **{overall.mean():.2f}** | "
                      f"**{overall.std():.2f}** | **p={p:.4f}** |")
    md_line(out, "")

    md_line(out, "### Feedback engagement (inference conditions only)")
    md_line(out, "")
    md_line(out, "Across all trial × visible-dim cells, what fraction did the participant "
                  "*not* leave at the model's default? Low rates suggest the participant is "
                  "rubber-stamping; very high rates may mean the model's defaults are bad.")
    md_line(out, "")
    md_line(out, "| Condition | N | action_rate | affirm | modify | remove |")
    md_line(out, "|---|---|---|---|---|---|")
    for c in sorted(df["condition"].unique()):
        sub = df[df["condition"] == c]
        if not sub["feedback_action_rate"].notna().any():
            continue
        ar = sub["feedback_action_rate"].mean()
        af = sub["feedback_affirm_rate"].mean()
        mo = sub["feedback_modify_rate"].mean()
        rm = sub["feedback_remove_rate"].mean()
        md_line(out, f"| {c} | {len(sub)} | {ar:.2f} | {af:.2f} | {mo:.2f} | {rm:.2f} |")
    md_line(out, "")

    md_line(out, "### Timing breakdown")
    md_line(out, "")
    md_line(out, "| Condition | mean choice RT (s) | mean feedback panel RT (s) |")
    md_line(out, "|---|---|---|")
    for c in sorted(df["condition"].unique()):
        sub = df[df["condition"] == c]
        cr = sub["mean_choice_rt_ms"].mean() / 1000
        fr = sub["mean_feedback_rt_ms"].mean() / 1000
        md_line(out, f"| {c} | {cr:.1f} | {fr:.1f} |")
    md_line(out, "")

    # ---------- 2) DRY-RUN ANALYSIS ----------
    md_line(out, "## 2. Planned full-study analysis (dry-run on pilot N)")
    md_line(out, "")
    md_line(out, "### Primary DV 1 — Evaluation rating")
    md_line(out, "")
    md_line(out, "Each participant compares two summaries side-by-side and rates which is "
                  "better on a 6-point Likert. We sign the rating in favor of the *target* "
                  "model: partial-with-feedback for inference conditions, the real fitted "
                  "model for choice_only (which compares real vs. random as a manipulation "
                  "check).")
    md_line(out, "")
    md_line(out, "| Condition | n | mean DV | SD | one-sample t vs 0 (two-sided) | Wilcoxon vs 0 | Cohen's d |")
    md_line(out, "|---|---|---|---|---|---|---|")
    for c in sorted(df["condition"].unique()):
        x = df[df["condition"] == c]["eval_dv"].dropna().values
        if len(x) < 2:
            md_line(out, f"| {c} | {len(x)} | — | — | — | — | — |")
            continue
        try:
            t, p_t = stats.ttest_1samp(x, 0)
        except Exception:
            t, p_t = float("nan"), float("nan")
        try:
            w, p_w = stats.wilcoxon(x, zero_method="zsplit")
        except ValueError:
            p_w = float("nan")
        d, lo, hi = cohens_d_one_sample(x, 0.0)
        md_line(out, f"| {c} | {len(x)} | {x.mean():+.2f} | {x.std():.2f} | "
                      f"t={t:+.2f}, p={p_t:.3f} | p={p_w:.3f} | "
                      f"d={d:+.2f} [{lo:+.2f}, {hi:+.2f}] |")
    md_line(out, "")
    md_line(out, "Pairwise (between-condition):")
    md_line(out, "")
    md_line(out, "| Comparison | mean Δ | Welch t | p | Cohen's d_s |")
    md_line(out, "|---|---|---|---|---|")
    cs = sorted(df["condition"].unique())
    for i in range(len(cs)):
        for j in range(i + 1, len(cs)):
            a = df[df["condition"] == cs[i]]["eval_dv"].dropna().values
            b = df[df["condition"] == cs[j]]["eval_dv"].dropna().values
            if len(a) < 2 or len(b) < 2:
                continue
            t, p = stats.ttest_ind(a, b, equal_var=False)
            sd = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
            d = (a.mean() - b.mean()) / sd if sd > 0 else float("nan")
            md_line(out, f"| {cs[i]} vs {cs[j]} | {a.mean() - b.mean():+.2f} | "
                          f"{t:+.2f} | {p:.3f} | {d:+.2f} |")
    md_line(out, "")

    md_line(out, "### Primary DV 2 — Prediction-check accuracy rating")
    md_line(out, "")
    md_line(out, "Participant rates the model's predicted choice on a real held-out "
                  "trial pair: 1 = very inaccurate, 6 = very accurate. Above 3.5 ⇒ "
                  "prediction is judged net accurate.")
    md_line(out, "")
    md_line(out, "| Condition | n | mean | SD | t vs 3.5 | p | Cohen's d |")
    md_line(out, "|---|---|---|---|---|---|---|")
    for c in sorted(df["condition"].unique()):
        x = df[df["condition"] == c]["pred_dv"].dropna().astype(float).values
        if len(x) < 2:
            md_line(out, f"| {c} | {len(x)} | — | — | — | — | — |")
            continue
        try:
            t, p = stats.ttest_1samp(x, 3.5)
        except Exception:
            t, p = float("nan"), float("nan")
        d, lo, hi = cohens_d_one_sample(x, 3.5)
        md_line(out, f"| {c} | {len(x)} | {x.mean():.2f} | {x.std():.2f} | "
                      f"t={t:+.2f} | p={p:.3f} | d={d:+.2f} |")
    md_line(out, "")

    md_line(out, "### Secondary — feedback engagement vs DV (correlations)")
    md_line(out, "")
    md_line(out, "Hypothesis: participants who engaged more with the inference UI got "
                  "more accurate summaries, so we should see action_rate ↔ eval_dv > 0 "
                  "in the inference conditions.")
    md_line(out, "")
    md_line(out, "| Condition | n | r(action_rate, eval_dv) | p | r(action_rate, pred_dv) | p |")
    md_line(out, "|---|---|---|---|---|---|")
    for c in sorted(df["condition"].unique()):
        sub = df[df["condition"] == c]
        ar = sub["feedback_action_rate"]
        ev = sub["eval_dv"]
        pv = sub["pred_dv"].astype(float)
        ok = ar.notna() & ev.notna()
        if ok.sum() >= 3 and ar[ok].std() > 0 and ev[ok].std() > 0:
            r1, p1 = stats.pearsonr(ar[ok], ev[ok])
            r1s, p1s = f"{r1:+.2f}", f"{p1:.3f}"
        else:
            r1s = p1s = "—"
        ok2 = ar.notna() & pv.notna()
        if ok2.sum() >= 3 and ar[ok2].std() > 0 and pv[ok2].std() > 0:
            r2, p2 = stats.pearsonr(ar[ok2], pv[ok2])
            r2s, p2s = f"{r2:+.2f}", f"{p2:.3f}"
        else:
            r2s = p2s = "—"
        md_line(out, f"| {c} | {len(sub)} | {r1s} | {p1s} | {r2s} | {p2s} |")
    md_line(out, "")

    # ---------- 3) POWER ----------
    md_line(out, "## 3. Power analysis for the full study")
    md_line(out, "")
    md_line(out, "Using the pilot's effect-size estimates, what per-cell N do we need to "
                  "achieve 80% power at α=0.05 (two-sided)? These are rough — the pilot's "
                  "small N gives noisy d estimates with wide bootstrap CIs.")
    md_line(out, "")

    md_line(out, "### One-sample tests (DV vs null)")
    md_line(out, "")
    md_line(out, "| Test | observed d | 95% CI (boot) | N needed (point) | N needed (lower CI) |")
    md_line(out, "|---|---|---|---|---|")
    for c in sorted(df["condition"].unique()):
        x = df[df["condition"] == c]["eval_dv"].dropna().values
        if len(x) < 2: continue
        d, lo, hi = cohens_d_one_sample(x, 0.0)
        d_lower = min(abs(lo), abs(hi)) if (np.isfinite(lo) and np.isfinite(hi)) else float("nan")
        n_pt = n_for_one_sample_t(d)
        n_lo = n_for_one_sample_t(d_lower) if d_lower else None
        md_line(out, f"| {c} eval_dv vs 0 | {d:+.2f} | [{lo:+.2f}, {hi:+.2f}] | "
                      f"{n_pt or '∞'} | {n_lo or '∞'} |")
    for c in sorted(df["condition"].unique()):
        x = df[df["condition"] == c]["pred_dv"].dropna().astype(float).values
        if len(x) < 2: continue
        d, lo, hi = cohens_d_one_sample(x, 3.5)
        d_lower = min(abs(lo), abs(hi)) if (np.isfinite(lo) and np.isfinite(hi)) else float("nan")
        n_pt = n_for_one_sample_t(d)
        n_lo = n_for_one_sample_t(d_lower) if d_lower else None
        md_line(out, f"| {c} pred_dv vs 3.5 | {d:+.2f} | [{lo:+.2f}, {hi:+.2f}] | "
                      f"{n_pt or '∞'} | {n_lo or '∞'} |")
    md_line(out, "")

    md_line(out, "### Two-sample tests (between conditions, eval_dv)")
    md_line(out, "")
    md_line(out, "| Comparison | observed Δ | pooled SD | d_s | Per-cell N needed |")
    md_line(out, "|---|---|---|---|---|")
    cs = sorted(df["condition"].unique())
    for i in range(len(cs)):
        for j in range(i + 1, len(cs)):
            a = df[df["condition"] == cs[i]]["eval_dv"].dropna().values
            b = df[df["condition"] == cs[j]]["eval_dv"].dropna().values
            if len(a) < 2 or len(b) < 2: continue
            sd = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
            d = (a.mean() - b.mean()) / sd if sd > 0 else float("nan")
            n_per_cell = n_for_two_sample_t(d)
            md_line(out, f"| {cs[i]} vs {cs[j]} | {a.mean() - b.mean():+.2f} | "
                          f"{sd:.2f} | {d:+.2f} | {n_per_cell or '∞'} |")
    md_line(out, "")

    md_line(out, "### Recommendation")
    md_line(out, "")
    md_line(out, "- **Choose the largest N** across the comparisons you actually plan to "
                  "report as primary. Inference-condition vs. choice_only is usually the "
                  "strictest test and should drive the recruitment target.")
    md_line(out, "- Inflate by 15–20% for attention-check / completion attrition.")
    md_line(out, "- The bootstrap CIs are wide at this N — treat point estimates as "
                  "lower-bound optimism. The CI-lower-bound column gives a more "
                  "conservative anchor.")
    md_line(out, "")

    # ---------- 4) DATA-COMPLETENESS CHECKLIST ----------
    md_line(out, "## 4. Data-completeness checklist for the full study")
    md_line(out, "")
    md_line(out, "Each row in this checklist should be 100% green before launching the "
                  "main study. If anything is missing now, fix the data export *first*.")
    md_line(out, "")
    have = lambda col: df[col].notna().sum()
    n = len(df)
    items = [
        ("Qualtrics ResponseId", "qualtrics_id"),
        ("PROLIFIC_PID for ID match", "prolific_pid"),
        ("Condition assignment", "condition"),
        ("Domain label", "domain"),
        ("Total survey duration", "duration_s"),
        ("Practice-trial accuracy", "training_acc"),
        ("Feedback-trial RTs", "mean_choice_rt_ms"),
        ("Feedback engagement (inference)", "feedback_action_rate"),
        ("Evaluation DV (signed)", "eval_dv"),
        ("Prediction-check DV", "pred_dv"),
    ]
    md_line(out, "| Field | non-null / total |")
    md_line(out, "|---|---|")
    for label, col in items:
        if col not in df.columns:
            md_line(out, f"| {label} | **MISSING from CSV** |")
            continue
        md_line(out, f"| {label} | {have(col)}/{n} |")
    md_line(out, "")

    # Plots
    plot_eval_dv(df, PILOT_DIR / "eval_dv_by_condition.png")
    plot_pred_dv(df, PILOT_DIR / "pred_dv_by_condition.png")
    md_line(out, "## Plots")
    md_line(out, "")
    md_line(out, "- `eval_dv_by_condition.png` — boxplot + jitter of the evaluation DV.")
    md_line(out, "- `pred_dv_by_condition.png` — boxplot + jitter of the prediction-check DV.")
    md_line(out, "- `per_participant.csv` — flat per-participant feature table (use this "
                  "as the input for any further analysis you write).")

    REPORT_PATH.write_text("\n".join(out) + "\n")
    print(f"Wrote {REPORT_PATH}")
    print(f"Wrote {PILOT_DIR / 'per_participant.csv'}")
    print(f"Wrote {PILOT_DIR / 'eval_dv_by_condition.png'}")
    print(f"Wrote {PILOT_DIR / 'pred_dv_by_condition.png'}")


if __name__ == "__main__":
    run()
