"""
LLM-Persona Preference Learning Simulation (revamped to match the 3 final
experimental conditions, with checkpoint-based learning curves).

LLM personas replace the synthetic weight-vec users. Each persona:
  1. Makes binary choices on a held-out test set (ground truth).
  2. For each of 3 conditions, runs through T training trials, providing
     per-dim feedback when the condition asks for it (mirrors the actual
     web-interface UI). The persona's choices and feedback are collected
     ONCE then cached — checkpoint refits don't trigger new LLM calls.
  3. Refit at every checkpoint t ∈ checkpoints (default: every trial) on
     the prefix [0:t]:
        standard       — kernel logistic in dual form
        feedback-adj   — K-dim primal logistic on Ũ = Λ ⊙ U with a
                         zero-centered G-shape prior
     Compute held-out test accuracy + log-likelihood at each checkpoint.
  4. Final-T metrics → predicted_dv.png + summary.md;
     all checkpoints → learning_curves.{csv,png}.
  5. Predicted experimental DV: P(participant prefers K-dim summary over
     standard summary) ≈ σ(τ · ΔLL) on the held-out test set.

Standalone script — does NOT import run_simulation.py.
"""

import argparse
import itertools
import json
import math
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from openai import OpenAI
from scipy.stats import wilcoxon


