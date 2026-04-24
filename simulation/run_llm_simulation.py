"""
LLM-Persona Preference Learning Simulation

Replaces synthetic weight-vector users with LLM-driven personas.
Each simulated user is an LLM prompted with a naturalistic persona description
that makes choices and adjusts sliders the same way a human participant would.

Two-stage design:
  Stage 1: Generate diverse persona descriptions via LLM
  Stage 2: Run the preference learning loop with LLM choices + slider adjustments

Standalone script — does NOT import run_simulation.py.
"""

import argparse
import hashlib
import itertools
import json
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


# ---------------------------------------------------------------------------
# Data loading (copied from run_simulation.py — standalone, no cross-import)
# ---------------------------------------------------------------------------

def load_data(embeddings_parquet: str, bt_scores_csv: str, directions_npz: str,
              option_id_column: str = "movie_id"):
    """Load and align option representations.

    Returns
    -------
    embeddings : (N, d) float64
    bt_scores  : (N, K) float64
    V          : (K, d) float64  — direction matrix (unit-length rows, NOT orthogonal)
    G_inv      : (K, K) float64  — inverse Gram matrix (V V⊤)⁻¹
    mu         : (d,)  float64   — mean embedding
    option_ids : list of str
    dim_names  : list of str
    """
    parquet_df = pd.read_parquet(embeddings_parquet)
    parquet_df["option_id"] = parquet_df[option_id_column].astype(str)
    parquet_df = parquet_df.sort_values("option_id").reset_index(drop=True)
    option_ids = parquet_df["option_id"].tolist()
    embeddings = np.stack(parquet_df["embedding"].apply(np.array).values)

    bt_df = pd.read_csv(bt_scores_csv)
    bt_df["option_id"] = bt_df["option_id"].astype(str)
    dim_info = (
        bt_df[["dimension_id", "dimension_name"]]
        .drop_duplicates()
        .sort_values("dimension_id")
    )
    dim_names = dim_info["dimension_name"].tolist()
    dim_ids = dim_info["dimension_id"].tolist()
    bt_pivot = bt_df.pivot(index="option_id", columns="dimension_id", values="bt_score")
    bt_pivot = bt_pivot[dim_ids]
    bt_pivot = bt_pivot.loc[option_ids]
    bt_scores = bt_pivot.values.astype(np.float64)

    npz = np.load(directions_npz)
    V_raw = npz["directions_raw"].astype(np.float64)   # (K, d)
    mu = npz["mean_embedding"].astype(np.float64)

    # Normalize rows to unit length
    norms = np.linalg.norm(V_raw, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    V = V_raw / norms

    # Gram matrix and regularized inverse
    G = V @ V.T
    G_inv = np.linalg.inv(G + 1e-6 * np.eye(G.shape[0]))

    print(f"  Gram matrix condition number: {np.linalg.cond(G):.1f}")
    off_diag = G - np.eye(G.shape[0])
    print(f"  Max inter-dimension correlation: {np.abs(off_diag).max():.3f}")

    return embeddings, bt_scores, V, G_inv, mu, option_ids, dim_names


def load_dimensions(dimensions_json: str):
    """Load dimension metadata (names, poles) from dimensions.json."""
    with open(dimensions_json) as f:
        data = json.load(f)
    return data["dimensions"]


def load_option_descriptions(csv_path: str, template_path: str,
                             id_column: str = "movie_id"):
    """Load option descriptions by filling the template for each option.

    Returns dict mapping option_id (str) -> rendered description text.
    """
    df = pd.read_csv(csv_path)
    with open(template_path) as f:
        template = f.read().strip()

    descriptions = {}
    for _, row in df.iterrows():
        oid = str(row[id_column])
        try:
            text = template.format(**row.to_dict())
        except KeyError:
            # Fallback: concatenate all non-id columns
            parts = [f"{k}: {v}" for k, v in row.items()
                     if k != id_column and pd.notna(v) and str(v).strip()]
            text = " | ".join(parts)
        descriptions[oid] = text
    return descriptions


# ---------------------------------------------------------------------------
# LLM client + caching (matches method_llm_gen/pipeline.py client pattern)
# ---------------------------------------------------------------------------

PROVIDER_DEFAULTS = {
    "openai": {"base_url": "https://api.openai.com/v1", "env_key": "OPENAI_API_KEY"},
    "anthropic": {"base_url": "https://api.anthropic.com/v1", "env_key": "ANTHROPIC_API_KEY"},
}


class ClientPool:
    """Thread-safe round-robin pool over multiple OpenAI clients."""

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
        raise ValueError(
            f"Missing --api-key" + (f" (or set {env_hint})" if env_hint else "")
        )
    return OpenAI(base_url=base_url, api_key=api_key)


def make_client_or_pool(base_url, api_key, provider="local"):
    """Create a single client or a round-robin pool from comma-separated URLs."""
    if base_url and "," in base_url:
        urls = [u.strip() for u in base_url.split(",") if u.strip()]
        clients = [make_client(url, api_key, provider) for url in urls]
        print(f"[client] Round-robin pool with {len(clients)} endpoints", flush=True)
        return ClientPool(clients)
    return make_client(base_url, api_key, provider)


def _raw_llm_call(client, model, prompt, temperature, timeout, retries,
                  max_tokens: int = 1024):
    """Low-level LLM call with pool-aware retry (matches pipeline.py pattern)."""
    is_pool = isinstance(client, ClientPool)
    pool_size = client.size if is_pool else 1
    max_attempts = max(retries, pool_size)
    last_err = None
    for attempt in range(1, max_attempts + 1):
        resolved = client.next() if is_pool else client
        try:
            resp = resolved.chat.completions.create(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
                timeout=timeout,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            text = (resp.choices[0].message.content or "").strip()
            # Strip any <think> blocks that leaked through
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
            if "<think>" in text and "</think>" not in text:
                text = text[:text.index("<think>")].strip()
            return text
        except Exception as e:
            last_err = e
            is_conn = "Connection" in type(e).__name__
            if attempt < max_attempts:
                if not is_conn:
                    time.sleep(min(attempt, 3))
    raise last_err


class LLMClient:
    """Wrapper around the OpenAI-compatible API with disk caching and pool support."""

    def __init__(self, client, cache_path: Path | None = None,
                 timeout: int = 120, retries: int = 3):
        self.client = client
        self.timeout = timeout
        self.retries = retries
        self.cache_path = cache_path
        self._cache = {}
        self._cache_lock = threading.Lock()
        if cache_path and cache_path.exists():
            with open(cache_path) as f:
                self._cache = json.load(f)

    def call(self, model: str, prompt: str, temperature: float = 0.0,
             cache_key: str | None = None, max_tokens: int = 512) -> str:
        """Make a chat completion call, with optional caching."""
        if cache_key:
            with self._cache_lock:
                if cache_key in self._cache:
                    return self._cache[cache_key]

        text = _raw_llm_call(
            self.client, model, prompt, temperature,
            self.timeout, self.retries, max_tokens,
        )
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
# Stage 1: Persona generation
# ---------------------------------------------------------------------------

def generate_personas(client: LLMClient, model: str, num_personas: int) -> list[dict]:
    """Generate diverse persona descriptions via LLM."""
    prompt = f"""You are helping design a psychology experiment about movie preferences.

Generate {num_personas} diverse, realistic personas of people who watch movies. Each persona should be a short paragraph (3–5 sentences) describing the person's background, personality, and movie-watching habits in enough detail that you could predict which of two movies they'd prefer.

The personas should collectively represent meaningful variation in movie preferences. Include people who differ in age, background, and taste — not just genre preferences, but also preferences for things like pacing, emotional depth, visual style, humor, complexity, etc.

Do NOT make the personas cartoonish or one-dimensional. Real people have nuanced, sometimes contradictory tastes.

Return each persona in this format:

===PERSONA===
name: <first name and age>
description: <3–5 sentence description>"""

    text = client.call(model, prompt, temperature=0.7,
                       cache_key="persona_generation",
                       max_tokens=4096)

    # Strip <think> blocks from Qwen3
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if "<think>" in text and "</think>" not in text:
        # Unclosed think block — try to find content after it
        idx = text.index("<think>")
        text = text[:idx].strip()

    personas = []
    blocks = text.split("===PERSONA===")
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        name_match = re.search(r"name:\s*(.+)", block)
        desc_match = re.search(r"description:\s*(.+)", block, re.DOTALL)
        if name_match and desc_match:
            personas.append({
                "id": len(personas),
                "name": name_match.group(1).strip(),
                "description": desc_match.group(1).strip(),
            })

    if len(personas) < num_personas:
        print(f"  Warning: requested {num_personas} personas but parsed {len(personas)}")

    return personas[:num_personas]


# ---------------------------------------------------------------------------
# Stage 2: LLM choice and slider models
# ---------------------------------------------------------------------------

def build_choice_prompt(persona: dict, option_a_text: str, option_b_text: str) -> str:
    return f"""You are roleplaying as the following person. Stay in character and make choices as this person would — not as a neutral AI.

PERSONA:
{persona['description']}

---

You are choosing which movie to watch tonight. Read both options carefully, then choose the one this person would prefer.

OPTION A:
{option_a_text}

OPTION B:
{option_b_text}

Respond with valid JSON only:
{{"thinking": "<2–3 sentences of in-character reasoning about what draws this person to one option over the other>", "choice": "A" or "B"}}"""


def build_slider_prompt(persona: dict, choice_label: str, other_label: str,
                        dim_metadata: list[dict], slider_values: dict[str, int]) -> str:
    slider_lines = []
    for dim in dim_metadata:
        name = dim["name"]
        val = slider_values[name]
        low = dim["low_pole"]["label"]
        high = dim["high_pole"]["label"]
        slider_lines.append(f"- {name}: {val} (low pole: {low} ↔ high pole: {high})")

    return f"""You just chose Option {choice_label} over Option {other_label}.

The system has decomposed your choice into the following preference dimensions. Each slider ranges from -100 to +100, where positive means the chosen option scores higher on this dimension and negative means the unchosen option scores higher.

Review each slider value. Adjust any that don't reflect why THIS PERSON made this choice. If a dimension was irrelevant to the choice, set it closer to 0. If a dimension was the primary driver, make its magnitude larger.

PERSONA:
{persona['description']}

Current slider values:
{chr(10).join(slider_lines)}

Respond with valid JSON only:
{{"reasoning": "<1–2 sentences about which dimensions mattered most for this person's choice>", "adjusted_sliders": {{{", ".join(f'"{d["name"]}": <integer in [-100, 100]>' for d in dim_metadata)}}}}}"""


def parse_json_response(text: str) -> dict:
    """Extract JSON from an LLM response, handling markdown fences and truncation."""
    # Strip Qwen3 reasoning blocks
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    # Strip unclosed <think> blocks (model used all tokens on reasoning)
    if "<think>" in text and "</think>" not in text:
        text = text[:text.index("<think>")].strip()
    # Try to find JSON in code fences first
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        return json.loads(fence_match.group(1))
    # Try the whole text
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass
    # Last resort: response was truncated mid-JSON — extract whatever key-value
    # pairs are fully present using a line-by-line regex scan.
    partial: dict = {}
    for m in re.finditer(r'"(\w+)"\s*:\s*"((?:[^"\\]|\\.)*)"', text):
        partial[m.group(1)] = m.group(2)
    for m in re.finditer(r'"(\w+)"\s*:\s*(-?\d+)', text):
        partial[m.group(1)] = int(m.group(2))
    if partial:
        return partial
    raise ValueError(f"Could not parse JSON from LLM response: {text[:200]}")


def llm_choice(client: LLMClient, model: str, persona: dict,
               option_a_text: str, option_b_text: str,
               cache_key: str) -> dict:
    """Ask the LLM persona to choose between two options.

    Returns dict with keys: choice ('A' or 'B'), thinking (str).
    """
    prompt = build_choice_prompt(persona, option_a_text, option_b_text)
    text = client.call(model, prompt, temperature=0.3, cache_key=cache_key)
    parsed = parse_json_response(text)
    choice = parsed.get("choice", "A").strip().upper()
    if choice not in ("A", "B"):
        choice = "A"  # fallback
    return {"choice": choice, "thinking": parsed.get("thinking", "")}


def llm_slider_adjustment(client: LLMClient, model: str, persona: dict,
                          choice_label: str, other_label: str,
                          dim_metadata: list[dict], slider_values: dict[str, int],
                          cache_key: str) -> dict:
    """Ask the LLM persona to adjust slider values.

    Returns dict with keys: reasoning (str), adjusted_sliders (dict name->int).
    """
    prompt = build_slider_prompt(persona, choice_label, other_label,
                                 dim_metadata, slider_values)
    text = client.call(model, prompt, temperature=0.0, cache_key=cache_key,
                       max_tokens=1024)
    parsed = parse_json_response(text)
    adjusted = parsed.get("adjusted_sliders", {})
    # Clamp values to [-100, 100]
    for name in adjusted:
        try:
            adjusted[name] = max(-100, min(100, int(adjusted[name])))
        except (ValueError, TypeError):
            adjusted[name] = slider_values.get(name, 0)
    return {"reasoning": parsed.get("reasoning", ""), "adjusted_sliders": adjusted}


# ---------------------------------------------------------------------------
# Gradient updates (copied from run_simulation.py — standalone)
# ---------------------------------------------------------------------------

def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -50, 50)))


