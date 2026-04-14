#!/usr/bin/env python3
"""
Adaptive dimension discovery for pairwise preference explanations.

Workflow:
1) Sample a subset of items (default 500 wines) from embedded parquet.
2) Sample a seed set (default 50) and ask the LLM for 10 initial dimensions.
3) Repeatedly judge random item pairs:
   - mark which active dimensions explain the difference
   - collect missed difference labels
4) Every `switch_interval` judgments (default 20):
   - identify low-performing active dimensions
   - merge frequent missed labels into candidate dimensions
   - swap low performers with high-support candidates

Reliability:
- Checkpoint/resume built in.
- Per-judgment progress/ranking logs are written continuously.
- Judgment-level failures are retried with backoff and do not terminate run unless
  max consecutive failures is exceeded.
"""

import argparse
import base64
import csv
import json
import math
import os
import pickle
import random
import re
import threading
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pyarrow.parquet as pq


DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parent / "outputs"
DEFAULT_TIMEOUT = 90
DEFAULT_RETRIES = 3
DEFAULT_SEED = 42

PROVIDER_DEFAULTS = {
    "openai": {"base_url": "https://api.openai.com/v1", "env_key": "OPENAI_API_KEY"},
    "anthropic": {"base_url": "https://api.anthropic.com/v1", "env_key": "ANTHROPIC_API_KEY"},
    "nvidia": {"base_url": "https://integrate.api.nvidia.com/v1", "env_key": "NVIDIA_API_KEY"},
}

_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


@dataclass
class RateLimiter:
    requests_per_minute: float
    _lock: threading.Lock = threading.Lock()
    _last_call_ts: float = 0.0

    def wait(self):
        if self.requests_per_minute <= 0:
            return
        min_interval = 60.0 / self.requests_per_minute
        with self._lock:
            now = time.monotonic()
            wait_for = (self._last_call_ts + min_interval) - now
            if wait_for > 0:
                time.sleep(wait_for)
            self._last_call_ts = time.monotonic()


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", required=True)
    p.add_argument("--provider", choices=["openai", "anthropic", "nvidia", "local"], default="nvidia")
    p.add_argument("--base-url", default=None)
    p.add_argument("--model", default="meta/llama-3.3-70b-instruct")
    p.add_argument("--api-key", default=None)
    p.add_argument("--output-dir", default=None)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--subset-size", type=int, default=500)
    p.add_argument("--seed-sample-size", type=int, default=50)
    p.add_argument("--n-dimensions", type=int, default=10)
    p.add_argument("--judgments-total", type=int, default=120)
    p.add_argument("--switch-interval", type=int, default=20)
    p.add_argument("--max-swaps-per-interval", type=int, default=2)
    p.add_argument("--rate-limit-per-minute", type=float, default=40.0)
    p.add_argument("--request-timeout-seconds", type=int, default=DEFAULT_TIMEOUT)
    p.add_argument("--max-retries", type=int, default=DEFAULT_RETRIES)
    p.add_argument("--max-consecutive-failures", type=int, default=20)
    p.add_argument("--retry-sleep-seconds", type=int, default=15)
    p.add_argument(
        "--prompt-style",
        choices=[
            "baseline",
            "human_tradeoff",
            "decision_framed",
            "judgeable_axes",
            "content_presence",
            "clear_binary_axes",
            "mixed_clear_axes",
        ],
        default="human_tradeoff",
    )
    p.add_argument("--resume", action="store_true", default=True)
    p.add_argument("--no-resume", action="store_false", dest="resume")
    return p.parse_args()


def load_dotenv():
    if not _ENV_FILE.exists():
        return
    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if k and k not in os.environ:
            os.environ[k] = v


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")


def write_csv(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def read_csv_rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"Could not read headers from {path}")
        return [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in reader]


def make_client(base_url, api_key, provider):
    from openai import OpenAI

    d = PROVIDER_DEFAULTS.get(provider, {})
    base_url = base_url or d.get("base_url")
    api_key = api_key or os.environ.get(d.get("env_key", ""), "") or "x"
    if not base_url:
        raise ValueError(f"--base-url required for provider='{provider}'")
    return OpenAI(base_url=base_url, api_key=api_key)


_VALID_ESCAPES = set('"\\/ bfnrtu')


def _fix_escapes(s):
    out, i = [], 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            out.append(s[i] if s[i + 1] in _VALID_ESCAPES else "\\\\")
            i += 1
        else:
            out.append(s[i])
        i += 1
    return "".join(out)


def parse_json_blob(content):
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\\s*", "", content)
        content = re.sub(r"\\s*```$", "", content)

    attempts = [
        lambda c: json.loads(c),
        lambda c: json.loads(c[c.find("["): c.rfind("]") + 1]),
        lambda c: json.loads(_fix_escapes(c[c.find("["): c.rfind("]") + 1])),
        lambda c: json.loads(c[c.find("{"): c.rfind("}") + 1]),
        lambda c: json.loads(_fix_escapes(c[c.find("{"): c.rfind("}") + 1])),
    ]
    for f in attempts:
        try:
            return f(content)
        except Exception:
            continue
    raise ValueError(f"Could not parse JSON response: {content[:400]}")


def _is_rate_limit_error(e: Exception) -> bool:
    msg = str(e)
    return "429" in msg or "Too Many Requests" in msg or "rate_limit" in msg.lower()


def chat(client, model, prompt, timeout, retries, limiter: RateLimiter, max_tokens=None):
    last_err = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            limiter.wait()
            req = {
                "model": model,
                "temperature": 0,
                "messages": [{"role": "user", "content": prompt}],
                "timeout": timeout,
            }
            if max_tokens is not None:
                req["max_tokens"] = int(max_tokens)
            resp = client.chat.completions.create(**req)
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            last_err = e
            if attempt < retries:
                if _is_rate_limit_error(e):
                    wait = min(20 * attempt, 180)
                    print(f"[rate-limit] 429 on attempt {attempt}/{retries}, sleeping {wait}s", flush=True)
                    time.sleep(wait)
                else:
                    time.sleep(min(attempt, 3))
    raise last_err