CONDITIONS = ["choice_only", "inference_affirm", "inference_categories"]
DEFAULT_MULTS = np.array([-1.5, -1.0, 0.0, 1.0, 1.5])
DEFAULT_CATEGORY_LABELS = ["prefer to skip", "aren't into", "are indifferent to", "like", "love"]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data(embeddings_parquet, bt_scores_csv, directions_npz, option_id_column):
    parquet_df = pd.read_parquet(embeddings_parquet)
    parquet_df["option_id"] = parquet_df[option_id_column].astype(str)
    parquet_df = parquet_df.sort_values("option_id").reset_index(drop=True)
    option_ids = parquet_df["option_id"].tolist()
    embeddings = np.stack(parquet_df["embedding"].apply(np.array).values).astype(np.float64)

    bt_df = pd.read_csv(bt_scores_csv)
    bt_df["option_id"] = bt_df["option_id"].astype(str)
    dim_info = (bt_df[["dimension_id", "dimension_name"]]
                .drop_duplicates().sort_values("dimension_id"))
    dim_names = dim_info["dimension_name"].tolist()
    dim_ids = dim_info["dimension_id"].tolist()
    bt_pivot = bt_df.pivot(index="option_id", columns="dimension_id", values="bt_score")
    bt_pivot = bt_pivot[dim_ids].loc[option_ids]
    bt_scores = bt_pivot.values.astype(np.float64)

    npz = np.load(directions_npz)
    V_raw = npz["directions_raw"].astype(np.float64)
    mu = npz["mean_embedding"].astype(np.float64)
    norms = np.linalg.norm(V_raw, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    V = V_raw / norms

    G = V @ V.T

    print(f"  Gram matrix condition number: {np.linalg.cond(G):.1f}")
    print(f"  Max inter-dimension correlation: {np.abs(G - np.eye(G.shape[0])).max():.3f}")

    return embeddings, bt_scores, V, G, mu, option_ids, dim_names


def load_dimensions(path):
    with open(path) as f:
        return json.load(f)["dimensions"]


# Fields that are "liftable" — when both options of a pair share them, they
# get rendered once as shared context above the option cards (matches the web
# interface's LIFTABLE_FIELDS in index.html, line 241).
LIFTABLE_FIELDS = ("situation",)


def _render_template_minus_fields(template, row_dict, blank_fields):
    """Render the option template, blanking the listed fields and dropping
    the now-empty 'Key: ' lines so they don't leave dangling text."""
    safe = {k: v for k, v in row_dict.items()}
    for f in blank_fields:
        safe[f] = ""
    try:
        text = template.format(**safe)
    except KeyError:
        text = " | ".join(f"{k}: {v}" for k, v in row_dict.items()
                          if k not in blank_fields and pd.notna(v) and str(v).strip())
    # Strip lines whose value collapsed to empty (e.g., "Situation: ").
    keep = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        # A line like "Situation:" or "Situation: " is a blanked-out field.
        if s.endswith(":") or any(s == f"{f.title()}:" or s == f"{f}:" for f in blank_fields):
            continue
        keep.append(line)
    return "\n".join(keep).strip()


def load_option_descriptions(csv_path, template_path, id_column):
    """Load per-option text. Returns (descriptions, raw_rows, template_str).

    `descriptions[oid]` is the fully-rendered template (situation + action +
    consequence for dilemmas, etc.) — used when no shared-context lifting is
    needed (movies, wines, or any random-pair sampling).

    `raw_rows[oid]` is the CSV row as a dict; used to build lifted prompts
    when --predefined-pairs is set, by detecting fields the two options
    share and rendering them once as shared context.
    """
    df = pd.read_csv(csv_path)
    template = Path(template_path).read_text().strip()
    descriptions = {}
    raw_rows = {}
    for _, row in df.iterrows():
        oid = str(row[id_column])
        d = row.to_dict()
        raw_rows[oid] = d
        try:
            text = template.format(**d)
        except KeyError:
            parts = [f"{k}: {v}" for k, v in d.items()
                     if k != id_column and pd.notna(v) and str(v).strip()]
            text = " | ".join(parts)
        descriptions[oid] = text
    return descriptions, raw_rows, template


def lifted_pair_text(raw_a, raw_b, template, liftable_fields=LIFTABLE_FIELDS):
    """If raw_a and raw_b share any liftable fields with identical non-empty
    values, return (shared_text, option_a_text, option_b_text) where the
    shared field is rendered once and stripped from each option.

    If nothing is shared, returns (None, None, None) and caller falls back to
    the unlifted prompt.
    """
    shared = []
    for f in liftable_fields:
        va, vb = raw_a.get(f), raw_b.get(f)
        if (va is not None and vb is not None and pd.notna(va) and pd.notna(vb)
                and str(va).strip() and str(va) == str(vb)):
            shared.append(f)
    if not shared:
        return None, None, None
    shared_text = "\n".join(f"{f.capitalize()}: {raw_a[f]}" for f in shared)
    a_text = _render_template_minus_fields(template, raw_a, shared)
    b_text = _render_template_minus_fields(template, raw_b, shared)
    return shared_text, a_text, b_text


def load_predefined_pairs(json_path, option_ids):
    """Load predefined pairs (e.g., dilemma pairs from predefined_pairs.json)
    and convert option_ids to embedding indices.

    Returns: list of (idx_a, idx_b) tuples. Pairs whose ids aren't in the
    embedding pool are dropped with a warning.
    """
    with open(json_path) as f:
        pairs_raw = json.load(f)
    id_to_idx = {oid: i for i, oid in enumerate(option_ids)}
    pairs = []
    dropped = 0
    for p in pairs_raw:
        a, b = str(p["option_a_id"]), str(p["option_b_id"])
        if a in id_to_idx and b in id_to_idx:
            pairs.append((id_to_idx[a], id_to_idx[b]))
        else:
            dropped += 1
    if dropped:
        print(f"  [predefined-pairs] dropped {dropped} pairs missing from pool")
    print(f"  [predefined-pairs] using {len(pairs)} pairs from {json_path}")
    return pairs


# ---------------------------------------------------------------------------
# LLM client + caching
# ---------------------------------------------------------------------------

PROVIDER_DEFAULTS = {
    "openai": {"base_url": "https://api.openai.com/v1", "env_key": "OPENAI_API_KEY"},
    "anthropic": {"base_url": "https://api.anthropic.com/v1", "env_key": "ANTHROPIC_API_KEY"},
}


class ClientPool:
    def __init__(self, clients):
        self._cycle = itertools.cycle(clients)
        self._lock = threading.Lock()
        self.size = len(clients)

    def next(self):
        with self._lock:
            return next(self._cycle)


def make_client(base_url, api_key, provider="local"):
    defaults = PROVIDER_DEFAULTS.get(provider, {})
    base_url = base_url or defaults.get("base_url")
    api_key = api_key or os.environ.get(defaults.get("env_key", ""), "")
    if not base_url:
        raise ValueError("Missing --base-url (required for provider='local')")
    if not api_key:
        env_hint = defaults.get("env_key", "")
        raise ValueError("Missing --api-key" + (f" (or set {env_hint})" if env_hint else ""))
    return OpenAI(base_url=base_url, api_key=api_key)


def make_client_or_pool(base_url, api_key, provider="local"):
    if base_url and "," in base_url:
        urls = [u.strip() for u in base_url.split(",") if u.strip()]
        clients = [make_client(url, api_key, provider) for url in urls]
        print(f"[client] Round-robin pool with {len(clients)} endpoints", flush=True)
        return ClientPool(clients)
    return make_client(base_url, api_key, provider)


def _raw_llm_call(client, model, prompt, temperature, timeout, retries, max_tokens=1024):
    is_pool = isinstance(client, ClientPool)
    pool_size = client.size if is_pool else 1
    max_attempts = max(retries, pool_size)
    last_err = None
    for attempt in range(1, max_attempts + 1):
        resolved = client.next() if is_pool else client
        try:
            resp = resolved.chat.completions.create(
                model=model, temperature=temperature, max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
                timeout=timeout,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            text = (resp.choices[0].message.content or "").strip()
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
            if "<think>" in text and "</think>" not in text:
                text = text[:text.index("<think>")].strip()
            return text
        except Exception as e:
            last_err = e
            is_conn = "Connection" in type(e).__name__
            if attempt < max_attempts and not is_conn:
                time.sleep(min(attempt, 3))
    raise last_err


class LLMClient:
    def __init__(self, client, cache_path=None, timeout=120, retries=3):
        self.client = client
        self.timeout = timeout
        self.retries = retries
        self.cache_path = cache_path
        self._cache = {}
        self._cache_lock = threading.Lock()
        if cache_path and cache_path.exists():
            with open(cache_path) as f:
                self._cache = json.load(f)

    def call(self, model, prompt, temperature=0.0, cache_key=None, max_tokens=512):
        if cache_key:
            with self._cache_lock:
                if cache_key in self._cache:
                    return self._cache[cache_key]
        text = _raw_llm_call(self.client, model, prompt, temperature,
                             self.timeout, self.retries, max_tokens)
        if cache_key:
            with self._cache_lock:
                self._cache[cache_key] = text
        return text

    def save_cache(self):
        if self.cache_path:
            with self._cache_lock:
                with open(self.cache_path, "w") as f:
                    json.dump(self._cache, f, indent=1)


# ---------------------------------------------------------------------------
# Persona generation
# ---------------------------------------------------------------------------

def generate_personas(client, model, num_personas, domain="movies", choice_context=""):
    context_line = f" Context: {choice_context}" if choice_context else ""
    prompt = f"""You are helping design a psychology experiment about preferences in the domain of {domain}.{context_line}

Generate {num_personas} diverse, realistic personas of people who have opinions in this domain. Each persona should be a short paragraph (3-5 sentences) describing the person's background, personality, and relevant preferences in enough detail that you could predict which of two options they'd prefer.

The personas should collectively represent meaningful variation in preferences. Include people who differ in age, background, and taste — not just surface-level preferences, but also deeper values, priorities, and decision-making styles.

Do NOT make the personas cartoonish or one-dimensional. Real people have nuanced, sometimes contradictory tastes.

Return each persona in this format:

===PERSONA===
name: <first name and age>
description: <3-5 sentence description>"""
    text = client.call(model, prompt, temperature=0.7,
                       cache_key="persona_generation", max_tokens=4096)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if "<think>" in text and "</think>" not in text:
        text = text[:text.index("<think>")].strip()
    personas = []
    for block in text.split("===PERSONA==="):
        block = block.strip()
        if not block:
            continue
        name_match = re.search(r"name:\s*(.+)", block)
        desc_match = re.search(r"description:\s*(.+)", block, re.DOTALL)
        if name_match and desc_match:
            personas.append({"id": len(personas),
                             "name": name_match.group(1).strip(),
                             "description": desc_match.group(1).strip()})
    if len(personas) < num_personas:
        print(f"  Warning: requested {num_personas} but parsed {len(personas)}")
    return personas[:num_personas]


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------

def parse_json_response(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if "<think>" in text and "</think>" not in text:
        text = text[:text.index("<think>")].strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        return json.loads(fence_match.group(1))
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass
    partial = {}
    for m in re.finditer(r'"(\w+)"\s*:\s*"((?:[^"\\]|\\.)*)"', text):
        partial[m.group(1)] = m.group(2)
    for m in re.finditer(r'"(\w+)"\s*:\s*(-?\d+)', text):
        partial[m.group(1)] = int(m.group(2))
    if partial:
        return partial
    raise ValueError(f"Could not parse JSON: {text[:200]}")


# ---------------------------------------------------------------------------
# Choice prompt + parser
# ---------------------------------------------------------------------------

def build_choice_prompt(persona, option_a_text, option_b_text, choice_context="",
                        shared_context=None):
    """Choice prompt. When `shared_context` is provided (e.g., a dilemma's
    situation that both options share), it renders once above the option
    cards — mirroring the web interface's lifted-fields presentation."""
    context_line = choice_context if choice_context else "You are choosing between two options."
    if shared_context:
        return f"""You are roleplaying as the following person. Stay in character and make choices as this person would — not as a neutral AI.

PERSONA:
{persona['description']}

---

{context_line} Read the shared context, then choose the action this person would prefer.

CONTEXT:
{shared_context}

OPTION A:
{option_a_text}

OPTION B:
{option_b_text}

Respond with valid JSON only:
{{"thinking": "<2-3 sentences of in-character reasoning>", "choice": "A" or "B"}}"""
    return f"""You are roleplaying as the following person. Stay in character and make choices as this person would — not as a neutral AI.

PERSONA:
{persona['description']}

---

{context_line} Read both options carefully, then choose the one this person would prefer.

OPTION A:
{option_a_text}

OPTION B:
{option_b_text}

Respond with valid JSON only:
{{"thinking": "<2-3 sentences of in-character reasoning>", "choice": "A" or "B"}}"""


def llm_choice(client, model, persona, option_a_text, option_b_text,
               cache_key, choice_context="", shared_context=None):
    prompt = build_choice_prompt(persona, option_a_text, option_b_text,
                                  choice_context, shared_context=shared_context)
    text = client.call(model, prompt, temperature=0.3, cache_key=cache_key)
    parsed = parse_json_response(text)
    choice = parsed.get("choice", "A").strip().upper()
    if choice not in ("A", "B"):
        choice = "A"
    return {"choice": choice, "thinking": parsed.get("thinking", "")}


# ---------------------------------------------------------------------------
# Inference-feedback prompts (UI-faithful)
# ---------------------------------------------------------------------------

def _format_dim_for_prompt(dim_meta):
    name = dim_meta.get("name") or dim_meta.get("label") or "dim"
    low = (dim_meta.get("low_pole") or {}).get("label", "")
    high = (dim_meta.get("high_pole") or {}).get("label", "")
    poles = f" (low: {low} ↔ high: {high})" if low or high else ""
    return name, poles


def build_inference_affirm_prompt(persona, choice_label, other_label,
                                  visible_dims, category_labels, choice_context=""):
    """visible_dims: list of dicts with keys name, low_pole, high_pole, pre_category_label, pre_phrase."""
    context = choice_context or "You just chose between two options."
    dim_lines = []
    for i, vd in enumerate(visible_dims, 1):
        name, poles = _format_dim_for_prompt(vd["meta"])
        phrase = vd["pre_phrase"]
        dim_lines.append(f'{i}. The system thinks: "You {phrase} {name}"{poles}')
    dim_block = "\n".join(dim_lines)
    schema_keys = ", ".join(f'"{i+1}": "<affirm | moderate | remove>"' for i in range(len(visible_dims)))

    return f"""You are roleplaying as the following person:

{persona['description']}

{context} You chose Option {choice_label} over Option {other_label}.

The system has guessed what your choice reveals about your preferences on the dimensions below. For each guess, decide:
- "affirm" — yes, that strongly describes me on this dimension
- "moderate" — partly true; the system's guess is in the right direction but too strong
- "remove" — no, this dimension didn't drive my choice (or the system has the wrong direction)

GUESSES:
{dim_block}

Respond with valid JSON only:
{{"reasoning": "<1-2 sentences of in-character reasoning>", "actions": {{{schema_keys}}}}}"""


def build_inference_categories_prompt(persona, choice_label, other_label,
                                      visible_dims, category_labels, choice_context=""):
    """category_labels: list of 5 strings (matching DEFAULT_MULTS order)."""
    context = choice_context or "You just chose between two options."
    cats_listed = " / ".join(f'"{c}"' for c in category_labels)
    dim_lines = []
    for i, vd in enumerate(visible_dims, 1):
        name, poles = _format_dim_for_prompt(vd["meta"])
        pre = vd["pre_category_label"]
        dim_lines.append(f'{i}. {name}{poles} — system pre-selected: "{pre}"')
    dim_block = "\n".join(dim_lines)
    schema_keys = ", ".join(f'"{i+1}": "<one of {cats_listed}>"' for i in range(len(visible_dims)))

    return f"""You are roleplaying as the following person:

{persona['description']}

{context} You chose Option {choice_label} over Option {other_label}.

For each of the dimensions below, pick the category that best describes how this person feels about that quality. The system has pre-selected its best guess; you can keep it or change it.

CATEGORIES (most negative → most positive): {cats_listed}

DIMENSIONS:
{dim_block}

Respond with valid JSON only:
{{"reasoning": "<1-2 sentences>", "categories": {{{schema_keys}}}}}"""


def llm_inference_affirm(client, model, persona, choice_label, other_label,
                         visible_dims, category_labels, cache_key, choice_context=""):
    prompt = build_inference_affirm_prompt(persona, choice_label, other_label,
                                           visible_dims, category_labels, choice_context)
    text = client.call(model, prompt, temperature=0.0, cache_key=cache_key, max_tokens=1024)
    parsed = parse_json_response(text)
    actions_raw = parsed.get("actions", {})
    actions = {}
    for i in range(1, len(visible_dims) + 1):
        a = str(actions_raw.get(str(i), "affirm")).strip().lower()
        if a not in ("affirm", "moderate", "remove"):
            a = "affirm"
        actions[i] = a
    return {"reasoning": parsed.get("reasoning", ""), "actions": actions}


def llm_inference_categories(client, model, persona, choice_label, other_label,
                             visible_dims, category_labels, cache_key, choice_context=""):
    prompt = build_inference_categories_prompt(persona, choice_label, other_label,
                                               visible_dims, category_labels, choice_context)
    text = client.call(model, prompt, temperature=0.0, cache_key=cache_key, max_tokens=1024)
    parsed = parse_json_response(text)
    cats_raw = parsed.get("categories", {})
    cats = {}
    label_to_idx = {lbl.lower(): i for i, lbl in enumerate(category_labels)}
    for i in range(1, len(visible_dims) + 1):
        c = str(cats_raw.get(str(i), category_labels[2])).strip().lower()
        cats[i] = label_to_idx.get(c, 2)  # default to indifferent
    return {"reasoning": parsed.get("reasoning", ""), "categories": cats}


# ---------------------------------------------------------------------------
# UI helpers (categorization + multiplier mapping)
# ---------------------------------------------------------------------------

def perdim_quintile_boundaries(values_pool, n_cats=5):
    T, K = values_pool.shape
    n_bounds = n_cats - 1
    quantiles = np.linspace(0, 1, n_cats + 1)[1:-1]
    boundaries = np.zeros((n_bounds, K))
    for k in range(K):
        v = values_pool[:, k]
        symm = np.concatenate([v, -v])
        boundaries[:, k] = np.quantile(symm, quantiles)
    return boundaries


def value_to_cat_idx(value, boundaries_k, n_cats):
    return int(np.searchsorted(boundaries_k, value))


def moderated_idx(idx, n_cats):
    center = n_cats // 2
    if idx == center:
        return idx
    if idx < center:
        return idx + 1
    return idx - 1


def mult_from_action(action, pre_idx, mults, affirm_bonus=1.5):
    """Apply UI affirm/moderate/remove semantics to produce final multiplier."""
    if action == "remove":
        return 0.0
    if action == "moderate":
        return float(mults[moderated_idx(pre_idx, len(mults))])
    return float(affirm_bonus * mults[pre_idx])  # affirm


# ---------------------------------------------------------------------------
# Newton-fit math
# ---------------------------------------------------------------------------

def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -50, 50)))


