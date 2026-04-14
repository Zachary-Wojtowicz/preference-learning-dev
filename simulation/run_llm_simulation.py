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

def load_data(embeddings_parquet: str, bt_scores_csv: str, directions_npz: str):
    """Load and align option representations.

    Returns
    -------
    embeddings : (N, d) float64
    bt_scores  : (N, K) float64
    V          : (K, d) float64  — orthonormal direction matrix
    mu         : (d,)  float64   — mean embedding
    option_ids : list of str
    dim_names  : list of str
    """
    parquet_df = pd.read_parquet(embeddings_parquet)
    parquet_df["option_id"] = parquet_df["movie_id"].astype(str)
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
    V = npz["directions_ortho"].astype(np.float64)
    mu = npz["mean_embedding"].astype(np.float64)

    return embeddings, bt_scores, V, mu, option_ids, dim_names


def load_dimensions(dimensions_json: str):
    """Load dimension metadata (names, poles) from dimensions.json."""
    with open(dimensions_json) as f:
        data = json.load(f)
    return data["dimensions"]


def load_option_descriptions(csv_path: str, template_path: str):
    """Load option descriptions by filling the template for each option.

    Returns dict mapping option_id (str) -> rendered description text.
    """
    df = pd.read_csv(csv_path)
    with open(template_path) as f:
        template = f.read().strip()

    descriptions = {}
    for _, row in df.iterrows():
        oid = str(row["movie_id"])
        text = template.format(
            title=row["title"],
            genres=row["genres"],
            director=row["director"],
            stars=row["stars"],
            plot_summary=row["plot_summary"],
        )
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


def _raw_llm_call(client, model, prompt, temperature, timeout, retries):
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
                messages=[{"role": "user", "content": prompt}],
                timeout=timeout,
            )
            return (resp.choices[0].message.content or "").strip()
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
        if cache_path and cache_path.exists():
            with open(cache_path) as f:
                self._cache = json.load(f)

    def call(self, model: str, prompt: str, temperature: float = 0.0,
             cache_key: str | None = None) -> str:
        """Make a chat completion call, with optional caching."""
        if cache_key and cache_key in self._cache:
            return self._cache[cache_key]

        text = _raw_llm_call(
            self.client, model, prompt, temperature,
            self.timeout, self.retries,
        )
        if cache_key:
            self._cache[cache_key] = text
        return text

    def save_cache(self):
        if self.cache_path:
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

    text = client.call(model, prompt, temperature=0.7, cache_key="persona_generation")

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
    """Extract JSON from an LLM response, handling markdown fences."""
    # Try to find JSON in code fences first
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        return json.loads(fence_match.group(1))
    # Try the whole text
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        return json.loads(brace_match.group(0))
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
    text = client.call(model, prompt, temperature=0.0, cache_key=cache_key)
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


def update_projected(theta, phi_a, phi_b, y, lr, V):
    delta = phi_a - phi_b
    pred = sigmoid(theta @ delta)
    grad = (y - pred) * delta
    projected_grad = V.T @ (V @ grad)
    return theta + lr * projected_grad


def update_slider(theta, phi_a, phi_b, y, lr, V, lam_adjusted):
    delta = phi_a - phi_b
    pred = sigmoid(theta @ delta)
    grad_direction = V.T @ lam_adjusted
    return theta + lr * (y - pred) * grad_direction