def update_standard(theta, phi_a, phi_b, y, lr):
    delta = phi_a - phi_b
    pred = sigmoid(theta @ delta)
    return theta + lr * (y - pred) * delta


def update_projected(theta, phi_a, phi_b, y, lr, V, G_inv):
    """Condition 2: Gradient projected onto interpretable subspace.

    With non-orthogonal V, the oblique projector is P = V⊤ G⁻¹ V.
    """
    delta = phi_a - phi_b
    pred = sigmoid(theta @ delta)
    grad = (y - pred) * delta
    lam = V @ grad
    projected_grad = V.T @ (G_inv @ lam)
    return theta + lr * projected_grad


def update_slider(theta, phi_a, phi_b, y, lr, V, G_inv, lam_adjusted):
    """Condition 3: Slider-adjusted gradient.

    Sliders provide importance-weighted magnitudes.
    Direction comes from (y - pred). G⁻¹ decorrelates before lifting.
    """
    delta = phi_a - phi_b
    pred = sigmoid(theta @ delta)
    grad_direction = V.T @ (G_inv @ lam_adjusted)
    return theta + lr * (y - pred) * grad_direction


def update_partial(theta, phi_a, phi_b, y, lr, V, G_inv, lam_adjusted, proj_lambda):
    """Condition 4: Interpolation between standard and slider-adjusted."""
    delta = phi_a - phi_b
    pred = sigmoid(theta @ delta)
    scalar = y - pred
    standard_part = scalar * delta
    slider_part = scalar * (V.T @ (G_inv @ lam_adjusted))
    return theta + lr * ((1 - proj_lambda) * standard_part + proj_lambda * slider_part)