def fit_standard_kernel(D, y, lam, max_iter=15, tol=1e-7):
    T = len(D)
    alpha = np.zeros(T)
    for _ in range(max_iter):
        u = D @ alpha
        p = sigmoid(u)
        w = p * (1 - p)
        rhs = -(p - y + lam * alpha)
        A = (w[:, None] * D) + lam * np.eye(T)
        try:
            d_alpha = np.linalg.solve(A, rhs)
        except np.linalg.LinAlgError:
            break
        alpha += d_alpha
        if np.max(np.abs(d_alpha)) < tol:
            break
    return alpha


def fit_partial_primal(U, y, G, beta0, lam, max_iter=15, tol=1e-7):
    T, K = U.shape
    beta = beta0.copy()
    for _ in range(max_iter):
        u = U @ beta
        p = sigmoid(u)
        w = p * (1 - p)
        grad = U.T @ (p - y) + lam * G @ (beta - beta0)
        H = U.T @ (w[:, None] * U) + lam * G
        try:
            d_beta = np.linalg.solve(H, -grad)
        except np.linalg.LinAlgError:
            break
        beta += d_beta
        if np.max(np.abs(d_beta)) < tol:
            break
    return beta


def make_checkpoints(num_trials, step):
    """Trial counts at which to refit. step<=0 → only num_trials.
    step=1 → every trial. step>1 → multiples of step, plus 1 and num_trials."""
    if step <= 0:
        return [num_trials]
    pts = list(range(step, num_trials + 1, step))
    if 1 not in pts:
        pts = [1] + pts
    if pts[-1] != num_trials:
        pts.append(num_trials)
    return sorted(set(pts))