def update_partial(theta, phi_a, phi_b, y, lr, V, lam_adjusted, proj_lambda):
    delta = phi_a - phi_b
    pred = sigmoid(theta @ delta)
    scalar = y - pred
    standard_part = scalar * delta
    slider_part = scalar * (V.T @ lam_adjusted)
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
    embeddings, bt_scores, V, mu, option_ids, dim_names = load_data(
        args.embeddings_parquet, args.bt_scores, args.directions
    )
    N, d = embeddings.shape
    K = V.shape[0]
    print(f"  Options: {N}, Embedding dim: {d}, Dimensions: {K}")
    print(f"  Dimensions: {dim_names}")

    dim_metadata = load_dimensions(args.dimensions_json)
    descriptions = load_option_descriptions(args.option_descriptions, args.option_template)

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
    lc_rows = []
    choice_log_rows = []
    consistency_rows = []

    # --- Per-persona simulation ---
    print("Running simulation...")
    for persona in personas:
        pid = persona["id"]
        print(f"  Persona {pid}: {persona['name']}")

        # --- Generate test set choices BEFORE training ---
        print(f"    Collecting test set choices ({args.num_test_pairs} pairs)...")
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
        print(f"    Running consistency check ({n_consistency} pairs)...")
        for ci in range(n_consistency):
            oid_a = option_ids[consistency_idx_a[ci]]
            oid_b = option_ids[consistency_idx_b[ci]]

            # First query (may reuse test set cache if same pair)
            cache_key_1 = f"consistency1_{pid}_{oid_a}_{oid_b}"
            r1 = llm_choice(client, args.choice_model, persona,
                            descriptions[oid_a], descriptions[oid_b],
                            cache_key=cache_key_1)

            # Second query — different cache key to force re-query
            cache_key_2 = f"consistency2_{pid}_{oid_a}_{oid_b}"
            r2 = llm_choice(client, args.choice_model, persona,
                            descriptions[oid_a], descriptions[oid_b],
                            cache_key=cache_key_2)

            consistency_rows.append({
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
            lc_rows.append(row)

        # --- Training loop ---
        print(f"    Training ({args.num_trials} trials)...")
        for t in range(1, args.num_trials + 1):
            # Sample a pair
            idx_a, idx_b = rng.choice(N, size=2, replace=False)
            oid_a = option_ids[idx_a]
            oid_b = option_ids[idx_b]
            phi_a = embeddings[idx_a]
            phi_b = embeddings[idx_b]

            # --- LLM choice ---
            choice_cache_key = f"train_choice_{pid}_{t}_{oid_a}_{oid_b}"
            choice_result = llm_choice(
                client, args.choice_model, persona,
                descriptions[oid_a], descriptions[oid_b],
                cache_key=choice_cache_key,
            )
            y = 1 if choice_result["choice"] == "A" else 0

            # --- Compute model slider values: λ_model = V⊤(φ(chosen) − φ(unchosen)) ---
            if y == 1:
                phi_chosen, phi_unchosen = phi_a, phi_b
                choice_label, other_label = "A", "B"
            else:
                phi_chosen, phi_unchosen = phi_b, phi_a
                choice_label, other_label = "B", "A"

            delta_chosen = phi_chosen - phi_unchosen
            lam_model = V @ delta_chosen  # (K,)

            # Scale to [-100, 100] for display
            lam_abs_max = np.abs(lam_model).max()
            if lam_abs_max > 0:
                scale_factor = 100.0 / lam_abs_max
            else:
                scale_factor = 1.0
            slider_values_display = {}
            for k, dim in enumerate(dim_metadata):
                slider_values_display[dim["name"]] = int(np.round(lam_model[k] * scale_factor))

            # --- LLM slider adjustment ---
            slider_cache_key = f"train_slider_{pid}_{t}_{oid_a}_{oid_b}"
            slider_result = llm_slider_adjustment(
                client, args.choice_model, persona,
                choice_label, other_label,
                dim_metadata, slider_values_display,
                cache_key=slider_cache_key,
            )

            # Convert adjusted sliders back to raw scale
            adjusted_sliders = slider_result["adjusted_sliders"]
            lam_adjusted = np.zeros(K)
            for k, dim in enumerate(dim_metadata):
                name = dim["name"]
                if name in adjusted_sliders:
                    lam_adjusted[k] = adjusted_sliders[name] / scale_factor
                else:
                    lam_adjusted[k] = lam_model[k]

            # --- Log the choice ---
            choice_log_rows.append({
                "persona_id": pid,
                "trial": t,
                "option_a_id": oid_a,
                "option_b_id": oid_b,
                "choice": choice_result["choice"],
                "thinking": choice_result["thinking"],
                "raw_sliders": json.dumps(slider_values_display),
                "adjusted_sliders": json.dumps(adjusted_sliders),
            })

            # --- Update each condition ---
            thetas["standard"] = update_standard(thetas["standard"], phi_a, phi_b, y, args.learning_rate)
            thetas["projected"] = update_projected(thetas["projected"], phi_a, phi_b, y, args.learning_rate, V)
            thetas["slider"] = update_slider(thetas["slider"], phi_a, phi_b, y, args.learning_rate, V, lam_adjusted)
            thetas["partial"] = update_partial(
                thetas["partial"], phi_a, phi_b, y, args.learning_rate, V, lam_adjusted, args.projection_lambda
            )

            # --- Evaluate ---
            metrics = evaluate_choice_prediction(thetas, test_pairs, test_choices, embeddings)
            for cond in conditions:
                row = {"persona_id": pid, "condition": cond, "trial": t}
                row.update(metrics[cond])
                lc_rows.append(row)

            if t % 10 == 0:
                print(f"      Trial {t}/{args.num_trials}")

        # Save cache periodically (after each persona)
        client.save_cache()
        print(f"  Persona {pid} done.")

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
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    # The --dimensions flag maps to dimensions_json internally
    args.dimensions_json = args.dimensions
    run_simulation(args)
