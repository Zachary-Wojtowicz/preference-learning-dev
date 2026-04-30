"""
LLM-Persona Preference Learning Simulation (revamped to match the 3 final
experimental conditions).

LLM personas replace the synthetic weight-vec users. Each persona:
  1. Makes binary choices on a held-out test set (ground truth).
  2. For each of 3 conditions, runs through T training trials, providing
     per-dim feedback when the condition asks for it (mirrors the actual
     web-interface UI).
  3. We run end-of-experiment Newton+L2 fits — kernel-logistic standard
     and K-dim primal partial/projected with G-shape prior centered at
     β₀ = G⁻¹·mean(λ_t).
  4. Predicted experimental DV: P(participant prefers K-dim summary over
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
    G_reg = G + 1e-6 * np.eye(G.shape[0])
    G_inv = np.linalg.inv(G_reg)

    print(f"  Gram matrix condition number: {np.linalg.cond(G):.1f}")
    print(f"  Max inter-dimension correlation: {np.abs(G - np.eye(G.shape[0])).max():.3f}")

    return embeddings, bt_scores, V, G, G_inv, mu, option_ids, dim_names


def load_dimensions(path):
    with open(path) as f:
        return json.load(f)["dimensions"]


def load_option_descriptions(csv_path, template_path, id_column):
    df = pd.read_csv(csv_path)
    template = Path(template_path).read_text().strip()
    descriptions = {}
    for _, row in df.iterrows():
        oid = str(row[id_column])
        try:
            text = template.format(**row.to_dict())
        except KeyError:
            parts = [f"{k}: {v}" for k, v in row.items()
                     if k != id_column and pd.notna(v) and str(v).strip()]
            text = " | ".join(parts)
        descriptions[oid] = text
    return descriptions


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

def build_choice_prompt(persona, option_a_text, option_b_text, choice_context=""):
    context_line = choice_context if choice_context else "You are choosing between two options."
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
               cache_key, choice_context=""):
    prompt = build_choice_prompt(persona, option_a_text, option_b_text, choice_context)
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


def compute_beta0(lam_traj, visible_traj, G_inv):
    K = lam_traj.shape[1]
    avg = np.zeros(K)
    for k in range(K):
        n_visible = visible_traj[:, k].sum()
        if n_visible > 0:
            avg[k] = lam_traj[visible_traj[:, k], k].mean()
    return G_inv @ avg


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
    G_inv = ctx["G_inv"]
    mu = ctx["mu"]
    quintile_bounds = ctx["quintile_bounds"]
    mults = ctx["mults"]
    category_labels = ctx["category_labels"]
    dim_metadata = ctx["dim_metadata"]
    descriptions = ctx["descriptions"]
    option_ids = ctx["option_ids"]
    test_pairs = ctx["test_pairs"]
    N, d = embeddings.shape
    K = V.shape[0]

    print(f"  Persona {pid}: {persona['name']}", flush=True)

    # --- Held-out test set choices (ground truth) ---
    print(f"    [{pid}] Test set ({args.num_test_pairs})...", flush=True)
    test_choices = np.zeros(args.num_test_pairs, dtype=int)
    for ti in range(args.num_test_pairs):
        oid_a = option_ids[test_pairs[ti, 0]]
        oid_b = option_ids[test_pairs[ti, 1]]
        result = llm_choice(client, args.choice_model, persona,
                            descriptions[oid_a], descriptions[oid_b],
                            cache_key=f"test_choice_{pid}_{oid_a}_{oid_b}",
                            choice_context=args.choice_context)
        test_choices[ti] = 1 if result["choice"] == "A" else 0
    test_delta = embeddings[test_pairs[:, 0]] - embeddings[test_pairs[:, 1]]
    test_U = test_delta @ V.T

    # --- One shared trial pool across conditions ---
    trial_pairs = []
    while len(trial_pairs) < args.num_trials:
        a, b = rng.choice(N, size=2, replace=False)
        trial_pairs.append((int(a), int(b)))

    # --- Pre-collect per-trial choices (shared across conditions, since the
    #     persona's choice isn't condition-dependent — only the feedback is) ---
    print(f"    [{pid}] Training choices ({args.num_trials})...", flush=True)
    trial_data = []  # list of dicts: idx_a, idx_b, choice ('A'/'B'), thinking
    for t, (idx_a, idx_b) in enumerate(trial_pairs):
        oid_a = option_ids[idx_a]
        oid_b = option_ids[idx_b]
        result = llm_choice(client, args.choice_model, persona,
                            descriptions[oid_a], descriptions[oid_b],
                            cache_key=f"train_choice_{pid}_{t}_{oid_a}_{oid_b}",
                            choice_context=args.choice_context)
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

        # Batch fits
        D = deltas @ deltas.T
        U = deltas @ V.T
        alpha = fit_standard_kernel(D, ys.astype(float), args.lambda_standard)
        if cond == "choice_only":
            beta0 = np.zeros(K)
            other_label = "projected"
        else:
            beta0 = compute_beta0(lam_traj, visible_traj, G_inv)
            other_label = "partial"
        beta = fit_partial_primal(U, ys.astype(float), G, beta0, args.lambda_partial)

        # Held-out log-likelihood
        cross_kernel = test_delta @ deltas.T
        logits_std = cross_kernel @ alpha
        logits_other = test_U @ beta
        ll_std = heldout_log_likelihood(logits_std, test_choices)
        ll_other = heldout_log_likelihood(logits_other, test_choices)
        acc_std = float(((logits_std > 0).astype(int) == test_choices).mean())
        acc_other = float(((logits_other > 0).astype(int) == test_choices).mean())
        rating = predicted_rating_from_ll(ll_other, ll_std, args.rating_temperature)

        cond_results[cond] = {
            "other_label": other_label,
            "ll_standard": ll_std, "ll_other": ll_other,
            "acc_standard": acc_std, "acc_other": acc_other,
            "predicted_rating_other_vs_standard": rating,
            "actions": action_log,
        }

    client.save_cache()
    print(f"  Persona {pid} done.", flush=True)
    return {"persona_id": pid, "name": persona["name"], "conditions": cond_results}


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def aggregate_results(per_persona_results):
    rows = []
    for pr in per_persona_results:
        pid = pr["persona_id"]
        for cond, r in pr["conditions"].items():
            rows.append({
                "persona_id": pid, "condition": cond, "other_label": r["other_label"],
                "ll_standard": r["ll_standard"], "ll_other": r["ll_other"],
                "acc_standard": r["acc_standard"], "acc_other": r["acc_other"],
                "rating_other_vs_standard": r["predicted_rating_other_vs_standard"],
            })
    return pd.DataFrame(rows)


def write_summary(df, args, output_dir):
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

    lines.append("## Predicted Rating (P[other > standard])\n")
    lines.append("| Condition | Other | Mean | SD | Pct > 0.5 |")
    lines.append("|-----------|-------|------|----|-----------|")
    for cond in CONDITIONS:
        cdf = df[df["condition"] == cond]
        if cdf.empty:
            continue
        lines.append(f"| {cond} | {cdf['other_label'].iloc[0]} | "
                     f"{cdf['rating_other_vs_standard'].mean():.3f} | "
                     f"{cdf['rating_other_vs_standard'].std():.3f} | "
                     f"{(cdf['rating_other_vs_standard'] > 0.5).mean()*100:.0f}% |")
    lines.append("")

    lines.append("## Held-Out Log-Likelihood (primary quality signal)\n")
    lines.append("| Condition | LL standard | LL other | Δ (other − standard) |")
    lines.append("|-----------|-------------|----------|----------------------|")
    for cond in CONDITIONS:
        cdf = df[df["condition"] == cond]
        if cdf.empty:
            continue
        ll_s = cdf["ll_standard"].mean()
        ll_o = cdf["ll_other"].mean()
        lines.append(f"| {cond} | {ll_s:+.4f} | {ll_o:+.4f} | {ll_o - ll_s:+.4f} |")
    lines.append("")

    lines.append("## Held-Out Choice Accuracy\n")
    lines.append("| Condition | Acc standard | Acc other |")
    lines.append("|-----------|--------------|-----------|")
    for cond in CONDITIONS:
        cdf = df[df["condition"] == cond]
        if cdf.empty:
            continue
        lines.append(f"| {cond} | {cdf['acc_standard'].mean():.3f} | "
                     f"{cdf['acc_other'].mean():.3f} |")
    lines.append("")

    lines.append("## Significance Tests\n")
    lines.append("| Comparison | n | mean Δ rating | Wilcoxon p |")
    lines.append("|------------|---|---------------|------------|")
    for cond in CONDITIONS:
        cdf = df[df["condition"] == cond]
        if cdf.empty:
            continue
        ratings = cdf["rating_other_vs_standard"].values
        try:
            stat, p = wilcoxon(ratings - 0.5, zero_method="zsplit")
        except ValueError:
            p = float("nan")
        lines.append(f"| {cond} vs 0.5 | {len(ratings)} | {ratings.mean() - 0.5:+.3f} | {p:.4f} |")
    base = df[df["condition"] == "choice_only"]["rating_other_vs_standard"].values
    for cond in ["inference_affirm", "inference_categories"]:
        other = df[df["condition"] == cond]["rating_other_vs_standard"].values
        if len(base) == 0 or len(other) == 0:
            continue
        n = min(len(base), len(other))
        try:
            stat, p = wilcoxon(other[:n], base[:n])
        except ValueError:
            p = float("nan")
        lines.append(f"| {cond} vs choice_only | {n} | "
                     f"{other[:n].mean() - base[:n].mean():+.3f} | {p:.4f} |")

    with open(output_dir / "summary.md", "w") as f:
        f.write("\n".join(lines) + "\n")


def plot_results(df, output_dir):
    fig, ax = plt.subplots(figsize=(8, 5))
    data, labels = [], []
    for cond in CONDITIONS:
        cdf = df[df["condition"] == cond]
        if not cdf.empty:
            data.append(cdf["rating_other_vs_standard"].values)
            labels.append(cond.replace("_", "\n"))
    if data:
        ax.boxplot(data, tick_labels=labels, showmeans=True)
    ax.axhline(0.5, color="gray", linestyle="--", alpha=0.5, label="no preference")
    ax.set_ylabel("P(K-dim summary preferred over standard)")
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
    embeddings, bt_scores, V, G, G_inv, mu, option_ids, dim_names = load_data(
        args.embeddings_parquet, args.bt_scores, args.directions,
        option_id_column=args.option_id_column,
    )
    N, d = embeddings.shape
    K = V.shape[0]
    print(f"  Options: {N}, d: {d}, K: {K}")

    dim_metadata = load_dimensions(args.dimensions)
    descriptions = load_option_descriptions(args.option_descriptions, args.option_template,
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
        "embeddings": embeddings, "V": V, "G": G, "G_inv": G_inv, "mu": mu,
        "quintile_bounds": quintile_bounds, "mults": DEFAULT_MULTS,
        "category_labels": category_labels,
        "dim_metadata": dim_metadata, "descriptions": descriptions,
        "option_ids": option_ids, "test_pairs": test_pairs,
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

    df = aggregate_results(per_persona_results)
    df.to_csv(output_dir / "per_persona_per_condition.csv", index=False)
    print(f"Saved per_persona_per_condition.csv ({len(df)} rows)")

    write_summary(df, args, output_dir)
    print("Saved summary.md")
    try:
        plot_results(df, output_dir)
        print("Saved predicted_dv.png")
    except Exception as e:
        print(f"Warning: could not save plot: {e}")
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
    p.add_argument("--lambda-partial", type=float, default=1.0)
    p.add_argument("--rating-temperature", type=float, default=20.0,
                   help="Larger τ for LLM sim because LL differences are smaller.")
    p.add_argument("--max-workers", type=int, default=4)
    p.add_argument("--seed", type=int, default=42)

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