def heldout_log_likelihood(logits, choices):
    p = sigmoid(logits)
    eps = 1e-10
    return float(np.mean(choices * np.log(p + eps)
                         + (1 - choices) * np.log(1 - p + eps)))


def predicted_rating_from_ll(ll_other, ll_standard, temperature):
    return float(sigmoid(temperature * (ll_other - ll_standard)))


# ---------------------------------------------------------------------------
# Per-persona simulation
# ---------------------------------------------------------------------------

def simulate_one_persona(persona, ctx, args, client):
    pid = persona["id"]
    rng = np.random.default_rng(args.seed + pid)
    embeddings = ctx["embeddings"]
    V = ctx["V"]
    G = ctx["G"]
    mu = ctx["mu"]
    quintile_bounds = ctx["quintile_bounds"]
    mults = ctx["mults"]
    category_labels = ctx["category_labels"]
    dim_metadata = ctx["dim_metadata"]
    descriptions = ctx["descriptions"]
    raw_rows = ctx.get("raw_rows", {})
    option_template = ctx.get("option_template", "")
    option_ids = ctx["option_ids"]
    predefined_pairs = ctx.get("predefined_pairs")
    use_lifted = predefined_pairs is not None  # match human interface presentation
    N, d = embeddings.shape
    K = V.shape[0]

    def _choice_kwargs(oid_a, oid_b):
        """Build (option_a_text, option_b_text, shared_context) for a pair.
        When --predefined-pairs is set, lift any shared 'situation'-style
        fields to match the web interface's presentation."""
        if use_lifted and oid_a in raw_rows and oid_b in raw_rows:
            shared, a_text, b_text = lifted_pair_text(
                raw_rows[oid_a], raw_rows[oid_b], option_template)
            if shared is not None:
                return a_text, b_text, shared
        return descriptions[oid_a], descriptions[oid_b], None

    print(f"  Persona {pid}: {persona['name']}", flush=True)

    # --- Build per-persona train + test trial pools ---
    # When predefined-pairs is set, both training and test trials come from
    # that pool (e.g., dilemma pairs), with a disjoint per-persona shuffle —
    # mirroring how the human experiment hands each participant a random
    # subset of the same fixed pair pool.
    if predefined_pairs is not None:
        pool = list(predefined_pairs)
        rng.shuffle(pool)
        test_pool = pool[:args.num_test_pairs]
        train_pool = pool[args.num_test_pairs:args.num_test_pairs + args.num_trials]
        test_pairs = np.array(test_pool, dtype=int)
        trial_pairs = list(train_pool)
    else:
        test_pairs = ctx["test_pairs"]
        trial_pairs = []
        while len(trial_pairs) < args.num_trials:
            a, b = rng.choice(N, size=2, replace=False)
            trial_pairs.append((int(a), int(b)))

    # --- Held-out test set choices (ground truth) ---
    print(f"    [{pid}] Test set ({args.num_test_pairs})...", flush=True)
    test_choices = np.zeros(args.num_test_pairs, dtype=int)
    for ti in range(args.num_test_pairs):
        oid_a = option_ids[test_pairs[ti, 0]]
        oid_b = option_ids[test_pairs[ti, 1]]
        a_text, b_text, shared = _choice_kwargs(oid_a, oid_b)
        ck = f"test_choice_{'lift_' if shared else ''}{pid}_{oid_a}_{oid_b}"
        result = llm_choice(client, args.choice_model, persona,
                            a_text, b_text,
                            cache_key=ck,
                            choice_context=args.choice_context,
                            shared_context=shared)
        test_choices[ti] = 1 if result["choice"] == "A" else 0
    test_delta = embeddings[test_pairs[:, 0]] - embeddings[test_pairs[:, 1]]
    test_U = test_delta @ V.T

    # --- Pre-collect per-trial choices (shared across conditions, since the
    #     persona's choice isn't condition-dependent — only the feedback is) ---
    print(f"    [{pid}] Training choices ({args.num_trials})...", flush=True)
    trial_data = []  # list of dicts: idx_a, idx_b, choice ('A'/'B'), thinking
    for t, (idx_a, idx_b) in enumerate(trial_pairs):
        oid_a = option_ids[idx_a]
        oid_b = option_ids[idx_b]
        a_text, b_text, shared = _choice_kwargs(oid_a, oid_b)
        ck = f"train_choice_{'lift_' if shared else ''}{pid}_{t}_{oid_a}_{oid_b}"
        result = llm_choice(client, args.choice_model, persona,
                            a_text, b_text,
                            cache_key=ck,
                            choice_context=args.choice_context,
                            shared_context=shared)
        trial_data.append({"idx_a": idx_a, "idx_b": idx_b,
                           "choice": result["choice"], "thinking": result["thinking"]})

    cond_results = {}

    for cond in CONDITIONS:
        deltas = np.zeros((args.num_trials, d))
        ys = np.zeros(args.num_trials, dtype=int)
        lam_traj = np.zeros((args.num_trials, K))
        visible_traj = np.zeros((args.num_trials, K), dtype=bool)
        action_log = []

        for t, td in enumerate(trial_data):
            idx_a, idx_b = td["idx_a"], td["idx_b"]
            phi_a = embeddings[idx_a]
            phi_b = embeddings[idx_b]
            deltas[t] = phi_a - phi_b
            y = 1 if td["choice"] == "A" else 0
            ys[t] = y

            if cond == "choice_only":
                continue

            chosen_phi = phi_a if y == 1 else phi_b
            value_if_chosen = V @ (chosen_phi - mu)
            k_vis = min(args.top_k_inferences, K)
            visible = np.argsort(-np.abs(value_if_chosen))[:k_vis]
            visible_traj[t, visible] = True

            visible_dims = []
            for k in visible:
                pre_idx = value_to_cat_idx(value_if_chosen[k],
                                           quintile_bounds[:, k], len(mults))
                visible_dims.append({
                    "k": int(k), "meta": dim_metadata[k] if k < len(dim_metadata) else {"name": f"dim_{k}"},
                    "pre_idx": pre_idx,
                    "pre_category_label": category_labels[pre_idx],
                    "pre_phrase": category_labels[pre_idx],
                })

            choice_label = "A" if y == 1 else "B"
            other_label = "B" if y == 1 else "A"

            if cond == "inference_affirm":
                cache_key = f"affirm_{pid}_{t}"
                resp = llm_inference_affirm(client, args.choice_model, persona,
                                            choice_label, other_label,
                                            visible_dims, category_labels,
                                            cache_key, args.choice_context)
                for i, vd in enumerate(visible_dims, 1):
                    action = resp["actions"].get(i, "affirm")
                    applied = mult_from_action(action, vd["pre_idx"], mults)
                    lam_traj[t, vd["k"]] = applied
                    action_log.append({"trial": t, "dim": vd["k"], "action": action,
                                       "pre_idx": vd["pre_idx"], "applied": applied})
            else:  # inference_categories
                cache_key = f"cats_{pid}_{t}"
                resp = llm_inference_categories(client, args.choice_model, persona,
                                                choice_label, other_label,
                                                visible_dims, category_labels,
                                                cache_key, args.choice_context)
                for i, vd in enumerate(visible_dims, 1):
                    cat_idx = resp["categories"].get(i, 2)
                    applied = float(mults[cat_idx])
                    action = "modify" if cat_idx != vd["pre_idx"] else "none"
                    lam_traj[t, vd["k"]] = applied
                    action_log.append({"trial": t, "dim": vd["k"], "action": action,
                                       "pre_idx": vd["pre_idx"], "cat_idx": cat_idx,
                                       "applied": applied})

        # Pre-compute full kernel/projection once; we'll slice into prefixes.
        D_full = deltas @ deltas.T          # (T, T)
        U_full = deltas @ V.T               # (T, K)
        cross_full = test_delta @ deltas.T  # (M, T)

        # Λ feedback multipliers → design-matrix scale, with α-interpolation:
        #     Ũ_α[t,k] = U[t,k] · ((1 − α) + α · λ_tk)   for visible dims
        #     Ũ_α[t,k] = U[t,k]                           for invisible dims
        # α=0 ⇒ projection; α=1 ⇒ full feedback. For calibration.
        alpha = getattr(args, "feedback_alpha", 1.0)
        feedback_full = np.ones_like(U_full)
        if cond != "choice_only":
            feedback_full[visible_traj] = ((1.0 - alpha)
                                            + alpha * lam_traj[visible_traj])
        U_adj_full = feedback_full * U_full

        checkpoints = make_checkpoints(args.num_trials, args.checkpoint_step)
        ckpts = []
        for t_end in checkpoints:
            if t_end < 1 or t_end > args.num_trials:
                continue
            D_t = D_full[:t_end, :t_end]
            U_t = U_full[:t_end]
            U_adj_t = U_adj_full[:t_end]
            y_t = ys[:t_end].astype(float)

            # All three fits, every checkpoint, every condition.
            alpha = fit_standard_kernel(D_t, y_t, args.lambda_standard)
            beta_proj = fit_partial_primal(U_t, y_t, G, np.zeros(K),
                                           args.lambda_partial)
            if cond == "choice_only":
                beta_part = beta_proj
            else:
                beta_part = fit_partial_primal(U_adj_t, y_t, G, np.zeros(K),
                                               args.lambda_partial)

            cross_t = cross_full[:, :t_end]
            logits_std = cross_t @ alpha
            logits_proj = test_U @ beta_proj
            logits_part = test_U @ beta_part
            ll_std = heldout_log_likelihood(logits_std, test_choices)
            ll_proj = heldout_log_likelihood(logits_proj, test_choices)
            ll_part = heldout_log_likelihood(logits_part, test_choices)
            acc_std = float(((logits_std > 0).astype(int) == test_choices).mean())
            acc_proj = float(((logits_proj > 0).astype(int) == test_choices).mean())
            acc_part = float(((logits_part > 0).astype(int) == test_choices).mean())
            # Predicted DV uses partial vs standard (matches the experiment).
            rating = predicted_rating_from_ll(ll_part, ll_std,
                                              args.rating_temperature)
            ckpts.append({
                "n_trials": int(t_end),
                "ll_standard": ll_std, "ll_projected": ll_proj, "ll_partial": ll_part,
                "acc_standard": acc_std, "acc_projected": acc_proj, "acc_partial": acc_part,
                "rating_partial_vs_standard": rating,
            })

        cond_results[cond] = {
            "checkpoints": ckpts,
            "actions": action_log,
        }

    client.save_cache()
    print(f"  Persona {pid} done.", flush=True)
    return {"persona_id": pid, "name": persona["name"], "conditions": cond_results}


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