# ---------------------------------------------------------------------------
# Evaluation (adapted — no ground-truth weights)
# ---------------------------------------------------------------------------

def evaluate_choice_prediction(thetas: dict, test_pairs: np.ndarray,
                               test_choices: np.ndarray,
                               embeddings: np.ndarray) -> dict:
    """Compute choice prediction accuracy and log-likelihood for each condition.

    No ground-truth weights available, so utility correlation / weight recovery
    are omitted.
    """
    results = {}
    for cond, theta in thetas.items():
        idx_a = test_pairs[:, 0]
        idx_b = test_pairs[:, 1]
        delta_test = embeddings[idx_a] - embeddings[idx_b]
        logits = delta_test @ theta
        probs = sigmoid(logits)

        preds = (probs > 0.5).astype(int)
        accuracy = np.mean(preds == test_choices)

        eps = 1e-10
        ll = np.mean(
            test_choices * np.log(probs + eps)
            + (1 - test_choices) * np.log(1 - probs + eps)
        )
        results[cond] = {"accuracy": accuracy, "log_likelihood": ll}
    return results


# ---------------------------------------------------------------------------
# Main simulation
# ---------------------------------------------------------------------------

def run_simulation(args):
    rng = np.random.default_rng(args.seed)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- LLM client (matches method_llm_gen/pipeline.py pattern) ---
    raw_client = make_client_or_pool(args.base_url, args.api_key, args.api_provider)
    client = LLMClient(
        raw_client,
        cache_path=output_dir / "llm_cache.json",
    )

    # --- Load data ---
    print("Loading data...")
    embeddings, bt_scores, V, G_inv, mu, option_ids, dim_names = load_data(
        args.embeddings_parquet, args.bt_scores, args.directions,
        option_id_column=args.option_id_column,
    )
    N, d = embeddings.shape
    K = V.shape[0]
    print(f"  Options: {N}, Embedding dim: {d}, Dimensions: {K}")
    print(f"  Dimensions: {dim_names}")

    dim_metadata = load_dimensions(args.dimensions_json)
    descriptions = load_option_descriptions(args.option_descriptions, args.option_template,
                                             id_column=args.option_id_column)

    # --- Stage 1: Generate personas ---
    print("Generating personas...")
    personas = generate_personas(client, args.persona_model, args.num_personas)
    print(f"  Generated {len(personas)} personas")

    # Save personas
    with open(output_dir / "personas.json", "w") as f:
        json.dump(personas, f, indent=2)
    print("  Saved personas.json")
    client.save_cache()

    # --- Build test pairs (shared across personas) ---
    test_idx_a = rng.integers(0, N, size=args.num_test_pairs)
    test_idx_b = rng.integers(0, N, size=args.num_test_pairs)
    mask = test_idx_a == test_idx_b
    while mask.any():
        test_idx_b[mask] = rng.integers(0, N, size=mask.sum())
        mask = test_idx_a == test_idx_b
    test_pairs = np.stack([test_idx_a, test_idx_b], axis=1)

    # --- Build consistency check pairs (10 duplicate pairs per persona) ---
    n_consistency = 10
    consistency_idx_a = rng.integers(0, N, size=n_consistency)
    consistency_idx_b = rng.integers(0, N, size=n_consistency)
    mask = consistency_idx_a == consistency_idx_b
    while mask.any():
        consistency_idx_b[mask] = rng.integers(0, N, size=mask.sum())
        mask = consistency_idx_a == consistency_idx_b

    conditions = ["standard", "projected", "slider", "partial"]

    def simulate_one_persona(persona):
        """Run the full simulation for a single persona. Thread-safe."""
        pid = persona["id"]
        # Each persona gets its own RNG seeded deterministically to avoid races
        persona_rng = np.random.default_rng(args.seed + pid)
        N, d = embeddings.shape
        K = V.shape[0]

        lc_rows_p = []
        choice_log_rows_p = []
        consistency_rows_p = []

        print(f"  Persona {pid}: {persona['name']}", flush=True)

        # --- Generate test set choices BEFORE training ---
        print(f"    [{pid}] Collecting test set choices ({args.num_test_pairs} pairs)...", flush=True)
        test_choices = np.zeros(args.num_test_pairs, dtype=int)
        for ti in range(args.num_test_pairs):
            oid_a = option_ids[test_pairs[ti, 0]]
            oid_b = option_ids[test_pairs[ti, 1]]
            cache_key = f"test_choice_{pid}_{oid_a}_{oid_b}"
            result = llm_choice(
                client, args.choice_model, persona,
                descriptions[oid_a], descriptions[oid_b],
                cache_key=cache_key,
            )
            test_choices[ti] = 1 if result["choice"] == "A" else 0

        # --- Consistency check ---
        print(f"    [{pid}] Running consistency check ({n_consistency} pairs)...", flush=True)
        for ci in range(n_consistency):
            oid_a = option_ids[consistency_idx_a[ci]]
            oid_b = option_ids[consistency_idx_b[ci]]

            cache_key_1 = f"consistency1_{pid}_{oid_a}_{oid_b}"
            r1 = llm_choice(client, args.choice_model, persona,
                            descriptions[oid_a], descriptions[oid_b],
                            cache_key=cache_key_1)

            # Different cache key to force re-query
            cache_key_2 = f"consistency2_{pid}_{oid_a}_{oid_b}"
            r2 = llm_choice(client, args.choice_model, persona,
                            descriptions[oid_a], descriptions[oid_b],
                            cache_key=cache_key_2)

            consistency_rows_p.append({
                "persona_id": pid,
                "option_a_id": oid_a,
                "option_b_id": oid_b,
                "choice_1": r1["choice"],
                "choice_2": r2["choice"],
                "consistent": int(r1["choice"] == r2["choice"]),
            })

        # --- Initialize θ for each condition ---
        thetas = {c: np.zeros(d) for c in conditions}

        # Evaluate at trial 0
        metrics_0 = evaluate_choice_prediction(thetas, test_pairs, test_choices, embeddings)
        for cond in conditions:
            row = {"persona_id": pid, "condition": cond, "trial": 0}
            row.update(metrics_0[cond])
            lc_rows_p.append(row)

        # --- Training loop ---
        print(f"    [{pid}] Training ({args.num_trials} trials)...", flush=True)
        for t in range(1, args.num_trials + 1):
            idx_a, idx_b = persona_rng.choice(N, size=2, replace=False)
            oid_a = option_ids[idx_a]
            oid_b = option_ids[idx_b]
            phi_a = embeddings[idx_a]
            phi_b = embeddings[idx_b]

            choice_cache_key = f"train_choice_{pid}_{t}_{oid_a}_{oid_b}"
            choice_result = llm_choice(
                client, args.choice_model, persona,
                descriptions[oid_a], descriptions[oid_b],
                cache_key=choice_cache_key,
            )
            y = 1 if choice_result["choice"] == "A" else 0

            # Compute model slider values in A-B frame (always)
            delta_ab = phi_a - phi_b
            lam_model = V @ delta_ab

            lam_abs_max = np.abs(lam_model).max()
            scale_factor = 100.0 / lam_abs_max if lam_abs_max > 0 else 1.0

            # For display to the LLM persona, show in chosen-vs-unchosen frame
            if y == 1:
                choice_label, other_label = "A", "B"
                lam_display = lam_model
            else:
                choice_label, other_label = "B", "A"
                lam_display = -lam_model  # flip for display only

            slider_values_display = {
                dim["name"]: int(np.round(lam_display[k] * scale_factor))
                for k, dim in enumerate(dim_metadata)
            }

            slider_cache_key = f"train_slider_{pid}_{t}_{oid_a}_{oid_b}"
            slider_result = llm_slider_adjustment(
                client, args.choice_model, persona,
                choice_label, other_label,
                dim_metadata, slider_values_display,
                cache_key=slider_cache_key,
            )

            adjusted_sliders = slider_result["adjusted_sliders"]
            # Convert LLM's adjustments back to A-B frame
            # LLM sees chosen-vs-unchosen; when y=0 (chose B), flip sign back
            sign = 1.0 if y == 1 else -1.0
            lam_adjusted = np.array([
                sign * adjusted_sliders.get(dim["name"], lam_display[k]) / scale_factor
                for k, dim in enumerate(dim_metadata)
            ])

            choice_log_rows_p.append({
                "persona_id": pid,
                "trial": t,
                "option_a_id": oid_a,
                "option_b_id": oid_b,
                "choice": choice_result["choice"],
                "thinking": choice_result["thinking"],
                "raw_sliders": json.dumps(slider_values_display),
                "adjusted_sliders": json.dumps(adjusted_sliders),
            })

            thetas["standard"] = update_standard(thetas["standard"], phi_a, phi_b, y, args.learning_rate)
            thetas["projected"] = update_projected(thetas["projected"], phi_a, phi_b, y, args.learning_rate, V, G_inv)
            thetas["slider"] = update_slider(thetas["slider"], phi_a, phi_b, y, args.learning_rate, V, G_inv, lam_adjusted)
            thetas["partial"] = update_partial(
                thetas["partial"], phi_a, phi_b, y, args.learning_rate, V, G_inv, lam_adjusted, args.projection_lambda
            )

            metrics = evaluate_choice_prediction(thetas, test_pairs, test_choices, embeddings)
            for cond in conditions:
                row = {"persona_id": pid, "condition": cond, "trial": t}
                row.update(metrics[cond])
                lc_rows_p.append(row)

            if t % 10 == 0:
                print(f"      [{pid}] Trial {t}/{args.num_trials}", flush=True)

        client.save_cache()
        print(f"  Persona {pid} done.", flush=True)
        return lc_rows_p, choice_log_rows_p, consistency_rows_p

    # --- Run personas in parallel ---
    print("Running simulation...")
    lc_rows = []
    choice_log_rows = []
    consistency_rows = []

    max_workers = getattr(args, "max_workers", 4)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(simulate_one_persona, p): p for p in personas}
        for future in as_completed(futures):
            persona = futures[future]
            try:
                p_lc, p_choices, p_consistency = future.result()
                lc_rows.extend(p_lc)
                choice_log_rows.extend(p_choices)
                consistency_rows.extend(p_consistency)
            except Exception as e:
                print(f"  Persona {persona['id']} failed: {e}", flush=True)
                raise

    # --- Save outputs ---
    print("Saving outputs...")

    # 1. learning_curves.csv
    lc_df = pd.DataFrame(lc_rows)
    lc_df.to_csv(output_dir / "learning_curves.csv", index=False)
    print(f"  learning_curves.csv ({len(lc_df)} rows)")

    # 2. choices_log.csv
    choices_df = pd.DataFrame(choice_log_rows)
    choices_df.to_csv(output_dir / "choices_log.csv", index=False)
    print(f"  choices_log.csv ({len(choices_df)} rows)")

    # 3. consistency_check.csv
    consistency_df = pd.DataFrame(consistency_rows)
    consistency_df.to_csv(output_dir / "consistency_check.csv", index=False)
    print(f"  consistency_check.csv ({len(consistency_df)} rows)")

    # 4. summary.md
    print(f"  lc_df shape: {lc_df.shape}, columns: {list(lc_df.columns)}")
    if lc_df.empty or "trial" not in lc_df.columns:
        print("  WARNING: learning curves DataFrame is empty or missing 'trial' column. Skipping summary.")
    else:
        write_summary(lc_df, consistency_df, personas, conditions, dim_names, args, output_dir)
        print("  summary.md")

    # 5. learning_curves.png
    try:
        plot_learning_curves(lc_df, conditions, output_dir)
        print("  learning_curves.png")
    except Exception as e:
        print(f"  Warning: could not save plot: {e}")

    # Final cache save
    client.save_cache()
    print("Done.")


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def write_summary(lc_df, consistency_df, personas, conditions, dim_names, args, output_dir):
    lines = []
    lines.append("# LLM-Persona Simulation Summary\n")

    lines.append("## Experimental Parameters\n")
    lines.append("| Parameter | Value |")
    lines.append("|-----------|-------|")
    lines.append(f"| Number of personas | {len(personas)} |")
    lines.append(f"| Persona model | {args.persona_model} |")
    lines.append(f"| Choice model | {args.choice_model} |")
    lines.append(f"| Number of trials | {args.num_trials} |")
    lines.append(f"| Number of test pairs | {args.num_test_pairs} |")
    lines.append(f"| Number of dimensions (K) | {len(dim_names)} |")
    lines.append(f"| Dimensions | {', '.join(dim_names)} |")
    lines.append(f"| Learning rate | {args.learning_rate} |")
    lines.append(f"| Projection lambda (partial) | {args.projection_lambda} |")
    lines.append(f"| Random seed | {args.seed} |")
    lines.append("")

    # Final metrics table
    final_df = lc_df[lc_df["trial"] == args.num_trials]
    lines.append("## Final Performance (at last trial)\n")
    headers = ["Condition", "Accuracy", "Log-Likelihood"]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for cond in conditions:
        cdf = final_df[final_df["condition"] == cond]
        acc = cdf["accuracy"].mean()
        ll = cdf["log_likelihood"].mean()
        lines.append(f"| {cond} | {acc:.3f} | {ll:.4f} |")
    lines.append("")

    # Learning curve summary (accuracy at every 10 trials)
    lines.append("## Learning Curve (Average Accuracy by Trial)\n")
    milestone_trials = [0] + list(range(10, args.num_trials + 1, 10))
    headers2 = ["Trial"] + conditions
    lines.append("| " + " | ".join(headers2) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers2)) + " |")
    for t in milestone_trials:
        tdf = lc_df[lc_df["trial"] == t]
        row_parts = [str(t)]
        for cond in conditions:
            val = tdf[tdf["condition"] == cond]["accuracy"].mean()
            row_parts.append(f"{val:.3f}")
        lines.append("| " + " | ".join(row_parts) + " |")
    lines.append("")

    # Threshold analysis
    threshold = 0.75
    lines.append(f"## First Trial to Reach {int(threshold*100)}% Accuracy\n")
    lines.append("| Condition | First Trial >= 75% Accuracy |")
    lines.append("|-----------|---------------------------|")
    for cond in conditions:
        cdf = lc_df[lc_df["condition"] == cond].groupby("trial")["accuracy"].mean()
        reached = cdf[cdf >= threshold]
        if reached.empty:
            lines.append(f"| {cond} | Never reached |")
        else:
            lines.append(f"| {cond} | {reached.index[0]} |")
    lines.append("")

    # Consistency check
    if len(consistency_df) > 0:
        lines.append("## Internal Consistency\n")
        overall_rate = consistency_df["consistent"].mean()
        lines.append(f"Overall consistency rate: **{overall_rate:.1%}**\n")
        lines.append("| Persona | Name | Consistency Rate |")
        lines.append("|---------|------|-----------------|")
        for persona in sorted(consistency_df["persona_id"].unique()):
            pdf = consistency_df[consistency_df["persona_id"] == persona]
            rate = pdf["consistent"].mean()
            # Find persona name
            pname = next((p["name"] for p in personas if p["id"] == persona), str(persona))  # noqa: B023
            lines.append(f"| {persona} | {pname} | {rate:.0%} |")
        lines.append("")

    # Key findings
    lines.append("## Key Findings\n")
    final_accs = {}
    for cond in conditions:
        final_accs[cond] = final_df[final_df["condition"] == cond]["accuracy"].mean()
    best = max(final_accs, key=final_accs.get)
    lines.append(f"- **Best final accuracy**: {best} ({final_accs[best]:.3f})")
    lines.append(f"- **Standard baseline accuracy**: {final_accs['standard']:.3f}")
    gain = final_accs["slider"] - final_accs["standard"]
    lines.append(f"- **Slider vs standard gain**: {gain:+.3f}")

    with open(output_dir / "summary.md", "w") as f:
        f.write("\n".join(lines) + "\n")