def chat_json(client, model, prompt, timeout, retries, limiter: RateLimiter, max_tokens=None):
    text = chat(client, model, prompt, timeout, retries, limiter, max_tokens=max_tokens)
    return parse_json_blob(text)


def parse_pair_response(raw_text: str):
    """Best-effort parser for pair judgment JSON; handles truncated outputs."""
    try:
        parsed = parse_json_blob(raw_text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    used_ids = []
    missed = []
    explanations = []

    m = re.search(r'"used_dimension_ids"\\s*:\\s*\\[([^\\]]*)\\]', raw_text, flags=re.IGNORECASE | re.DOTALL)
    if m:
        used_ids = [int(x) for x in re.findall(r"-?\\d+", m.group(1))]

    for em in re.finditer(
        r'\\{\\s*"dimension_id"\\s*:\\s*(-?\\d+)\\s*,\\s*"reason"\\s*:\\s*"([^"]*)"',
        raw_text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        explanations.append({"dimension_id": int(em.group(1)), "reason": em.group(2).strip()})

    for lm in re.finditer(r'"label"\\s*:\\s*"([^"]+)"', raw_text, flags=re.IGNORECASE):
        lbl = normalize_label(lm.group(1))
        if lbl:
            missed.append({"label": lbl, "reason": ""})

    return {
        "used_dimension_ids": used_ids,
        "dimension_explanations": explanations,
        "missed_differences": missed,
    }


def load_items(config, subset_size, seed):
    path = Path(config["input_path"])
    id_col = config.get("id_column", "row_id")
    text_col = config.get("text_column", "text")
    template_path = config.get("template_path")

    if path.suffix.lower() == ".csv":
        rows = read_csv_rows(path)
    else:
        columns = None
        if not template_path:
            columns = [id_col, text_col]
        table = pq.read_table(path, columns=columns)
        rows = table.to_pylist()

    rng = random.Random(seed)
    if subset_size and subset_size < len(rows):
        rows = rng.sample(rows, subset_size)

    template_text = None
    if template_path:
        template_text = Path(template_path).read_text(encoding="utf-8").strip()

    items = []
    for row in rows:
        text = str(row.get(text_col) or "")
        if template_text:
            lookup = {str(k): str(v) for k, v in row.items()}
            lookup.update({str(k).lower(): str(v) for k, v in row.items()})
            text = re.sub(r"\{([^{}]+)\}", lambda m: lookup.get(m.group(1).strip(), ""), template_text)
        items.append({"item_id": str(row[id_col]), "text": text.strip()})
    return items


def normalize_label(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9\\s\-]", "", s)
    s = re.sub(r"\\s+", " ", s).strip()
    return s


def dim_short_text(dim):
    return f"#{dim['dimension_id']}: {dim['name']} | low='{dim['low_label']}' high='{dim['high_label']}'"


def build_seed_prompt(domain, choice_context, sample_rows, n_dimensions, prompt_style):
    examples = "\n".join([f"- {r['text'][:450]}" for r in sample_rows])
    if prompt_style == "baseline":
        return (
            "You are defining interpretable preference dimensions for pairwise differences.\\n\\n"
            f"DOMAIN: {domain}\\n"
            f"CHOICE CONTEXT: {choice_context}\\n\\n"
            f"Here are sample options ({len(sample_rows)}):\\n{examples}\\n\\n"
            f"Return exactly {n_dimensions} dimensions as a JSON array.\\n"
            "Each object must have: name, low_label, high_label, description.\\n"
            "Rules:\\n"
            "- Dimensions should explain why one option is preferred over another.\\n"
            "- Keep names short and non-overlapping.\\n"
            "- Use labels grounded in these examples.\\n"
            "- Output JSON only."
        )
    if prompt_style == "decision_framed":
        return (
            "You are helping design a choice study.\\n\\n"
            f"DOMAIN: {domain}\\n"
            f"CHOICE CONTEXT: {choice_context}\\n\\n"
            f"Here are sample options ({len(sample_rows)}):\\n{examples}\\n\\n"
            f"Return exactly {n_dimensions} axes as JSON.\\n"
            "Each object must contain: name, low_label, high_label, description.\\n"
            "Goal:\\n"
            "- Create axes that a normal chooser could actually use to compare two options and say, tonight I want more X and less Y.\\n"
            "- Favor experiential or decision-relevant contrasts over metadata buckets.\\n"
            "- Avoid broad catch-alls, production-side trivia, or labels that absorb many unrelated reasons.\\n"
            "- Each axis should isolate one understandable contrast with two opposed poles.\\n"
            "- If an axis would be hard to judge from the option descriptions, do not include it.\\n"
            "- Output JSON only."
        )
    if prompt_style == "judgeable_axes":
        return (
            "You are designing a set of comparison axes that ordinary people could actually use when choosing between two options.\\n\\n"
            f"DOMAIN: {domain}\\n"
            f"CHOICE CONTEXT: {choice_context}\\n\\n"
            f"Here are sample options ({len(sample_rows)}):\\n{examples}\\n\\n"
            f"Return exactly {n_dimensions} axes as JSON.\\n"
            "Each object must contain: name, low_label, high_label, description.\\n"
            "Rules:\\n"
            "- Every axis must pass this test: if shown two option descriptions, a human could reasonably judge which one is more toward the high pole.\\n"
            "- Prefer chooser-facing contrasts over metadata, producer-side facts, or abstract analysis jargon.\\n"
            "- Each axis should represent one clean contrast, not an umbrella.\\n"
            "- Avoid labels that are too vague to judge directly from descriptions.\\n"
            "- A good axis has clearly opposed poles and can be applied consistently by two different humans.\\n"
            "- Keep the poles clearly opposed and easy to understand.\\n"
            "- Output JSON only."
        )
    if prompt_style == "content_presence":
        return (
            "You are designing comparison axes that ordinary people could use immediately.\\n\\n"
            f"DOMAIN: {domain}\\n"
            f"CHOICE CONTEXT: {choice_context}\\n\\n"
            f"Here are sample options ({len(sample_rows)}):\\n{examples}\\n\\n"
            f"Return exactly {n_dimensions} axes as JSON.\\n"
            "Each object must contain: name, low_label, high_label, description.\\n"
            "Rules:\\n"
            "- Favor axes where the high pole often means MORE of a salient thing and the low pole means LESS or NONE of it.\\n"
            "- Prefer directly observable presence or intensity contrasts over interpretive umbrella concepts.\\n"
            "- Each axis should be easy to judge from a short description.\\n"
            "- Avoid vague abstractions that require interpretation rather than observation.\\n"
            "- Keep axes broad enough to recur, but concrete enough that two people would make similar judgments.\\n"
            "- Output JSON only."
        )
    if prompt_style == "clear_binary_axes":
        return (
            "You are designing comparison axes for a human judgment task.\\n\\n"
            f"DOMAIN: {domain}\\n"
            f"CHOICE CONTEXT: {choice_context}\\n\\n"
            f"Here are sample options ({len(sample_rows)}):\\n{examples}\\n\\n"
            f"Return exactly {n_dimensions} axes as JSON.\\n"
            "Each object must contain: name, low_label, high_label, description.\\n"
            "Rules:\\n"
            "- Favor axes with crisp opposed poles that humans can compare reliably.\\n"
            "- Prefer binary-like or monotonic contrasts over soft umbrella concepts.\\n"
            "- Ask: could a person look at two descriptions and confidently say which one has more of this?\\n"
            "- Include both observable-content contrasts and experiential contrasts, but only if both are directly judgeable.\\n"
            "- Output JSON only."
        )
    if prompt_style == "mixed_clear_axes":
        return (
            "You are designing a choice study and need 10 strong axes.\\n\\n"
            f"DOMAIN: {domain}\\n"
            f"CHOICE CONTEXT: {choice_context}\\n\\n"
            f"Here are sample options ({len(sample_rows)}):\\n{examples}\\n\\n"
            f"Return exactly {n_dimensions} axes as JSON.\\n"
            "Each object must contain: name, low_label, high_label, description.\\n"
            "Rules:\\n"
            "- Mix two kinds of judgeable axes: content-presence axes and experiential tradeoff axes.\\n"
            "- Content-presence axes should capture whether some salient feature is absent, present, weak, or strong.\\n"
            "- Experiential tradeoff axes should capture how choosing one option can feel meaningfully different from choosing another.\\n"
            "- Every axis must be concrete enough that a human could place two movies on opposite sides from the description alone.\\n"
            "- Avoid generic buckets, analysis jargon, and labels that blend several unrelated ideas.\\n"
            "- Output JSON only."
        )
    return (
        "You are defining interpretable preference axes for pairwise choices.\\n\\n"
        f"DOMAIN: {domain}\\n"
        f"CHOICE CONTEXT: {choice_context}\\n\\n"
        f"Here are sample options ({len(sample_rows)}):\\n{examples}\\n\\n"
        f"Return exactly {n_dimensions} dimensions as a JSON array.\\n"
        "Each object must have: name, low_label, high_label, description.\\n"
        "Rules:\\n"
        "- Dimensions should explain why one option is preferred over another in a pairwise comparison.\\n"
        "- Each dimension should capture one clear tradeoff, not a bag of traits.\\n"
        "- Good axes are specific and interpretable, such as slow-burn vs propulsive, intimate vs epic, playful vs bleak.\\n"
        "- Avoid broad umbrella labels that could absorb many unrelated reasons.\\n"
        "- Keep names short and non-overlapping.\\n"
        "- Use labels grounded in these examples and in the actual decision a chooser would make.\\n"
        "- Output JSON only."
    )


def build_pair_prompt(domain, choice_context, a, b, active_dims, prompt_style):
    dims_text = "\n".join(dim_short_text(d) for d in active_dims)
    if prompt_style == "judgeable_axes":
        return (
            "You are comparing two options using axes that must be directly judgeable from the descriptions.\\n\\n"
            f"DOMAIN: {domain}\\n"
            f"CHOICE CONTEXT: {choice_context}\\n\\n"
            "Active dimensions:\\n"
            f"{dims_text}\\n\\n"
            "Option A:\\n"
            f"{a['text'][:900]}\\n\\n"
            "Option B:\\n"
            f"{b['text'][:900]}\\n\\n"
            "Return ONE JSON object only with keys used_dimension_ids, dimension_explanations, missed_differences.\\n"
            "Rules:\\n"
            "- Use a dimension only if the descriptions contain enough evidence to compare A vs B on it.\\n"
            "- If the descriptions reveal a sharper difference than the active dimensions capture, add it to missed_differences.\\n"
            "- Do not reward broad vague dimensions just because they can loosely fit many cases.\\n"
            "- Keep each reason <= 10 words.\\n"
            "- Include at most 5 used dimensions and at most 4 missed_differences.\\n"
            "- Output JSON only."
        )
    if prompt_style == "decision_framed":
        return (
            "You are analyzing how a real chooser would compare two options.\\n\\n"
            f"DOMAIN: {domain}\\n"
            f"CHOICE CONTEXT: {choice_context}\\n\\n"
            "Active dimensions:\\n"
            f"{dims_text}\\n\\n"
            "Option A:\\n"
            f"{a['text'][:900]}\\n\\n"
            "Option B:\\n"
            f"{b['text'][:900]}\\n\\n"
            "Return ONE JSON object only with keys used_dimension_ids, dimension_explanations, missed_differences.\\n"
            "Rules:\\n"
            "- Only use a dimension if it clearly captures a real chooser's tradeoff here.\\n"
            "- If the true difference is sharper than the available dimensions, put it in missed_differences instead of forcing a broad fit.\\n"
            "- Use only listed dimension ids.\\n"
            "- Keep each reason <= 10 words.\\n"
            "- Include at most 5 used dimensions and at most 4 missed_differences.\\n"
            "- missed_differences labels must be short concrete phrases.\\n"
            "- Output JSON only."
        )
    return (
        "You are analyzing why two options differ in a way relevant to preference.\\n\\n"
        f"DOMAIN: {domain}\\n"
        f"CHOICE CONTEXT: {choice_context}\\n\\n"
        "Active dimensions:\\n"
        f"{dims_text}\\n\\n"
        "Option A:\\n"
        f"{a['text'][:900]}\\n\\n"
        "Option B:\\n"
        f"{b['text'][:900]}\\n\\n"
        "Return ONE JSON object only (no markdown, no code fences) with keys:\\n"
        "- used_dimension_ids: list of integer ids from the active list that are reasonably used to explain A vs B differences\\n"
        "- dimension_explanations: list of objects {dimension_id, reason}\\n"
        "- missed_differences: list of objects {label, reason} for important differences not captured by active dimensions\\n"
        "Rules:\\n"
        "- Prefer dimensions that clearly explain a real chooser's tradeoff between these two options.\\n"
        "- Do not force-fit a broad dimension when a sharper uncovered difference is doing the real work.\\n"
        "- Use only listed dimension ids.\\n"
        "- If none fit, return empty used_dimension_ids.\\n"
        "- Keep each reason <= 12 words.\\n"
        "- Include at most 6 used dimensions and at most 4 missed_differences.\\n"
        "- missed_differences labels must be short noun phrases (2-5 words).\\n"
        "- Output JSON only."
    )


def build_merge_prompt(domain, choice_context, top_labels, n_candidates, active_dims, prompt_style):
    labels_text = "\n".join([f"- {lbl}: {cnt}" for lbl, cnt in top_labels])
    active_text = "\n".join(
        [f"- {d['name']} ({d['low_label']} <-> {d['high_label']})" for d in active_dims]
    )
    if prompt_style == "decision_framed":
        return (
            "You are repairing a set of comparison axes for a choice study.\\n\\n"
            f"DOMAIN: {domain}\\n"
            f"CHOICE CONTEXT: {choice_context}\\n\\n"
            "Current active dimensions:\\n"
            f"{active_text}\\n\\n"
            "Frequent missed labels in recent judgments:\\n"
            f"{labels_text}\\n\\n"
            f"Return up to {n_candidates} replacement axes as JSON array.\\n"
            "Each object must contain name, low_label, high_label, description, merged_labels, support_score.\\n"
            "Rules:\\n"
            "- Each replacement should represent one crisp chooser-facing tradeoff.\\n"
            "- Stay close to the missed-label evidence.\\n"
            "- Do not produce umbrella buckets or renamed versions of current axes.\\n"
            "- If labels do not support one clean axis, do not merge them.\\n"
            "- low_label and high_label must be clearly opposed and easy to judge from descriptions.\\n"
            "- Output JSON only."
        )
    if prompt_style == "judgeable_axes":
        return (
            "You are improving a set of chooser-facing comparison axes.\\n\\n"
            f"DOMAIN: {domain}\\n"
            f"CHOICE CONTEXT: {choice_context}\\n\\n"
            "Current active dimensions:\\n"
            f"{active_text}\\n\\n"
            "Frequent missed labels in recent judgments:\\n"
            f"{labels_text}\\n\\n"
            f"Return up to {n_candidates} replacement axes as JSON array.\\n"
            "Each object must contain name, low_label, high_label, description, merged_labels, support_score.\\n"
            "Rules:\\n"
            "- Each replacement must be directly judgeable from descriptions in pairwise comparisons.\\n"
            "- Each replacement must represent one narrow, interpretable contrast.\\n"
            "- Do not output broad abstractions, umbrella terms, or relabeled versions of current axes.\\n"
            "- Stay close to the evidence in merged_labels.\\n"
            "- If labels do not support one clear axis, do not merge them.\\n"
            "- Output JSON only."
        )
    return (
        "You are consolidating overrepresented missed-difference labels into better dimensions.\\n\\n"
        f"DOMAIN: {domain}\\n"
        f"CHOICE CONTEXT: {choice_context}\\n\\n"
        "Current active dimensions:\\n"
        f"{active_text}\\n\\n"
        "Frequent missed labels in recent judgments:\\n"
        f"{labels_text}\\n\\n"
        f"Return up to {n_candidates} replacement dimension candidates as JSON array.\\n"
        "Each object must contain:\\n"
        "- name\\n- low_label\\n- high_label\\n- description\\n"
        "- merged_labels (list of labels from the list above that this candidate combines)\\n"
        "- support_score (0 to 1, higher means should be added sooner)\\n"
        "Rules:\\n"
        "- Merge semantically overlapping labels.\\n"
        "- Prefer concrete bipolar preference contrasts over umbrella buckets.\\n"
        "- A good axis should feel like one interpretable thing a person could clearly trade off when choosing.\\n"
        "- Do not create a candidate that overlaps an active dimension just by renaming it or broadening it.\\n"
        "- Each candidate should merge labels into one crisp latent factor, not a bag of unrelated traits.\\n"
        "- low_label and high_label must be semantically opposed and specific.\\n"
        "- The axis name and poles should stay close to the evidence in merged_labels rather than drifting into an abstract umbrella.\\n"
        "- If the labels do not support one clean axis, do not merge them.\\n"
        "- Output JSON only."
    )


def sanitize_dimensions(raw_dims, n_dimensions):
    out = []
    for d in raw_dims:
        if len(out) >= n_dimensions:
            break
        name = str(d.get("name", "")).strip()
        low = str(d.get("low_label", "")).strip()
        high = str(d.get("high_label", "")).strip()
        desc = str(d.get("description", "")).strip()
        if not (name and low and high):
            continue
        out.append(
            {
                "name": name,
                "low_label": low,
                "high_label": high,
                "description": desc or "Preference-relevant contrast.",
                "source": "seed",
            }
        )
    if len(out) != n_dimensions:
        raise ValueError(f"Expected {n_dimensions} valid initial dimensions, got {len(out)}")
    return out


def coerce_int_ids(vals):
    out = []
    for v in vals or []:
        try:
            out.append(int(v))
        except Exception:
            continue
    return out


def _rng_to_str(rng: random.Random) -> str:
    return base64.b64encode(pickle.dumps(rng.getstate())).decode("ascii")


def _rng_from_str(rng: random.Random, s: str):
    rng.setstate(pickle.loads(base64.b64decode(s.encode("ascii"))))


def progress_rows_for_judgment(judgment_index, active_dimensions):
    ranked = sorted(
        active_dimensions,
        key=lambda d: ((d.get("used_count", 0) / max(1, d.get("active_judgments", 0))), d.get("used_count", 0)),
        reverse=True,
    )
    rows = []
    for rank, d in enumerate(ranked, 1):
        active_j = d.get("active_judgments", 0)
        used = d.get("used_count", 0)
        rows.append(
            {
                "judgment_index": judgment_index,
                "rank": rank,
                "dimension_id": d["dimension_id"],
                "name": d["name"],
                "source": d.get("source", "unknown"),
                "active_judgments": active_j,
                "used_count": used,
                "usage_rate": round((used / active_j) if active_j > 0 else 0.0, 4),
            }
        )
    return rows


def normalized_name_tokens(name: str):
    tokens = [t for t in re.split(r"[^a-z0-9]+", (name or "").lower()) if t]
    stop = {"and", "or", "the", "of", "vs", "with", "without"}
    return {t for t in tokens if t not in stop}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def axis_signature_tokens(axis: dict) -> set[str]:
    parts = [
        axis.get("name", ""),
        axis.get("description", ""),
        axis.get("low_label", ""),
        axis.get("high_label", ""),
    ]
    tokens = set()
    for part in parts:
        tokens |= normalized_name_tokens(part)
    return tokens


def merged_label_token_sets(axis: dict) -> list[set[str]]:
    token_sets = []
    for lbl in axis.get("merged_labels", []) or []:
        toks = normalized_name_tokens(lbl)
        if toks:
            token_sets.append(toks)
    return token_sets


def merged_label_union_tokens(axis: dict) -> set[str]:
    out = set()
    for toks in merged_label_token_sets(axis):
        out |= toks
    return out


def evidence_alignment_ratio(axis: dict) -> float:
    sig = axis_signature_tokens(axis)
    evidence = merged_label_union_tokens(axis)
    if not evidence or not sig:
        return 1.0
    return len(sig & evidence) / len(sig)


def merged_label_cohesion(axis: dict) -> float:
    token_sets = merged_label_token_sets(axis)
    if len(token_sets) <= 1:
        return 1.0
    scores = []
    for i in range(len(token_sets)):
        for j in range(i + 1, len(token_sets)):
            scores.append(jaccard(token_sets[i], token_sets[j]))
    return sum(scores) / len(scores) if scores else 1.0


def is_clear_axis_candidate(candidate: dict, active_dimensions: list[dict]) -> bool:
    name = candidate.get("name", "").strip()
    low = candidate.get("low_label", "").strip()
    high = candidate.get("high_label", "").strip()
    desc = candidate.get("description", "").strip()
    merged_labels = candidate.get("merged_labels", [])

    if not (name and low and high):
        return False
    if low.lower() == high.lower():
        return False

    sig = axis_signature_tokens(candidate)
    name_tokens = normalized_name_tokens(name)
    merged_token_set = set()
    for lbl in merged_labels:
        merged_token_set |= normalized_name_tokens(lbl)
    alignment = evidence_alignment_ratio(candidate)
    cohesion = merged_label_cohesion(candidate)

    if len(sig) < 3:
        return False
    if len(merged_labels) >= 2 and alignment < 0.2:
        return False
    if len(merged_labels) >= 3 and cohesion == 0.0 and alignment < 0.34:
        return False
    if len(name_tokens) <= 1 and len(merged_token_set) >= 3:
        return False

    for active in active_dimensions:
        active_sig = axis_signature_tokens(active)
        if jaccard(sig, active_sig) >= 0.4:
            return False

    return True


def semantically_duplicate_axis(candidate: dict, selected: list[dict]) -> bool:
    cand_name = normalized_name_tokens(candidate["name"])
    cand_sig = axis_signature_tokens(candidate)
    for prev in selected:
        prev_name = normalized_name_tokens(prev["name"])
        prev_sig = axis_signature_tokens(prev)
        if jaccard(cand_name, prev_name) >= 0.5:
            return True
        if jaccard(cand_sig, prev_sig) >= 0.4:
            return True
        if jaccard(merged_label_union_tokens(candidate), merged_label_union_tokens(prev)) >= 0.34:
            return True
    return False


def select_final_axes(dim_history, target_n):
    scored = []
    for d in dim_history:
        active_j = d.get("active_judgments", 0)
        used = d.get("used_count", 0)
        usage_rate = (used / active_j) if active_j > 0 else 0.0
        maturity = min(1.0, active_j / 20.0)
        alignment = evidence_alignment_ratio(d)
        cohesion = merged_label_cohesion(d)
        specificity_multiplier = 0.7 + (0.3 * alignment)
        if len((d.get("merged_labels", []) or [])) >= 2:
            specificity_multiplier *= 0.8 + (0.2 * cohesion)
        source_multiplier = 0.95 if d.get("source") == "merged_missed" else 1.0
        score = (
            usage_rate
            * (0.5 + 0.5 * maturity)
            * math.log1p(used + 1)
            * specificity_multiplier
            * source_multiplier
        )
        scored.append(
            {
                "dimension_id": d["dimension_id"],
                "name": d["name"],
                "low_label": d["low_label"],
                "high_label": d["high_label"],
                "description": d.get("description", ""),
                "source": d.get("source", "unknown"),
                "active_judgments": active_j,
                "used_count": used,
                "usage_rate": round(usage_rate, 4),
                "evidence_alignment_ratio": round(alignment, 4),
                "merged_label_cohesion": round(cohesion, 4),
                "selection_score": round(score, 4),
            }
        )

    scored.sort(key=lambda x: (x["selection_score"], x["usage_rate"], x["used_count"]), reverse=True)
    selected = []
    for cand in scored:
        if cand["active_judgments"] < 10 or cand["used_count"] < 4:
            continue
        if cand["evidence_alignment_ratio"] < 0.2 and cand["usage_rate"] < 0.75:
            continue
        if semantically_duplicate_axis(cand, selected):
            continue
        selected.append(cand)
        if len(selected) >= target_n:
            break

    if len(selected) < target_n:
        seen = {d["dimension_id"] for d in selected}
        for cand in scored:
            if cand["dimension_id"] in seen:
                continue
            selected.append(cand)
            if len(selected) >= target_n:
                break
    return selected, scored


def save_checkpoint(output_dir: Path, state: dict):
    save_json(output_dir / "checkpoint_state.json", state)


def load_checkpoint(output_dir: Path):
    p = output_dir / "checkpoint_state.json"
    if not p.exists():
        return None
    return load_json(p)


def summarize(dim_history, active_dimensions, judgment_rows, switches, missed_counter, progress_rows, error_rows, out_dir: Path, config, args):
    active_ids = {d["dimension_id"] for d in active_dimensions}
    final_axes, all_scored_axes = select_final_axes(dim_history, args.n_dimensions)
    dim_rows = []
    for d in dim_history:
        dim_id = d["dimension_id"]
        active_j = d.get("active_judgments", 0)
        used = d.get("used_count", 0)
        usage_rate = (used / active_j) if active_j > 0 else 0.0
        dim_rows.append(
            {
                "dimension_id": dim_id,
                "name": d["name"],
                "source": d.get("source", "unknown"),
                "active_now": dim_id in active_ids,
                "introduced_at_judgment": d.get("introduced_at_judgment", 0),
                "retired_at_judgment": d.get("retired_at_judgment", ""),
                "active_judgments": active_j,
                "used_count": used,
                "usage_rate": round(usage_rate, 4),
                "selected_for_final_axes": any(ax["dimension_id"] == dim_id for ax in final_axes),
                "times_swapped_out": d.get("times_swapped_out", 0),
            }
        )
    dim_rows.sort(key=lambda r: (not r["active_now"], -r["usage_rate"], -r["used_count"]))

    missed_rows = [{"label": lbl, "count": cnt} for lbl, cnt in missed_counter.most_common()]

    write_csv(out_dir / "dimension_performance.csv", dim_rows)
    write_csv(out_dir / "missed_labels.csv", missed_rows)
    write_csv(out_dir / "judgments.csv", judgment_rows)
    write_csv(out_dir / "judgment_progress.csv", progress_rows)
    write_csv(out_dir / "switch_log.csv", switches)
    write_csv(out_dir / "errors.csv", error_rows)
    write_csv(out_dir / "final_axes.csv", final_axes)
    save_json(out_dir / "final_axes.json", {"axes": final_axes, "all_scored_axes": all_scored_axes})

    summary_lines = []
    summary_lines.append("# Adaptive Dimension Discovery Summary")
    summary_lines.append("")
    summary_lines.append("## Run setup")
    summary_lines.append("")
    summary_lines.append(f"- Domain: {config.get('domain', 'unknown')}")
    summary_lines.append(f"- Choice context: {config.get('choice_context', '')}")
    summary_lines.append(f"- Subset size: {args.subset_size}")
    summary_lines.append(f"- Seed sample size: {args.seed_sample_size}")
    summary_lines.append(f"- Initial dimensions: {args.n_dimensions}")
    summary_lines.append(f"- Total judgments completed: {len(judgment_rows)}/{args.judgments_total}")
    summary_lines.append(f"- Switch interval: {args.switch_interval}")
    summary_lines.append(f"- Max swaps / interval: {args.max_swaps_per_interval}")
    summary_lines.append(f"- Rate limit used: {args.rate_limit_per_minute} requests/min")
    summary_lines.append("")

    summary_lines.append("## Final axes")
    summary_lines.append("")
    for d in final_axes:
        summary_lines.append(
            f"- #{d['dimension_id']} {d['name']} ({d['low_label']} <-> {d['high_label']}), "
            f"usage_rate={d['usage_rate']:.4f}, used={d['used_count']}"
        )
    summary_lines.append("")

    summary_lines.append("## Top dimension usefulness")
    summary_lines.append("")
    summary_lines.append("| dimension_id | name | source | active_judgments | used_count | usage_rate |")
    summary_lines.append("|---|---|---|---:|---:|---:|")
    for r in sorted(dim_rows, key=lambda x: (-x["usage_rate"], -x["used_count"]))[:15]:
        summary_lines.append(
            f"| {r['dimension_id']} | {r['name']} | {r['source']} | {r['active_judgments']} | {r['used_count']} | {r['usage_rate']:.4f} |"
        )
    summary_lines.append("")

    summary_lines.append("## Top overrepresented missed labels")
    summary_lines.append("")
    for lbl, cnt in missed_counter.most_common(20):
        summary_lines.append(f"- {lbl}: {cnt}")
    summary_lines.append("")

    summary_lines.append("## Switch events")
    summary_lines.append("")
    if switches:
        for s in switches:
            summary_lines.append(
                f"- Judgment {s['judgment_index']}: swapped out #{s['removed_dimension_id']} ({s['removed_name']}) "
                f"for #{s['added_dimension_id']} ({s['added_name']}); candidate_support={s['candidate_support_count']}"
            )
    else:
        summary_lines.append("- No swaps were performed.")

    (out_dir / "summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")


def main():
    args = parse_args()
    load_dotenv()

    config = load_json(Path(args.config))
    run_name = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) if args.output_dir else (DEFAULT_OUTPUT_ROOT / run_name)
    output_dir.mkdir(parents=True, exist_ok=True)

    save_json(output_dir / "run_config.json", {**config, **vars(args)})

    rng = random.Random(args.seed)
    limiter = RateLimiter(requests_per_minute=args.rate_limit_per_minute)
    client = make_client(args.base_url, args.api_key, args.provider)

    domain = config.get("domain", "wines")
    choice_context = config.get("choice_context", "A person compares two options.")

    # Resume or initialize
    checkpoint = load_checkpoint(output_dir) if args.resume else None
    if checkpoint:
        print("[resume] Loaded checkpoint state", flush=True)
        items = checkpoint["items"]
        seed_items = checkpoint["seed_items"]
        active_dimensions = checkpoint["active_dimensions"]
        all_dimensions = checkpoint["all_dimensions"]
        switches = checkpoint["switches"]
        judgment_rows = checkpoint["judgment_rows"]
        progress_rows = checkpoint.get("progress_rows", [])
        error_rows = checkpoint.get("error_rows", [])
        next_dim_id = int(checkpoint["next_dim_id"])
        missed_counter = Counter(checkpoint.get("missed_counter", {}))
        _rng_from_str(rng, checkpoint["rng_state"])
    else:
        items = load_items(config, subset_size=args.subset_size, seed=args.seed)
        if len(items) < max(2, args.seed_sample_size):
            raise ValueError(f"Not enough items in sampled subset: {len(items)}")

        write_csv(output_dir / "subset_items.csv", items)

        seed_items = rng.sample(items, args.seed_sample_size)
        write_csv(output_dir / "seed_items.csv", seed_items)

        seed_prompt = build_seed_prompt(domain, choice_context, seed_items, args.n_dimensions, args.prompt_style)
        raw_dims = chat_json(
            client,
            args.model,
            seed_prompt,
            timeout=args.request_timeout_seconds,
            retries=args.max_retries,
            limiter=limiter,
            max_tokens=900,
        )
        if not isinstance(raw_dims, list):
            raise ValueError("Seed dimension response must be a JSON array")

        seed_dimensions = sanitize_dimensions(raw_dims, args.n_dimensions)

        active_dimensions = []
        all_dimensions = []
        next_dim_id = 1
        for d in seed_dimensions:
            dim = {
                "dimension_id": next_dim_id,
                "name": d["name"],
                "low_label": d["low_label"],
                "high_label": d["high_label"],
                "description": d["description"],
                "source": "seed",
                "introduced_at_judgment": 0,
                "active_judgments": 0,
                "used_count": 0,
                "times_swapped_out": 0,
            }
            active_dimensions.append(dim)
            all_dimensions.append(dim)
            next_dim_id += 1

        save_json(output_dir / "initial_dimensions.json", {"dimensions": active_dimensions})

        switches = []
        judgment_rows = []
        progress_rows = []
        error_rows = []
        missed_counter = Counter()

    def dim_map():
        return {d["dimension_id"]: d for d in all_dimensions}

    def persist_state():
        state = {
            "items": items,
            "seed_items": seed_items,
            "active_dimensions": active_dimensions,
            "all_dimensions": all_dimensions,
            "next_dim_id": next_dim_id,
            "switches": switches,
            "judgment_rows": judgment_rows,
            "progress_rows": progress_rows,
            "error_rows": error_rows,
            "missed_counter": dict(missed_counter),
            "rng_state": _rng_to_str(rng),
        }
        save_checkpoint(output_dir, state)

        # Keep continuously updated tables for monitoring
        summarize(
            dim_history=all_dimensions,
            active_dimensions=active_dimensions,
            judgment_rows=judgment_rows,
            switches=switches,
            missed_counter=missed_counter,
            progress_rows=progress_rows,
            error_rows=error_rows,
            out_dir=output_dir,
            config=config,
            args=args,
        )

    start_j = len(judgment_rows) + 1
    if start_j > args.judgments_total:
        print("[resume] Already complete based on checkpoint", flush=True)
        save_json(output_dir / "final_active_dimensions.json", {"dimensions": active_dimensions})
        save_json(output_dir / "all_dimensions_history.json", {"dimensions": all_dimensions})
        persist_state()
        print(f"[done] Outputs written to: {output_dir}")
        return

    consecutive_failures = 0
    j = start_j

    while j <= args.judgments_total:
        try:
            a, b = rng.sample(items, 2)
            prompt = build_pair_prompt(domain, choice_context, a, b, active_dimensions, args.prompt_style)
            raw_text = chat(
                client,
                args.model,
                prompt,
                timeout=args.request_timeout_seconds,
                retries=args.max_retries,
                limiter=limiter,
                max_tokens=600,
            )
            raw = parse_pair_response(raw_text)

            used_ids = []
            missed = []
            explanations = []
            if isinstance(raw, dict):
                used_ids = coerce_int_ids(raw.get("used_dimension_ids", []))
                explanations = raw.get("dimension_explanations", []) if isinstance(raw.get("dimension_explanations", []), list) else []
                missed = raw.get("missed_differences", []) if isinstance(raw.get("missed_differences", []), list) else []

            active_ids = {d["dimension_id"] for d in active_dimensions}
            used_ids = sorted(set([i for i in used_ids if i in active_ids]))

            id_to_dim = dim_map()
            for d in active_dimensions:
                id_to_dim[d["dimension_id"]]["active_judgments"] += 1
            for dim_id in used_ids:
                id_to_dim[dim_id]["used_count"] += 1

            normalized_missed = []
            for m in missed:
                if not isinstance(m, dict):
                    continue
                lbl = normalize_label(str(m.get("label", "")))
                reason = str(m.get("reason", "")).strip()
                if not lbl:
                    continue
                normalized_missed.append({"label": lbl, "reason": reason})
                missed_counter[lbl] += 1

            judgment_rows.append(
                {
                    "judgment_index": j,
                    "item_a_id": a["item_id"],
                    "item_b_id": b["item_id"],
                    "used_dimension_ids": ";".join(str(x) for x in used_ids),
                    "used_dimension_count": len(used_ids),
                    "missed_labels": ";".join(x["label"] for x in normalized_missed),
                    "raw_dimension_explanations": json.dumps(explanations, ensure_ascii=True),
                    "raw_missed_differences": json.dumps(normalized_missed, ensure_ascii=True),
                }
            )

            progress_rows.extend(progress_rows_for_judgment(j, active_dimensions))

            if j % args.switch_interval == 0:
                window = judgment_rows[-args.switch_interval:]
                window_usage = Counter()
                window_missed = Counter()
                for row in window:
                    ids = [int(x) for x in row["used_dimension_ids"].split(";") if x.strip()]
                    for i in ids:
                        window_usage[i] += 1
                    labels = [x.strip() for x in row["missed_labels"].split(";") if x.strip()]
                    for lbl in labels:
                        window_missed[lbl] += 1

                id_to_dim = dim_map()
                low_dims = sorted(
                    active_dimensions,
                    key=lambda d: (
                        (window_usage.get(d["dimension_id"], 0) / max(1, args.switch_interval)),
                        (id_to_dim[d["dimension_id"]]["used_count"] / max(1, id_to_dim[d["dimension_id"]]["active_judgments"])),
                        id_to_dim[d["dimension_id"]]["used_count"],
                    ),
                )

                top_labels = window_missed.most_common(15)
                candidates = []
                if top_labels:
                    merge_prompt = build_merge_prompt(
                        domain,
                        choice_context,
                        top_labels,
                        n_candidates=max(args.max_swaps_per_interval * 2, 4),
                        active_dims=active_dimensions,
                        prompt_style=args.prompt_style,
                    )
                    raw_candidates = chat_json(
                        client,
                        args.model,
                        merge_prompt,
                        timeout=args.request_timeout_seconds,
                        retries=args.max_retries,
                        limiter=limiter,
                        max_tokens=800,
                    )
                    if isinstance(raw_candidates, list):
                        for c in raw_candidates:
                            if not isinstance(c, dict):
                                continue
                            name = str(c.get("name", "")).strip()
                            low = str(c.get("low_label", "")).strip()
                            high = str(c.get("high_label", "")).strip()
                            desc = str(c.get("description", "")).strip()
                            merged = [normalize_label(str(x)) for x in c.get("merged_labels", []) if str(x).strip()]
                            merged = [x for x in merged if x]
                            if not (name and low and high):
                                continue
                            support_count = sum(window_missed.get(lbl, 0) for lbl in merged)
                            try:
                                support_score = float(c.get("support_score", 0.0))
                            except Exception:
                                support_score = 0.0
                            candidate = {
                                "name": name,
                                "low_label": low,
                                "high_label": high,
                                "description": desc or "Merged from frequent missed differences.",
                                "merged_labels": merged,
                                "support_count": support_count,
                                "support_score": max(0.0, min(1.0, support_score)),
                            }
                            if not is_clear_axis_candidate(candidate, active_dimensions):
                                continue
                            candidates.append(candidate)

                candidates.sort(
                    key=lambda c: (
                        c["support_count"] + (c["support_score"] * float(args.switch_interval) * 0.25),
                        c["support_score"],
                        c["support_count"],
                    ),
                    reverse=True,
                )
                save_json(
                    output_dir / f"merge_candidates_after_{j}.json",
                    {
                        "judgment_index": j,
                        "top_window_missed_labels": [{"label": l, "count": c} for l, c in top_labels],
                        "candidates": candidates,
                    },
                )

                swaps_done = 0
                for idx in range(min(len(low_dims), len(candidates), args.max_swaps_per_interval)):
                    low_d = low_dims[idx]
                    cand = candidates[idx]
                    if cand["support_count"] <= 0:
                        continue

                    removed_id = low_d["dimension_id"]
                    low_d["retired_at_judgment"] = j
                    low_d["times_swapped_out"] = low_d.get("times_swapped_out", 0) + 1

                    new_dim = {
                        "dimension_id": next_dim_id,
                        "name": cand["name"],
                        "low_label": cand["low_label"],
                        "high_label": cand["high_label"],
                        "description": cand["description"],
                        "merged_labels": cand.get("merged_labels", []),
                        "source": "merged_missed",
                        "introduced_at_judgment": j,
                        "active_judgments": 0,
                        "used_count": 0,
                        "times_swapped_out": 0,
                    }

                    replace_pos = [k for k, d in enumerate(active_dimensions) if d["dimension_id"] == removed_id]
                    if not replace_pos:
                        continue

                    active_dimensions[replace_pos[0]] = new_dim
                    all_dimensions.append(new_dim)

                    switches.append(
                        {
                            "judgment_index": j,
                            "removed_dimension_id": removed_id,
                            "removed_name": low_d["name"],
                            "added_dimension_id": next_dim_id,
                            "added_name": new_dim["name"],
                            "candidate_support_count": cand["support_count"],
                            "candidate_support_score": round(cand["support_score"], 4),
                            "merged_labels": ";".join(cand.get("merged_labels", [])),
                        }
                    )

                    next_dim_id += 1
                    swaps_done += 1

                save_json(
                    output_dir / f"active_dimensions_after_{j}.json",
                    {
                        "judgment_index": j,
                        "active_dimensions": active_dimensions,
                        "window_usage": dict(window_usage),
                        "swaps_done": swaps_done,
                    },
                )

            if j % 10 == 0 or j == args.judgments_total:
                print(f"[progress] {j}/{args.judgments_total} judgments complete", flush=True)

            consecutive_failures = 0
            persist_state()
            j += 1

        except Exception as e:
            consecutive_failures += 1
            err_text = str(e)
            error_rows.append(
                {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "next_judgment_index": j,
                    "consecutive_failures": consecutive_failures,
                    "error": err_text[:2000],
                }
            )
            print(f"[warn] judgment {j} failed ({consecutive_failures} consecutive): {err_text}", flush=True)
            persist_state()

            if consecutive_failures >= args.max_consecutive_failures:
                raise RuntimeError(
                    f"Exceeded max consecutive failures ({args.max_consecutive_failures}) at judgment {j}."
                )

            sleep_s = min(args.retry_sleep_seconds * consecutive_failures, 300)
            time.sleep(sleep_s)

    save_json(output_dir / "final_active_dimensions.json", {"dimensions": active_dimensions})
    save_json(output_dir / "all_dimensions_history.json", {"dimensions": all_dimensions})
    persist_state()
    print(f"[done] Outputs written to: {output_dir}")


if __name__ == "__main__":
    main()