FIT_TYPES = ["standard", "projected", "partial"]


def aggregate_final(per_persona_results):
    """One row per (persona, condition) using the final-T checkpoint.

    Carries metrics for all three fits (standard / projected / partial).
    """
    rows = []
    for pr in per_persona_results:
        pid = pr["persona_id"]
        for cond, r in pr["conditions"].items():
            if not r["checkpoints"]:
                continue
            final = r["checkpoints"][-1]
            row = {
                "persona_id": pid, "condition": cond,
                "n_trials": final["n_trials"],
                "rating_partial_vs_standard": final["rating_partial_vs_standard"],
            }
            for fit in FIT_TYPES:
                row[f"ll_{fit}"] = final[f"ll_{fit}"]
                row[f"acc_{fit}"] = final[f"acc_{fit}"]
            rows.append(row)
    return pd.DataFrame(rows)


def aggregate_curves(per_persona_results):
    """One row per (persona, condition, n_trials, fit_type). Long format."""
    rows = []
    for pr in per_persona_results:
        pid = pr["persona_id"]
        for cond, r in pr["conditions"].items():
            for ckpt in r["checkpoints"]:
                t = ckpt["n_trials"]
                for fit in FIT_TYPES:
                    rows.append({
                        "persona_id": pid,
                        "condition": cond,
                        "fit_type": fit,
                        "n_trials": t,
                        "test_acc": ckpt[f"acc_{fit}"],
                        "test_ll": ckpt[f"ll_{fit}"],
                    })
    return pd.DataFrame(rows)