def plot_learning_curves(lc_df, conditions, output_dir):
    condition_colors = {
        "standard": "#e74c3c",
        "projected": "#3498db",
        "slider": "#2ecc71",
        "partial": "#9b59b6",
    }
    condition_labels = {
        "standard": "Standard (baseline)",
        "projected": "Projected",
        "slider": "Slider-adjusted",
        "partial": "Partial projection",
    }

    trials = sorted(lc_df["trial"].unique())

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    for ax_idx, (metric, ylabel) in enumerate([
        ("accuracy", "Choice Prediction Accuracy"),
        ("log_likelihood", "Choice Prediction Log-Likelihood"),
    ]):
        ax = axes[ax_idx]
        for cond in conditions:
            cdf = lc_df[lc_df["condition"] == cond]
            means = []
            sems = []
            for t in trials:
                vals = cdf[cdf["trial"] == t][metric].dropna().values
                means.append(vals.mean())
                sems.append(vals.std() / np.sqrt(max(len(vals), 1)))
            means = np.array(means)
            sems = np.array(sems)
            color = condition_colors.get(cond, "gray")
            label = condition_labels.get(cond, cond)
            ax.plot(trials, means, label=label, color=color, linewidth=2)
            ax.fill_between(trials, means - sems, means + sems, alpha=0.2, color=color)

        ax.set_xlabel("Trial", fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_title(ylabel, fontsize=13, fontweight="bold")
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        if metric == "accuracy":
            ax.axhline(0.75, color="gray", linestyle="--", alpha=0.5)
        ax.set_xlim(0, max(trials))

    fig.suptitle("LLM-Persona Simulation: Gradient Projection Comparison",
                 fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(output_dir / "learning_curves.png", dpi=150, bbox_inches="tight")
    plt.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="LLM-persona preference learning simulation."
    )
    parser.add_argument("--embeddings-parquet", required=True,
                        help="Path to the embeddings parquet file.")
    parser.add_argument("--bt-scores", required=True,
                        help="Path to bt_scores.csv.")
    parser.add_argument("--dimensions", required=True,
                        help="Path to dimensions.json.")
    parser.add_argument("--directions", required=True,
                        help="Path to directions.npz.")
    parser.add_argument("--option-descriptions", required=True,
                        help="Path to the option descriptions CSV.")
    parser.add_argument("--option-template", required=True,
                        help="Path to the option template text file.")
    parser.add_argument("--output-dir", required=True,
                        help="Directory to write outputs into.")
    parser.add_argument("--api-provider", choices=["local", "openai", "anthropic"],
                        default="local",
                        help="API provider (determines default base-url and env key).")
    parser.add_argument("--base-url",
                        help="API endpoint URL(s), comma-separated for round-robin across multiple servers.")
    parser.add_argument("--persona-model", default="gpt-4o-mini",
                        help="Model for persona generation (Stage 1).")
    parser.add_argument("--choice-model", default="gpt-4o-mini",
                        help="Model for choices and sliders (Stage 2).")
    parser.add_argument("--api-key", default=None,
                        help="API key (defaults to provider env var).")
    parser.add_argument("--num-personas", type=int, default=20,
                        help="Number of personas to generate.")
    parser.add_argument("--num-trials", type=int, default=50,
                        help="Training trials per persona.")
    parser.add_argument("--num-test-pairs", type=int, default=50,
                        help="Held-out test pairs per persona.")
    parser.add_argument("--learning-rate", type=float, default=0.01,
                        help="Gradient update learning rate.")
    parser.add_argument("--projection-lambda", type=float, default=0.5,
                        help="Interpolation weight for partial projection.")
    parser.add_argument("--max-workers", type=int, default=4,
                        help="Number of personas to simulate in parallel.")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed.")
    parser.add_argument("--option-id-column", default="movie_id",
                        help="Name of the option-id column in the parquet file (default: movie_id).")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    # The --dimensions flag maps to dimensions_json internally
    args.dimensions_json = args.dimensions
    run_simulation(args)