def write_summary(df, curves_df, args, output_dir):
    lines = ["# LLM-Persona Simulation Summary (revamped)\n"]
    lines.append("Predicts the experimental DV: probability that an LLM-persona "
                 "participant prefers the partial/projected K-dim summary over "
                 "the unrestricted standard summary, after T training trials.\n")
    lines.append("## Parameters\n")
    lines.append("| Parameter | Value |")
    lines.append("|-----------|-------|")
    lines.append(f"| Personas | {args.num_personas} |")
    lines.append(f"| Persona model | {args.persona_model} |")
    lines.append(f"| Choice model | {args.choice_model} |")
    lines.append(f"| Trials per persona | {args.num_trials} |")
    lines.append(f"| Test pairs (held-out) | {args.num_test_pairs} |")
    lines.append(f"| Top-K inferences visible | {args.top_k_inferences} |")
    lines.append(f"| λ standard | {args.lambda_standard} |")
    lines.append(f"| λ partial  | {args.lambda_partial} |")
    lines.append(f"| Rating temperature τ | {args.rating_temperature} |")
    lines.append(f"| Seed | {args.seed} |")
    lines.append("")

    lines.append("## Predicted Rating (P[partial > standard])\n")
    lines.append("| Condition | Mean | SD | Pct > 0.5 |")
    lines.append("|-----------|------|----|-----------|")
    for cond in CONDITIONS:
        cdf = df[df["condition"] == cond]
        if cdf.empty:
            continue
        lines.append(f"| {cond} | "
                     f"{cdf['rating_partial_vs_standard'].mean():.3f} | "
                     f"{cdf['rating_partial_vs_standard'].std():.3f} | "
                     f"{(cdf['rating_partial_vs_standard'] > 0.5).mean()*100:.0f}% |")
    lines.append("")

    lines.append("## Held-Out Log-Likelihood (primary quality signal)\n")
    lines.append("| Condition | LL standard | LL projected | LL partial | Δ proj−std | Δ part−std |")
    lines.append("|-----------|-------------|--------------|------------|------------|------------|")
    for cond in CONDITIONS:
        cdf = df[df["condition"] == cond]
        if cdf.empty:
            continue
        ll_s = cdf["ll_standard"].mean()
        ll_pr = cdf["ll_projected"].mean()
        ll_pa = cdf["ll_partial"].mean()
        lines.append(f"| {cond} | {ll_s:+.4f} | {ll_pr:+.4f} | {ll_pa:+.4f} | "
                     f"{ll_pr - ll_s:+.4f} | {ll_pa - ll_s:+.4f} |")
    lines.append("")

    lines.append("## Held-Out Choice Accuracy\n")
    lines.append("| Condition | Acc standard | Acc projected | Acc partial |")
    lines.append("|-----------|--------------|---------------|-------------|")
    for cond in CONDITIONS:
        cdf = df[df["condition"] == cond]
        if cdf.empty:
            continue
        lines.append(f"| {cond} | {cdf['acc_standard'].mean():.3f} | "
                     f"{cdf['acc_projected'].mean():.3f} | "
                     f"{cdf['acc_partial'].mean():.3f} |")
    lines.append("")

    lines.append("## Significance Tests\n")
    lines.append("| Comparison | n | mean Δ rating | Wilcoxon p |")
    lines.append("|------------|---|---------------|------------|")
    for cond in CONDITIONS:
        cdf = df[df["condition"] == cond]
        if cdf.empty:
            continue
        ratings = cdf["rating_partial_vs_standard"].values
        try:
            stat, p = wilcoxon(ratings - 0.5, zero_method="zsplit")
        except ValueError:
            p = float("nan")
        lines.append(f"| {cond} vs 0.5 | {len(ratings)} | {ratings.mean() - 0.5:+.3f} | {p:.4f} |")
    base = df[df["condition"] == "choice_only"]["rating_partial_vs_standard"].values
    for cond in ["inference_affirm", "inference_categories"]:
        other = df[df["condition"] == cond]["rating_partial_vs_standard"].values
        if len(base) == 0 or len(other) == 0:
            continue
        n = min(len(base), len(other))
        try:
            stat, p = wilcoxon(other[:n], base[:n])
        except ValueError:
            p = float("nan")
        lines.append(f"| {cond} vs choice_only | {n} | "
                     f"{other[:n].mean() - base[:n].mean():+.3f} | {p:.4f} |")
    lines.append("")

    # ----------------------------------------------------------------------
    # Learning-curve summary
    # ----------------------------------------------------------------------
    lines.append("## Learning Curves (test acc by trial count)\n")
    lines.append("Mean held-out accuracy across personas at each checkpoint. "
                 "Should rise with more trials if learning is working.\n")
    if curves_df is not None and not curves_df.empty:
        ts = sorted(curves_df["n_trials"].unique())
        if len(ts) > 5:
            idx = np.linspace(0, len(ts) - 1, 5).astype(int)
            ts_show = [ts[i] for i in idx]
        else:
            ts_show = ts
        header = ["Condition", "Fit"] + [f"T={t}" for t in ts_show]
        lines.append("| " + " | ".join(header) + " |")
        lines.append("| " + " | ".join(["---"] * len(header)) + " |")
        for cond in CONDITIONS:
            cdf = curves_df[curves_df["condition"] == cond]
            if cdf.empty:
                continue
            for fit_label in FIT_TYPES:
                if fit_label not in cdf["fit_type"].unique():
                    continue
                row = [cond, fit_label]
                for t in ts_show:
                    sub = cdf[(cdf["fit_type"] == fit_label) & (cdf["n_trials"] == t)]
                    row.append(f"{sub['test_acc'].mean():.3f}" if not sub.empty else "—")
                lines.append("| " + " | ".join(row) + " |")
        lines.append("")

        bad = []
        for cond in CONDITIONS:
            for fit_label in FIT_TYPES:
                sub = (curves_df[(curves_df["condition"] == cond)
                                 & (curves_df["fit_type"] == fit_label)]
                       .groupby("n_trials")["test_acc"].mean())
                if len(sub) < 3:
                    continue
                t_half = sub.index[len(sub) // 2]
                t_full = sub.index[-1]
                if sub.loc[t_full] <= sub.loc[t_half] - 1e-3:
                    bad.append(f"{cond}/{fit_label}: T={t_half}→{sub.loc[t_half]:.3f}, "
                               f"T={t_full}→{sub.loc[t_full]:.3f}")
        if bad:
            lines.append("**⚠ Non-monotonic learning detected (acc didn't improve "
                         "from mid-T to end-T):**\n")
            for b in bad:
                lines.append(f"- {b}")
            lines.append("")

    with open(output_dir / "summary.md", "w") as f:
        f.write("\n".join(lines) + "\n")


FIT_STYLE = {
    "standard":  {"color": "#444444", "marker": "o", "label": "MLE (standard kernel)"},
    "projected": {"color": "#1f77b4", "marker": "s", "label": "MLE projected onto basis"},
    "partial":   {"color": "#d62728", "marker": "^", "label": "Partial (feedback re-weighted)"},
}


def plot_learning_curves(curves_df, output_dir):
    if curves_df is None or curves_df.empty:
        return
    fig, axes = plt.subplots(2, len(CONDITIONS), figsize=(4.8 * len(CONDITIONS), 8),
                             sharex=True)
    if len(CONDITIONS) == 1:
        axes = axes[:, None]

    metric_specs = [
        ("test_acc", "Held-out accuracy", 0.5),
        ("test_ll", "Held-out log-likelihood", None),
    ]
    for row_idx, (col, ylabel, hline) in enumerate(metric_specs):
        for col_idx, cond in enumerate(CONDITIONS):
            ax = axes[row_idx, col_idx]
            cdf = curves_df[curves_df["condition"] == cond]
            if cdf.empty:
                ax.set_visible(False)
                continue
            for fit_label in FIT_TYPES:
                sub = cdf[cdf["fit_type"] == fit_label]
                if sub.empty:
                    continue
                grouped = sub.groupby("n_trials")[col]
                mean = grouped.mean()
                sem = grouped.std() / np.sqrt(grouped.count())
                style = FIT_STYLE[fit_label]
                ax.plot(mean.index, mean.values,
                        marker=style["marker"], color=style["color"],
                        label=style["label"], linewidth=2)
                ax.fill_between(mean.index, mean.values - sem.values,
                                mean.values + sem.values,
                                color=style["color"], alpha=0.15)
            if hline is not None:
                ax.axhline(hline, color="gray", linestyle="--", alpha=0.5)
            if row_idx == 0:
                ax.set_title(cond, fontweight="bold")
            if row_idx == len(metric_specs) - 1:
                ax.set_xlabel("# trials collected")
            if col_idx == 0:
                ax.set_ylabel(ylabel)
            ax.grid(True, alpha=0.3)
            if col_idx == 0 and row_idx == 0:
                ax.legend(loc="lower right", fontsize=9)
    fig.suptitle("LLM-Persona learning curves — three fits per condition",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig(output_dir / "learning_curves.png", dpi=150, bbox_inches="tight")
    plt.close()


def plot_results(df, output_dir):
    fig, ax = plt.subplots(figsize=(8, 5))
    data, labels = [], []
    for cond in CONDITIONS:
        cdf = df[df["condition"] == cond]
        if not cdf.empty:
            data.append(cdf["rating_partial_vs_standard"].values)
            labels.append(cond.replace("_", "\n"))
    if data:
        ax.boxplot(data, tick_labels=labels, showmeans=True)
    ax.axhline(0.5, color="gray", linestyle="--", alpha=0.5, label="no preference")
    ax.set_ylabel("P(partial summary preferred over standard)")
    ax.set_title("LLM-Persona Sim — Predicted experimental DV", fontweight="bold")
    ax.legend(loc="lower right")
    ax.set_ylim(0, 1)
    plt.tight_layout()
    plt.savefig(output_dir / "predicted_dv.png", dpi=150, bbox_inches="tight")
    plt.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_simulation(args):
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    raw_client = make_client_or_pool(args.base_url, args.api_key, args.api_provider)
    client = LLMClient(raw_client, cache_path=output_dir / "llm_cache.json")

    print("Loading data...")
    embeddings, bt_scores, V, G, mu, option_ids, dim_names = load_data(
        args.embeddings_parquet, args.bt_scores, args.directions,
        option_id_column=args.option_id_column,
    )
    N, d = embeddings.shape
    K = V.shape[0]
    print(f"  Options: {N}, d: {d}, K: {K}")

    dim_metadata = load_dimensions(args.dimensions)
    descriptions, raw_rows, option_template = load_option_descriptions(
        args.option_descriptions, args.option_template,
        id_column=args.option_id_column)

    centered = embeddings - mu[np.newaxis, :]
    pool_proj = centered @ V.T
    quintile_bounds = perdim_quintile_boundaries(pool_proj, n_cats=len(DEFAULT_MULTS))

    print("Generating personas...")
    personas = generate_personas(client, args.persona_model, args.num_personas,
                                 domain=args.domain, choice_context=args.choice_context)
    print(f"  Generated {len(personas)} personas")
    with open(output_dir / "personas.json", "w") as f:
        json.dump(personas, f, indent=2)
    client.save_cache()

    predefined_pairs = None
    if args.predefined_pairs:
        predefined_pairs = load_predefined_pairs(args.predefined_pairs, option_ids)
        need = args.num_trials + args.num_test_pairs
        if len(predefined_pairs) < need:
            raise ValueError(f"predefined-pairs pool has only {len(predefined_pairs)} "
                             f"pairs, but need {need} = num_trials + num_test_pairs.")
        # test_pairs gets selected per-persona (from the same pool, held out
        # from training) so we leave it unset here. simulate_one_persona will
        # build its own from the pool.
        test_pairs = None
    else:
        test_a = rng.integers(0, N, size=args.num_test_pairs)
        test_b = rng.integers(0, N, size=args.num_test_pairs)
        mask = test_a == test_b
        while mask.any():
            test_b[mask] = rng.integers(0, N, size=int(mask.sum()))
            mask = test_a == test_b
        test_pairs = np.stack([test_a, test_b], axis=1)

    category_labels = (args.category_labels.split("|")
                       if args.category_labels else DEFAULT_CATEGORY_LABELS)
    if len(category_labels) != len(DEFAULT_MULTS):
        raise ValueError(f"--category-labels must have {len(DEFAULT_MULTS)} entries "
                         f"separated by '|'.")

    ctx = {
        "embeddings": embeddings, "V": V, "G": G, "mu": mu,
        "quintile_bounds": quintile_bounds,
        "mults": DEFAULT_MULTS * args.multiplier_scale,
        "category_labels": category_labels,
        "dim_metadata": dim_metadata, "descriptions": descriptions,
        "raw_rows": raw_rows, "option_template": option_template,
        "option_ids": option_ids, "test_pairs": test_pairs,
        "predefined_pairs": predefined_pairs,
    }

    print("Running personas...")
    per_persona_results = []
    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = {executor.submit(simulate_one_persona, p, ctx, args, client): p
                   for p in personas}
        for future in as_completed(futures):
            p = futures[future]
            try:
                per_persona_results.append(future.result())
            except Exception as e:
                print(f"  Persona {p['id']} failed: {e}", flush=True)
                raise

    df = aggregate_final(per_persona_results)
    df.to_csv(output_dir / "per_persona_per_condition.csv", index=False)
    print(f"Saved per_persona_per_condition.csv ({len(df)} rows)")

    curves_df = aggregate_curves(per_persona_results)
    curves_df.to_csv(output_dir / "learning_curves.csv", index=False)
    print(f"Saved learning_curves.csv ({len(curves_df)} rows)")

    write_summary(df, curves_df, args, output_dir)
    print("Saved summary.md")
    try:
        plot_results(df, output_dir)
        print("Saved predicted_dv.png")
    except Exception as e:
        print(f"Warning: could not save predicted_dv.png: {e}")
    try:
        plot_learning_curves(curves_df, output_dir)
        print("Saved learning_curves.png")
    except Exception as e:
        print(f"Warning: could not save learning_curves.png: {e}")
    client.save_cache()
    print("Done.")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--embeddings-parquet", required=True)
    p.add_argument("--bt-scores", required=True)
    p.add_argument("--dimensions", required=True)
    p.add_argument("--directions", required=True)
    p.add_argument("--option-descriptions", required=True)
    p.add_argument("--option-template", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--option-id-column", default="movie_id")

    p.add_argument("--api-provider", choices=["local", "openai", "anthropic"], default="local")
    p.add_argument("--base-url")
    p.add_argument("--persona-model", default="gpt-4o-mini")
    p.add_argument("--choice-model", default="gpt-4o-mini")
    p.add_argument("--api-key", default=None)

    p.add_argument("--num-personas", type=int, default=20)
    p.add_argument("--num-trials", type=int, default=20)
    p.add_argument("--num-test-pairs", type=int, default=50)
    p.add_argument("--top-k-inferences", type=int, default=5)
    p.add_argument("--lambda-standard", type=float, default=10.0)
    p.add_argument("--lambda-partial", type=float, default=0.5,
                   help="L2 reg for K-dim primal fit (both projected + partial).")
    p.add_argument("--feedback-alpha", type=float, default=1.0,
                   help="Feedback strength α ∈ [0, 1] for partial fit. "
                        "Ũ_α = U·((1−α) + α·λ_tk). α=0 ⇒ projected; α=1 ⇒ full.")
    p.add_argument("--multiplier-scale", type=float, default=1.0,
                   help="Scalar applied to DEFAULT_MULTS = "
                        "[-1.5,-1.0,0,1.0,1.5]. For calibration.")
    p.add_argument("--rating-temperature", type=float, default=20.0,
                   help="Larger τ for LLM sim because LL differences are smaller.")
    p.add_argument("--max-workers", type=int, default=4)
    p.add_argument("--checkpoint-step", type=int, default=1,
                   help="Refit at every Nth trial. 1 = every trial (default), "
                        "5 = at trials 5, 10, 15, ... 0 disables intermediate "
                        "checkpoints (only fits at T).")
    p.add_argument("--seed", type=int, default=42)

    p.add_argument("--predefined-pairs", default=None,
                   help="Optional JSON file with predefined (option_a_id, "
                        "option_b_id) pairs (e.g., dilemma pairs). When set, "
                        "training and test trials are sampled WITHOUT replacement "
                        "from this pool — matching the human experiment, which "
                        "uses the same pair pool. Disjoint train/test split per "
                        "persona seeded by --seed + persona_id.")

    p.add_argument("--domain", default="movies")
    p.add_argument("--choice-context", default="")
    p.add_argument("--category-labels", default="",
                   help="5 category labels separated by '|', most-negative to "
                        "most-positive. Defaults to movies/wines language.")

    # Deprecated args (kept for backward compatibility)
    p.add_argument("--learning-rate", type=float, default=None,
                   help="DEPRECATED: ignored.")
    p.add_argument("--projection-lambda", type=float, default=None,
                   help="DEPRECATED: ignored.")

    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_simulation(args)
