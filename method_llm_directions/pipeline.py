#!/usr/bin/env python3
"""
method_llm_directions/pipeline.py

LLM-guided direction finding: generate many candidate axes via diverse LLM
strategies, score a wine sample to get ridge regression directions, then
greedily select the K axes that maximize variance coverage.

Stages (each resumes automatically if its output exists):
  generate         — 5 LLM strategies → candidate_axes.json   (~100 axes)
  score-sample     — LLM batch-scores N wines per axis         → sample_scores.npz
  fit-directions   — RidgeCV per axis on scored sample         → axis_directions.npz
  project          — Project full dataset onto all directions  → projection_scores.npz
  select           — Greedy variance-coverage selection        → selected_axes.json
  report           — Coverage / independence / r_j report      → report.md
  run-all          — All stages in sequence

Why LLM scores + ridge regression instead of embedding similarity
------------------------------------------------------------------
Keyword or pole-embedding cosine tricks live in a different or poorly-aligned
space from the pre-computed wine embeddings. Ridge regression finds the best
linear direction in the actual wine embedding space that predicts the LLM's
scores, giving us a direction that is both interpretable and grounded in the
data geometry. With ~100 scored wines per axis (100 LLM calls, one axis per
call) and RidgeCV this is fast and accurate enough for direction discovery.

Selection objective
-------------------
We maximize total variance coverage:  coverage(V) = tr(V C V^T) / tr(C)
using greedy Gram-Schmidt in projected score space. At each step the axis
added is the one with the highest residual variance after projecting out the
directions already selected. This gives the 2-approximation to the optimal
K-subset for variance coverage (equivalent to greedy OMP).

The selected directions are QR-orthogonalised and saved in the format
expected by method_directions/evaluate_basis.py.
"""

import argparse
import concurrent.futures
import itertools
import json
import os
import random
import re
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from sklearn.linear_model import RidgeCV

# ─────────────────────────────────────────────────────────────────────────────
# Constants / defaults
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parent / "outputs"
DEFAULT_TIMEOUT     = 90
DEFAULT_RETRIES     = 3
PROVIDER_DEFAULTS   = {
    "openai":    {"base_url": "https://api.openai.com/v1",             "env_key": "OPENAI_API_KEY"},
    "anthropic": {"base_url": "https://api.anthropic.com/v1",          "env_key": "ANTHROPIC_API_KEY"},
    "nvidia":    {"base_url": "https://integrate.api.nvidia.com/v1",   "env_key": "NVIDIA_API_KEY"},
}

_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def _load_dotenv():
    """Load key=value pairs from project .env into os.environ (if present)."""
    if not _ENV_FILE.exists():
        return
    for line in _ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if k and k not in os.environ:
            os.environ[k] = v


_load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subs = p.add_subparsers(dest="command", required=True)

    def add_base(sub):
        sub.add_argument("--config",     required=True)
        sub.add_argument("--output-dir", default=None)
        sub.add_argument("--seed",       type=int, default=42)
        return sub

    def add_llm(sub):
        sub.add_argument("--provider",   choices=["openai", "anthropic", "nvidia", "local"],
                         default="nvidia")
        sub.add_argument("--base-url",   default=None)
        sub.add_argument("--model",      default="meta/llama-3.3-70b-instruct")
        sub.add_argument("--api-key",    default=None)
        sub.add_argument("--max-workers", type=int, default=8)
        return sub

    for name in ["generate", "score-sample", "fit-directions",
                 "project", "select", "report", "run-all"]:
        sub = add_base(subs.add_parser(name))
        if name in ("generate", "score-sample", "run-all"):
            add_llm(sub)

    return p.parse_args()


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────
def load_json(path):
    return json.loads(Path(path).read_text("utf-8"))


def save_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")


def make_client(base_url, api_key, provider):
    from openai import OpenAI
    d        = PROVIDER_DEFAULTS.get(provider, {})
    base_url = base_url or d.get("base_url")
    api_key  = api_key  or os.environ.get(d.get("env_key", ""), "") or "x"
    if not base_url:
        raise ValueError(f"--base-url required for provider='{provider}'")
    return OpenAI(base_url=base_url, api_key=api_key)


class ClientPool:
    def __init__(self, clients):
        self._cycle = itertools.cycle(clients)
        self._lock  = threading.Lock()
        self.size   = len(clients)

    def next(self):
        with self._lock:
            return next(self._cycle)


def make_client_or_pool(base_url, api_key, provider):
    if base_url and "," in base_url:
        urls = [u.strip() for u in base_url.split(",") if u.strip()]
        return ClientPool([make_client(u, api_key, provider) for u in urls])
    return make_client(base_url, api_key, provider)


_VALID_ESCAPES = set('"\\/ bfnrtu')


def _fix_escapes(s):
    result, i = [], 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            result.append(s[i] if s[i + 1] in _VALID_ESCAPES else "\\\\")
            i += 1
        else:
            result.append(s[i])
        i += 1
    return "".join(result)


def parse_json_blob(content):
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    for extractor in [
        lambda c: json.loads(c),
        lambda c: json.loads(c[c.find("["):c.rfind("]") + 1]),
        lambda c: json.loads(_fix_escapes(c[c.find("["):c.rfind("]") + 1])),
        lambda c: json.loads(c[c.find("{"):c.rfind("}") + 1]),
        lambda c: json.loads(_fix_escapes(c[c.find("{"):c.rfind("}") + 1])),
    ]:
        try:
            return extractor(content)
        except Exception:
            continue
    raise ValueError(f"Could not parse JSON:\n{content[:500]}")


def _is_rate_limit(e: Exception) -> bool:
    msg = str(e)
    return "429" in msg or "Too Many Requests" in msg or "rate_limit" in msg.lower()


def chat(client, model, prompt, timeout, retries, temperature=0.9):
    is_pool   = isinstance(client, ClientPool)
    max_tries = max(retries, client.size if is_pool else 1)
    last_err  = None
    for attempt in range(1, max_tries + 1):
        c = client.next() if is_pool else client
        try:
            r = c.chat.completions.create(
                model=model, temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
                timeout=timeout,
            )
            return (r.choices[0].message.content or "").strip()
        except Exception as e:
            last_err = e
            if attempt < max_tries:
                # Rate-limit: back off much longer
                if _is_rate_limit(e):
                    wait = min(15 * attempt, 90)
                    print(f"    [429] rate-limited, sleeping {wait}s ...", flush=True)
                    time.sleep(wait)
                else:
                    time.sleep(min(attempt, 3))
    raise last_err


def chat_json(client, model, prompt, timeout, retries, temperature=0.9):
    last_err = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            return parse_json_blob(chat(client, model, prompt, timeout, retries=1,
                                        temperature=temperature))
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(min(attempt, 3))
    raise last_err


def normalize_rows(X: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    norms = np.where(norms < 1e-10, 1.0, norms)
    return X / norms


# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────
def load_wine_data(config, max_sample=None, seed=42, indices=None):
    """Load wine embeddings + texts from parquet.

    If `indices` is provided it takes precedence over `max_sample`.
    Returns (embeddings np.float32, texts list[str], ids list[str]).
    """
    path     = Path(config["input_path"])
    emb_col  = config.get("embedding_column", "embedding")
    id_col   = config.get("id_column",        "row_id")
    text_col = config.get("text_column",      "text")

    print(f"[data] Reading {path} ...", flush=True)
    table = pq.read_table(path, columns=[id_col, emb_col, text_col])
    rows  = table.to_pylist()

    if indices is not None:
        rows = [rows[i] for i in indices]
    elif max_sample and len(rows) > max_sample:
        rng  = random.Random(seed)
        rows = rng.sample(rows, max_sample)
        print(f"  sampled {max_sample}/{table.num_rows}", flush=True)

    ids        = [str(r[id_col]) for r in rows]
    texts      = [str(r.get(text_col) or "") for r in rows]
    embeddings = np.array([r[emb_col] for r in rows], dtype=np.float32)
    print(f"  {len(ids)} wines, dim={embeddings.shape[1]}", flush=True)
    return embeddings, texts, ids


# ─────────────────────────────────────────────────────────────────────────────
# LLM Generation Strategies (Stage 1)
# ─────────────────────────────────────────────────────────────────────────────
_AXIS_SCHEMA = (
    '{"name": "<axis name>", '
    '"low_label": "<2-5 words>", '
    '"low_description": "<one sentence>", '
    '"high_label": "<2-5 words>", '
    '"high_description": "<one sentence>"}'
)


def _parse_axes(raw) -> list[dict]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for k in ("axes", "dimensions", "results", "data"):
            if isinstance(raw.get(k), list):
                return raw[k]
        return [raw]
    return []


def _ok(a: dict) -> bool:
    return all(str(a.get(k, "")).strip()
               for k in ("name", "low_label", "low_description", "high_label", "high_description"))


# ── Strategy A: four brainstorm frames ────────────────────────────────────────
_BRAINSTORM_FRAMES = [
    ("general",
     lambda dom, ctx, n: (
         f"You are designing a preference study about {dom}.\nCONTEXT: {ctx}\n\n"
         f"Brainstorm exactly {n} bipolar preference axes covering the full space of "
         "what people care about — obvious, subtle, emotional, functional, aesthetic.\n"
         f"Return a JSON array of exactly {n} objects, each: {_AXIS_SCHEMA}"
     )),
    ("sensory",
     lambda dom, ctx, n: (
         f"You are a flavour scientist analysing {dom}.\nCONTEXT: {ctx}\n\n"
         f"Propose exactly {n} bipolar SENSORY and PHYSICAL property axes for {dom}. "
         "Go deep: sub-dimensions of taste, texture, aroma, mouthfeel, finish.\n"
         f"Return a JSON array of exactly {n} objects, each: {_AXIS_SCHEMA}"
     )),
    ("production",
     lambda dom, ctx, n: (
         f"You are a {dom} production expert.\nCONTEXT: {ctx}\n\n"
         f"Propose exactly {n} bipolar axes for origin, winemaking style, vintage, "
         "and regional identity. Think agricultural, climatic, cultural, technical.\n"
         f"Return a JSON array of exactly {n} objects, each: {_AXIS_SCHEMA}"
     )),
    ("value_occasion",
     lambda dom, ctx, n: (
         f"You are a consumer insights researcher for {dom}.\nCONTEXT: {ctx}\n\n"
         f"Propose exactly {n} bipolar axes for value perception, price-quality signals, "
         "occasion suitability, social signaling, accessibility, aging potential.\n"
         f"Return a JSON array of exactly {n} objects, each: {_AXIS_SCHEMA}"
     )),
]


def strategy_brainstorm(config, client, model, timeout, retries, n_per_round=15):
    dom, ctx = config["domain"], config["choice_context"]
    result   = []
    for frame_id, prompt_fn in _BRAINSTORM_FRAMES:
        try:
            axes = _parse_axes(chat_json(client, model, prompt_fn(dom, ctx, n_per_round),
                                         timeout, retries, temperature=0.9))
            valid = [a for a in axes if _ok(a)]
            for a in valid:
                a["_strategy"] = f"brainstorm_{frame_id}"
            print(f"  [brainstorm/{frame_id}] {len(valid)}/{n_per_round}", flush=True)
            result.extend(valid)
        except Exception as e:
            print(f"  [brainstorm/{frame_id}] FAILED: {e}", flush=True)
    return result


# ── Strategy B: expert personas ───────────────────────────────────────────────
_PERSONAS = [
    ("master_sommelier",
     "You are a Master Sommelier with 20 years of blind-tasting experience for {dom}. "
     "What {n} dimensions most differentiate items in technical, sensory, quality evaluation?"),
    ("casual_consumer",
     "You are a casual {dom} drinker. "
     "What {n} simple, gut-feel dimensions most determine whether you enjoy one?"),
    ("food_pairing_chef",
     "You are a Michelin chef. What {n} {dom} property axes matter most for food pairing?"),
    ("wine_investor",
     "You are a fine {dom} collector. What {n} axes define long-term value and aging potential?"),
    ("health_wellness",
     "You are a nutritionist. What {n} bipolar axes capture health and production philosophy?"),
]


def strategy_personas(config, client, model, timeout, retries, n_per_persona=8):
    dom, ctx = config["domain"], config["choice_context"]
    result   = []
    for pid, tmpl in _PERSONAS:
        prompt = (
            tmpl.format(dom=dom, n=n_per_persona)
            + f"\nCONTEXT: {ctx}\n"
            + f"Return a JSON array of exactly {n_per_persona} objects, each: {_AXIS_SCHEMA}"
        )
        try:
            axes  = _parse_axes(chat_json(client, model, prompt, timeout, retries, temperature=0.85))
            valid = [a for a in axes if _ok(a)]
            for a in valid:
                a["_strategy"] = f"persona_{pid}"
            print(f"  [persona/{pid}] {len(valid)}/{n_per_persona}", flush=True)
            result.extend(valid)
        except Exception as e:
            print(f"  [persona/{pid}] FAILED: {e}", flush=True)
    return result


# ── Strategy C: PCA-guided naming ─────────────────────────────────────────────
def strategy_pca_naming(config, client, model, timeout, retries,
                        wine_embeddings, wine_texts, n_components=10, n_examples=6):
    """Compute top PCA directions of wine embeddings, show extremes, ask LLM to name them."""
    dom = config["domain"]
    X   = wine_embeddings.astype(np.float64) - wine_embeddings.mean(axis=0)

    n_svd = min(4000, len(X))
    idx   = np.random.choice(len(X), n_svd, replace=False) if len(X) > n_svd else np.arange(len(X))
    _, _, Vt = np.linalg.svd(X[idx], full_matrices=False)
    components = Vt[:n_components].astype(np.float32)

    X_norm    = normalize_rows(wine_embeddings)
    scores_M  = X_norm @ components.T   # (N, K)

    result = []
    for i in range(n_components):
        scores  = scores_M[:, i]
        top_idx = np.argsort(scores)[-n_examples:][::-1]
        bot_idx = np.argsort(scores)[:n_examples]
        prompt  = (
            f"Analysing {dom}. Two groups occupy OPPOSITE ENDS of a hidden dimension.\n\n"
            "GROUP A (high pole):\n"
            + "\n".join(f"  {j+1}. {wine_texts[k][:280]}" for j, k in enumerate(top_idx))
            + "\n\nGROUP B (low pole):\n"
            + "\n".join(f"  {j+1}. {wine_texts[k][:280]}" for j, k in enumerate(bot_idx))
            + "\n\nName the single bipolar axis distinguishing A (high) from B (low).\n"
            f"Return exactly 1 JSON object: {_AXIS_SCHEMA}\n"
            "Be precise. Avoid trivial names like 'quality'."
        )
        try:
            raw = chat_json(client, model, prompt, timeout, retries, temperature=0.7)
            if isinstance(raw, list) and raw:
                raw = raw[0]
            if _ok(raw):
                raw["_strategy"] = f"pca_component_{i + 1}"
                result.append(raw)
                print(f"  [pca/{i+1}] → {raw['name']}", flush=True)
        except Exception as e:
            print(f"  [pca/{i+1}] FAILED: {e}", flush=True)
    return result


# ── Strategy D: contrastive pairs ─────────────────────────────────────────────
def strategy_contrastive(config, client, model, timeout, retries,
                         wine_embeddings, wine_texts,
                         n_far=8, n_close=4, axes_per_pair=2):
    """Far pairs → obvious axes; close pairs → fine-grained subtle axes."""
    dom    = config["domain"]
    X_norm = normalize_rows(wine_embeddings)
    N      = len(X_norm)
    samp   = min(600, N)
    s_idx  = np.random.choice(N, samp, replace=False)
    sim    = X_norm[s_idx] @ X_norm[s_idx].T

    def _pairs(target, high_sim):
        mat = sim.copy()
        np.fill_diagonal(mat, 0 if not high_sim else -1)
        order = np.argsort(mat.ravel())
        if high_sim:
            order = order[::-1]
        pairs, seen = [], set()
        for flat in order:
            li, lj = divmod(int(flat), samp)
            if li == lj or (lj, li) in seen:
                continue
            seen.add((li, lj))
            pairs.append((s_idx[li], s_idx[lj]))
            if len(pairs) >= target:
                break
        return pairs

    result = []
    for (gi, gj), mode in (
        [(p, "far")   for p in _pairs(n_far,   False)]
        + [(p, "close") for p in _pairs(n_close, True)]
    ):
        ta, tb = wine_texts[gi][:350], wine_texts[gj][:350]
        if mode == "far":
            prompt = (
                f"Two very different {dom} items:\nA: {ta}\nB: {tb}\n\n"
                f"What {axes_per_pair} bipolar dimension(s) best capture their KEY DIFFERENCES?\n"
                f"Return a JSON array of {axes_per_pair} objects, each: {_AXIS_SCHEMA}"
            )
        else:
            prompt = (
                f"Two similar {dom} items:\nA: {ta}\nB: {tb}\n\n"
                f"Find {axes_per_pair} SUBTLE bipolar dimension(s) still distinguishing them.\n"
                f"Return a JSON array of {axes_per_pair} objects, each: {_AXIS_SCHEMA}"
            )
        try:
            axes  = _parse_axes(chat_json(client, model, prompt, timeout, retries, temperature=0.8))
            valid = [a for a in axes if _ok(a)]
            for a in valid:
                a["_strategy"] = f"contrastive_{mode}"
            result.extend(valid)
            print(f"  [contrastive/{mode}] {len(valid)} axes", flush=True)
        except Exception as e:
            print(f"  [contrastive/{mode}] FAILED: {e}", flush=True)
    return result


# ── Strategy E: anti-redundancy ───────────────────────────────────────────────
def strategy_anti_redundancy(config, client, model, timeout, retries,
                              existing: list[dict], n_new=20):
    dom, ctx   = config["domain"], config["choice_context"]
    name_list  = "\n".join(f"  - {a['name']}" for a in existing)
    prompt     = (
        f"Preference study for {dom}. Existing axes:\n{name_list}\n\n"
        f"CONTEXT: {ctx}\n\n"
        f"Generate exactly {n_new} NEW axes as ORTHOGONAL as possible to all above. "
        "Avoid every topic already listed. Think: unusual sensory properties, cultural "
        "context, philosophical distinctions, niche technical characteristics.\n"
        f"Return a JSON array of exactly {n_new} objects, each: {_AXIS_SCHEMA}"
    )
    try:
        axes  = _parse_axes(chat_json(client, model, prompt, timeout, retries, temperature=1.0))
        valid = [a for a in axes if _ok(a)]
        for a in valid:
            a["_strategy"] = "anti_redundancy"
        print(f"  [anti_redundancy] {len(valid)}/{n_new}", flush=True)
        return valid
    except Exception as e:
        print(f"  [anti_redundancy] FAILED: {e}", flush=True)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: generate
# ─────────────────────────────────────────────────────────────────────────────
def generate_candidates(config, client, model, output_dir, seed=42):
    out_path = output_dir / "candidate_axes.json"
    if out_path.exists():
        print(f"[generate] Resuming from {out_path}", flush=True)
        return load_json(out_path)

    timeout    = int(config.get("request_timeout_seconds", DEFAULT_TIMEOUT))
    retries    = int(config.get("max_retries", DEFAULT_RETRIES))
    max_sample = int(config.get("max_wines_sample", 3000))
    np.random.seed(seed); random.seed(seed)

    wine_embs, wine_texts, _ = load_wine_data(config, max_sample=max_sample, seed=seed)

    print("\n[generate] A: Brainstorm (4 frames × 15)", flush=True)
    axes_a = strategy_brainstorm(config, client, model, timeout, retries, n_per_round=15)

    print("\n[generate] B: Personas (5 × 8)", flush=True)
    axes_b = strategy_personas(config, client, model, timeout, retries, n_per_persona=8)

    print("\n[generate] C: PCA-guided naming (10 components)", flush=True)
    axes_c = strategy_pca_naming(config, client, model, timeout, retries,
                                  wine_embs, wine_texts, n_components=10, n_examples=6)

    print("\n[generate] D: Contrastive pairs (8 far + 4 close)", flush=True)
    axes_d = strategy_contrastive(config, client, model, timeout, retries,
                                   wine_embs, wine_texts, n_far=8, n_close=4, axes_per_pair=2)

    pool = axes_a + axes_b + axes_c + axes_d
    print(f"\n[generate] Pool A-D: {len(pool)}. Running anti-redundancy ...", flush=True)

    print("\n[generate] E: Anti-redundancy (20)", flush=True)
    axes_e = strategy_anti_redundancy(config, client, model, timeout, retries, pool, n_new=20)

    # Dedup by name
    seen, deduped = set(), []
    for a in axes_a + axes_b + axes_c + axes_d + axes_e:
        key = a["name"].lower().strip()
        if key not in seen:
            seen.add(key)
            deduped.append(a)
    for i, a in enumerate(deduped):
        a["id"] = i + 1

    result = {
        "domain":            config["domain"],
        "total_generated":   len(axes_a) + len(axes_b) + len(axes_c) + len(axes_d) + len(axes_e),
        "total_after_dedup": len(deduped),
        "strategy_counts":   {
            "brainstorm":      len(axes_a),
            "personas":        len(axes_b),
            "pca_naming":      len(axes_c),
            "contrastive":     len(axes_d),
            "anti_redundancy": len(axes_e),
        },
        "axes": deduped,
    }
    save_json(out_path, result)
    print(f"\n[generate] {len(deduped)} unique axes saved → {out_path}", flush=True)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: score-sample
# ─────────────────────────────────────────────────────────────────────────────
def _score_axis(axis: dict, wine_texts: list[str], client, model,
                timeout: int, retries: int,
                chunk_size: int = 25) -> np.ndarray | None:
    """
    Score all wines on one axis by sending them in chunks of chunk_size.
    Chunking keeps each call short and lets partial results survive rate-limit
    failures.  Returns a float array of shape (N,) or None if every chunk fails.
    """
    n      = len(wine_texts)
    result = np.full(n, np.nan, dtype=np.float32)
    any_ok = False

    chunks = range(0, n, chunk_size)
    for ci, start in enumerate(chunks):
        end   = min(start + chunk_size, n)
        batch = wine_texts[start:end]
        nb    = len(batch)
        wines = "\n".join(f"{start + i + 1}. {t[:300]}" for i, t in enumerate(batch))
        prompt = (
            f"Scoring wine descriptions for a preference study.\n\n"
            f"DIMENSION: {axis['name']}\n"
            f"LOW  ({axis['low_label']}): {axis['low_description']}\n"
            f"HIGH ({axis['high_label']}): {axis['high_description']}\n\n"
            f"Score wines {start+1}–{end} on a 1-5 scale "
            f"(1 = clearly LOW pole, 5 = clearly HIGH pole). Use the full range.\n\n"
            f"WINES:\n{wines}\n\n"
            f"Return ONLY a JSON array of exactly {nb} integers. No explanation.\n"
            f"Example for {nb} wines: {[3]*nb}"
        )
        ok = False
        for attempt in range(1, max(1, retries) + 1):
            try:
                raw = parse_json_blob(
                    chat(client, model, prompt, timeout, retries=1, temperature=0.0)
                )
                if isinstance(raw, dict):
                    for k in ("scores", "ratings", "values", "data"):
                        if isinstance(raw.get(k), list):
                            raw = raw[k]
                            break
                if not isinstance(raw, list):
                    raise ValueError(f"Expected list, got {type(raw)}")
                scores = [float(x) for x in raw[:nb]]
                if len(scores) < nb:
                    raise ValueError(f"Too few scores: {len(scores)} < {nb}")
                result[start:end] = scores
                any_ok = True
                ok = True
                time.sleep(1.5)   # brief pause between successful chunk calls
                break
            except Exception as e:
                if attempt < retries:
                    wait = 30 if _is_rate_limit(e) else min(attempt * 2, 6)
                    time.sleep(wait)
                else:
                    print(f"    chunk {ci} of '{axis['name']}' FAILED: {e}", flush=True)

        if not ok:
            # single chunk failure: leave those entries as NaN and continue
            pass

    return result if any_ok else None


def score_sample(config, client, model, output_dir, seed=42):
    """
    Sample N wines, score all of them on every candidate axis (1 LLM call per axis).
    Saves sample_scores.npz with:
        scores      (N_axes, N_sample)  — raw 1-5 scores
        wine_indices (N_sample,)        — row indices into full parquet
        axis_ids     (N_axes,)
        axis_names   (N_axes,)
    """
    out_path  = output_dir / "sample_scores.npz"
    info_path = output_dir / "sample_info.json"
    cands_path = output_dir / "candidate_axes.json"

    if not cands_path.exists():
        raise FileNotFoundError(f"Run 'generate' first — missing: {cands_path}")
    if out_path.exists():
        print(f"[score-sample] Resuming from {out_path}", flush=True)
        d = np.load(out_path, allow_pickle=True)
        return d["scores"], d["wine_indices"].tolist(), d["axis_ids"].tolist()

    n_sample   = int(config.get("n_score_sample", 100))
    timeout    = int(config.get("request_timeout_seconds", DEFAULT_TIMEOUT))
    retries    = int(config.get("max_retries", DEFAULT_RETRIES))
    max_workers = int(config.get("max_workers", 8))

    cands = load_json(cands_path)
    axes  = cands["axes"]

    # Sample N wine indices reproducibly
    rng = random.Random(seed)
    np.random.seed(seed)
    total_wines = pq.read_metadata(Path(config["input_path"])).num_rows
    wine_indices = sorted(rng.sample(range(total_wines), min(n_sample, total_wines)))

    _, wine_texts, _ = load_wine_data(config, indices=wine_indices)

    # Sequential scoring (1 worker) to stay within NIM rate limits.
    # Each axis fires 4 chunk calls with 1.5s pauses → ~8s per axis.
    # Use score_workers > 1 in config only if you have a high-rate API plan.
    score_workers = min(max_workers, int(config.get("score_workers", 1)))
    print(f"[score-sample] Scoring {len(wine_indices)} wines × {len(axes)} axes "
          f"({len(axes)} axes, score_workers={score_workers}) ...", flush=True)

    scores_matrix = np.full((len(axes), len(wine_indices)), np.nan, dtype=np.float32)
    failed        = []

    def do_axis(i):
        return _score_axis(axes[i], wine_texts, client, model, timeout, retries)

    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=score_workers) as ex:
        futs = {ex.submit(do_axis, i): i for i in range(len(axes))}
        for f in concurrent.futures.as_completed(futs):
            i  = futs[f]
            s  = f.result()
            done += 1
            if s is not None:
                scores_matrix[i] = s
            else:
                failed.append(axes[i]["name"])
            if done % 10 == 0 or done == len(axes):
                print(f"  [{done}/{len(axes)}] scored", flush=True)

    if failed:
        print(f"[score-sample] {len(failed)} axes failed scoring: {failed[:5]}", flush=True)

    axis_ids   = np.array([a["id"]   for a in axes])
    axis_names = np.array([a["name"] for a in axes], dtype=object)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(out_path,
             scores=scores_matrix,
             wine_indices=np.array(wine_indices),
             axis_ids=axis_ids,
             axis_names=axis_names)

    save_json(info_path, {
        "n_wines": len(wine_indices),
        "n_axes":  len(axes),
        "failed_axes": failed,
        "wine_indices": wine_indices,
    })
    print(f"[score-sample] Saved → {out_path}", flush=True)
    return scores_matrix, wine_indices, axis_ids.tolist()


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3: fit-directions
# ─────────────────────────────────────────────────────────────────────────────
def fit_directions(config, output_dir):
    """
    For each axis, run RidgeCV on (sample_embeddings, axis_scores) to find the
    best linear direction in wine embedding space.

    Saves axis_directions.npz:
        directions_raw   (N_axes, D)  — L2-normalized ridge coef per axis
        mean_embedding   (D,)         — mean of sample wines
        axis_ids         (N_axes,)
        axis_names       (N_axes,)
        r2_cv            (N_axes,)    — cross-validated R² (quality signal)
    """
    out_path     = output_dir / "axis_directions.npz"
    scores_path  = output_dir / "sample_scores.npz"
    cands_path   = output_dir / "candidate_axes.json"

    for p in [scores_path, cands_path]:
        if not p.exists():
            raise FileNotFoundError(f"Required: {p}")
    if out_path.exists():
        print(f"[fit-directions] Resuming from {out_path}", flush=True)
        d = np.load(out_path, allow_pickle=True)
        return d["directions_raw"], d["axis_ids"].tolist(), d["axis_names"].tolist()

    sc_data      = np.load(scores_path, allow_pickle=True)
    scores_M     = sc_data["scores"]        # (N_axes, N_sample)
    wine_indices = sc_data["wine_indices"].tolist()
    axis_ids     = sc_data["axis_ids"]
    axis_names   = sc_data["axis_names"]

    print("[fit-directions] Loading sample wine embeddings ...", flush=True)
    wine_embs, _, _ = load_wine_data(config, indices=wine_indices)
    wine_embs_f64   = wine_embs.astype(np.float64)

    mu         = wine_embs_f64.mean(axis=0)
    X_centered = wine_embs_f64 - mu

    n_axes      = scores_M.shape[0]
    D           = X_centered.shape[1]
    directions  = np.zeros((n_axes, D), dtype=np.float32)
    r2_cv       = np.full(n_axes, np.nan, dtype=np.float32)

    alphas = [0.01, 0.1, 1.0, 10.0, 100.0, 1000.0]

    print(f"[fit-directions] Fitting RidgeCV for {n_axes} axes ...", flush=True)
    ok = 0
    for i in range(n_axes):
        y = scores_M[i]
        if np.isnan(y).any():
            continue
        if np.std(y) < 1e-4:   # axis was scored identically for all wines
            continue
        try:
            model = RidgeCV(alphas=alphas, fit_intercept=True)
            model.fit(X_centered, y)
            coef = model.coef_.astype(np.float32)
            norm = np.linalg.norm(coef)
            if norm > 1e-10:
                directions[i] = coef / norm
            # Approximate CV R² from RidgeCV
            y_pred = model.predict(X_centered)
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - y.mean()) ** 2)
            r2_cv[i] = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0
            ok += 1
        except Exception as e:
            print(f"  [fit] axis {i} ({axis_names[i]}) FAILED: {e}", flush=True)

    print(f"[fit-directions] {ok}/{n_axes} axes fitted successfully.", flush=True)
    print(f"  R² range: {np.nanmin(r2_cv):.3f} – {np.nanmax(r2_cv):.3f}", flush=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(out_path,
             directions_raw=directions,
             mean_embedding=mu.astype(np.float32),
             axis_ids=axis_ids,
             axis_names=axis_names,
             r2_cv=r2_cv)
    print(f"[fit-directions] Saved → {out_path}", flush=True)
    return directions, axis_ids.tolist(), axis_names.tolist()


# ─────────────────────────────────────────────────────────────────────────────
# Stage 4: project
# ─────────────────────────────────────────────────────────────────────────────
def project_and_score(config, output_dir):
    """
    Project a large wine sample onto every axis direction.
    Records the full score matrix for the selection stage.

    Saves projection_scores.npz:
        scores      (N_wines, N_axes) — raw dot products (not normalized)
        variances   (N_axes,)
        axis_ids    (N_axes,)
    """
    out_path = output_dir / "projection_scores.npz"
    dir_path = output_dir / "axis_directions.npz"
    if not dir_path.exists():
        raise FileNotFoundError(f"Run 'fit-directions' first — missing: {dir_path}")
    if out_path.exists():
        print(f"[project] Resuming from {out_path}", flush=True)
        d = np.load(out_path, allow_pickle=True)
        return d["scores"], d["variances"], d["axis_ids"].tolist()

    dir_data   = np.load(dir_path, allow_pickle=True)
    directions = dir_data["directions_raw"].astype(np.float64)   # (N_axes, D)
    mu         = dir_data["mean_embedding"].astype(np.float64)    # (D,)
    axis_ids   = dir_data["axis_ids"].tolist()

    max_sample = int(config.get("max_wines_sample", 5000))
    wine_embs, _, _ = load_wine_data(config, max_sample=max_sample)
    X = wine_embs.astype(np.float64) - mu   # center by training mean

    print(f"[project] {X.shape[0]} wines × {len(directions)} directions ...", flush=True)
    scores    = X @ directions.T   # (N_wines, N_axes)
    variances = np.var(scores, axis=0)

    print(f"[project] Variance: min={variances.min():.5f}  "
          f"median={np.median(variances):.5f}  max={variances.max():.5f}", flush=True)

    np.savez(out_path, scores=scores.astype(np.float32),
             variances=variances.astype(np.float32),
             axis_ids=np.array(axis_ids))
    print(f"[project] Saved → {out_path}", flush=True)
    return scores, variances, axis_ids


# ─────────────────────────────────────────────────────────────────────────────
# Stage 5: select — greedy variance coverage
# ─────────────────────────────────────────────────────────────────────────────
def _greedy_coverage(S: np.ndarray, k: int, eligible: np.ndarray) -> list[int]:
    """
    Greedy maximization of variance coverage via Gram-Schmidt in score space.

    At each step: orthogonalise remaining score vectors against already-selected,
    pick the one with the highest residual variance. This greedily maximises
    sum of unique variances ≈ tr(V_sel C V_sel^T) / tr(C).

    Args:
        S:        (N_wines, N_axes)  projected score matrix
        k:        number to select
        eligible: 1-D array of column indices to consider

    Returns: list of selected column indices (into S / axis arrays)
    """
    # Work only with eligible columns
    Selig   = S[:, eligible].copy()  # (N, M)
    M       = Selig.shape[1]
    residuals = Selig.copy()         # will be orthogonalised in place

    selected_local  = []
    selected_global = []

    for step in range(min(k, M)):
        variances = np.var(residuals, axis=0)
        # Exclude already selected
        for li in selected_local:
            variances[li] = -1.0
        best_local  = int(np.argmax(variances))
        best_global = eligible[best_local]
        selected_local.append(best_local)
        selected_global.append(best_global)

        # Gram-Schmidt: remove the contribution of best_local from all others
        s_best = residuals[:, best_local].copy()
        s_best -= s_best.mean()
        norm2  = s_best @ s_best
        if norm2 < 1e-12:
            continue
        for j in range(M):
            if j == best_local:
                continue
            proj = (residuals[:, j] @ s_best) / norm2
            residuals[:, j] -= proj * s_best

    return selected_global


def select_diverse_axes(config, output_dir):
    """
    Greedily select K axes that maximise variance coverage using the
    projected score matrix from the project stage.

    Also saves selected_directions.npz in evaluate_basis.py format
    (directions_ortho + mean_embedding).
    """
    out_path = output_dir / "selected_axes.json"

    for p in ["axis_directions.npz", "projection_scores.npz", "candidate_axes.json"]:
        if not (output_dir / p).exists():
            raise FileNotFoundError(f"Required: {output_dir / p}")

    k                  = int(config.get("n_select", 10))
    variance_floor_pct = float(config.get("variance_floor_pct", 0.05))

    dir_data   = np.load(output_dir / "axis_directions.npz", allow_pickle=True)
    directions = dir_data["directions_raw"].astype(np.float64)   # (N, D)
    mu         = dir_data["mean_embedding"].astype(np.float64)
    axis_ids   = dir_data["axis_ids"].tolist()
    axis_names = dir_data["axis_names"].tolist()
    r2_cv      = dir_data["r2_cv"] if "r2_cv" in dir_data else np.zeros(len(axis_ids))

    sc_data    = np.load(output_dir / "projection_scores.npz", allow_pickle=True)
    scores     = sc_data["scores"].astype(np.float64)     # (N_wines, N_axes)
    variances  = sc_data["variances"].astype(np.float64)  # (N_axes,)

    cands_data = load_json(output_dir / "candidate_axes.json")
    axes_by_id = {a["id"]: a for a in cands_data["axes"]}

    # Filter: remove axes with zero direction (failed fit) or very low variance
    has_dir   = np.linalg.norm(directions, axis=1) > 1e-6
    var_floor = np.quantile(variances[has_dir], variance_floor_pct) if has_dir.any() else 0.0
    eligible  = np.where(has_dir & (variances >= var_floor))[0]
    print(f"[select] {len(eligible)}/{len(variances)} axes eligible "
          f"(has direction + var ≥ {var_floor:.5f})", flush=True)

    if len(eligible) < k:
        print(f"[select] WARNING: only {len(eligible)} eligible, requested {k}", flush=True)
        k = len(eligible)

    print(f"[select] Greedy variance-coverage selection (k={k}) ...", flush=True)
    selected_global = _greedy_coverage(scores, k, eligible)

    # Build output and report per-step variance
    total_var  = float(np.sum(variances[eligible]))
    sel_var    = 0.0
    selected_axes = []
    for rank, gi in enumerate(selected_global):
        sel_var += variances[gi]
        aid = axis_ids[gi]
        a   = axes_by_id.get(aid, {})
        print(f"  [{rank+1:2d}] {axis_names[gi]:<42} "
              f"var={variances[gi]:.5f}  r2={float(r2_cv[gi]):.3f}  "
              f"cumcov={sel_var/total_var:.3f}", flush=True)
        selected_axes.append({
            "rank":             rank + 1,
            "id":               aid,
            "name":             axis_names[gi],
            "variance":         float(variances[gi]),
            "r2_cv":            float(r2_cv[gi]),
            "low_label":        a.get("low_label", ""),
            "low_description":  a.get("low_description", ""),
            "high_label":       a.get("high_label", ""),
            "high_description": a.get("high_description", ""),
            "_strategy":        a.get("_strategy", ""),
        })

    # QR-orthogonalise selected directions for evaluate_basis.py compatibility
    sel_dir = directions[selected_global]            # (K, D)
    Q, _    = np.linalg.qr(sel_dir.T)               # QR of (D, K) → Q is (D, K)
    V_ortho = Q.T.astype(np.float32)                 # (K, D) orthonormal

    np.savez(output_dir / "selected_directions.npz",
             directions_ortho=V_ortho,
             directions_raw=sel_dir.astype(np.float32),
             mean_embedding=mu.astype(np.float32))

    result = {
        "domain":       config["domain"],
        "n_candidates": len(variances),
        "n_eligible":   int(len(eligible)),
        "n_selected":   len(selected_axes),
        "selected_axes": selected_axes,
    }
    save_json(out_path, result)
    print(f"\n[select] Saved → {out_path}", flush=True)
    print(f"         Orthonormal basis → {output_dir / 'selected_directions.npz'}", flush=True)
    return selected_axes


# ─────────────────────────────────────────────────────────────────────────────
# Stage 6: report
# ─────────────────────────────────────────────────────────────────────────────
def _pca_eigenvalues(X_centered: np.ndarray) -> np.ndarray:
    """Eigenvalues of C = 2 Sigma via the N×N Gram trick (cheap when D >> N)."""
    N = X_centered.shape[0]
    G = (X_centered @ X_centered.T) / N
    ev = np.linalg.eigvalsh(G)[::-1]
    return 2.0 * np.clip(ev, 0, None)


def build_report(config, output_dir):
    """
    Compute evaluate_basis.py metrics inline:
        coverage    = tr(V C V^T) / tr(C)
        independence_j  = 1 / ([C_proj^{-1}]_jj * C_proj_jj)
        r_j (cumulative variance ratio)
    Then compare selected vs naive (top-K by variance alone).
    """
    sel_dir_path = output_dir / "selected_directions.npz"
    sc_path      = output_dir / "projection_scores.npz"
    sel_path     = output_dir / "selected_axes.json"
    dir_path     = output_dir / "axis_directions.npz"
    cands_path   = output_dir / "candidate_axes.json"

    for p in [sel_dir_path, sc_path, sel_path, dir_path]:
        if not p.exists():
            raise FileNotFoundError(f"Required: {p}")

    selected   = load_json(sel_path)
    sel_axes   = selected["selected_axes"]
    K          = len(sel_axes)

    sel_data   = np.load(sel_dir_path, allow_pickle=True)
    V_ortho    = sel_data["directions_ortho"].astype(np.float64)   # (K, D)
    mu         = sel_data["mean_embedding"].astype(np.float64)

    sc_data    = np.load(sc_path, allow_pickle=True)
    all_scores = sc_data["scores"].astype(np.float64)    # (N_wines, N_axes)
    all_vars   = sc_data["variances"].astype(np.float64)

    dir_data   = np.load(dir_path, allow_pickle=True)
    axis_names = dir_data["axis_names"].tolist()
    axis_ids   = dir_data["axis_ids"].tolist()

    sel_ids    = [a["id"] - 1 for a in sel_axes]   # 0-indexed into axis arrays

    # ── Full wine embeddings for PCA eigenvalue computation ──────────────────
    max_sample = int(config.get("max_wines_sample", 5000))
    wine_embs, _, _ = load_wine_data(config, max_sample=max_sample)
    X_centered = wine_embs.astype(np.float64) - mu

    # Projected covariance C_proj = V C V^T  (via sample)
    # C_proj_jl = 2/N (X V_j)^T (X V_l)
    Z      = X_centered @ V_ortho.T   # (N, K)
    N      = X_centered.shape[0]
    C_proj = 2.0 * (Z.T @ Z) / N     # (K, K)

    # PCA eigenvalues
    print("[report] Computing PCA eigenvalues ...", flush=True)
    eigvals = _pca_eigenvalues(X_centered)
    total_var = eigvals.sum()

    # Coverage
    coverage     = float(np.trace(C_proj) / total_var) if total_var > 0 else 0.0
    pca_coverage = float(eigvals[:K].sum() / total_var) if total_var > 0 else 0.0

    # Per-dimension variance + independence
    var_j = np.diag(C_proj)
    var_sorted = np.sort(var_j)[::-1]
    r_j = np.clip(np.cumsum(var_sorted) / np.cumsum(eigvals[:K]), 0, 1)

    independence = np.zeros(K)
    try:
        C_inv = np.linalg.inv(C_proj)
        for j in range(K):
            d = C_inv[j, j] * C_proj[j, j]
            independence[j] = float(1.0 / d) if d > 0 else 0.0
    except np.linalg.LinAlgError:
        independence[:] = np.nan

    # ── Naive baseline (top-K by variance only) ───────────────────────────────
    dir_data2   = np.load(dir_path, allow_pickle=True)
    all_dirs    = dir_data2["directions_raw"].astype(np.float64)
    has_dir     = np.linalg.norm(all_dirs, axis=1) > 1e-6
    eligible    = np.where(has_dir)[0]
    naive_idx   = eligible[np.argsort(all_vars[eligible])[-K:][::-1]]
    V_naive     = all_dirs[naive_idx]
    Q_naive, _  = np.linalg.qr(V_naive.T)
    V_naive_ort = Q_naive.T.astype(np.float64)
    Z_naive     = X_centered @ V_naive_ort.T
    C_naive     = 2.0 * (Z_naive.T @ Z_naive) / N
    naive_cov   = float(np.trace(C_naive) / total_var) if total_var > 0 else 0.0

    # ── Markdown report ───────────────────────────────────────────────────────
    cands = load_json(cands_path)
    sc_breakdown = {}
    for a in cands["axes"]:
        s = a.get("_strategy", "unknown")
        sc_breakdown[s] = sc_breakdown.get(s, 0) + 1

    sel_sc_breakdown: dict[str, int] = {}
    for a in sel_axes:
        s = a.get("_strategy", "unknown")
        sel_sc_breakdown[s] = sel_sc_breakdown.get(s, 0) + 1

    lines = [
        f"# LLM-Guided Direction Report: {config['domain']}",
        "",
        "## Generation Summary",
        f"- Total candidates: {selected['n_candidates']}",
        f"- Eligible (direction + variance filter): {selected['n_eligible']}",
        f"- Selected: {K}",
        "",
        "### Strategy breakdown (candidates / selected)",
    ]
    for s in sorted(sc_breakdown.keys()):
        lines.append(f"- `{s}`: {sc_breakdown.get(s, 0)} / {sel_sc_breakdown.get(s, 0)}")

    lines += [
        "",
        "## Selected Axes",
    ]
    for a in sel_axes:
        lines += [
            f"\n### {a['rank']}. {a['name']}",
            f"- **Low**  ({a['low_label']}) — {a['low_description']}",
            f"- **High** ({a['high_label']}) — {a['high_description']}",
            f"- Variance: `{a['variance']:.5f}`  |  Ridge R²: `{a['r2_cv']:.3f}`"
            f"  |  Strategy: `{a['_strategy']}`",
        ]

    lines += [
        "",
        "## Coverage Metrics",
        "",
        "| Metric | Selected (greedy cov.) | Naive top-K by variance |",
        "|--------|----------------------|------------------------|",
        f"| Coverage tr(VCV^T)/tr(C) | **{coverage:.4f}** | {naive_cov:.4f} |",
        f"| PCA upper bound          | {pca_coverage:.4f}  | {pca_coverage:.4f} |",
        f"| Relative coverage        | **{coverage/pca_coverage:.4f}** | {naive_cov/pca_coverage:.4f} |"
        if pca_coverage > 0 else
        f"| Relative coverage        | N/A | N/A |",
        f"| Mean independence        | {np.nanmean(independence):.4f} | — |",
        f"| Final r_K                | {r_j[-1]:.4f} | — |",
        "",
        "## Per-Dimension Metrics",
        "",
        "| Rank | Name | Var(v_j^T δ) | Independence |",
        "|------|------|-------------|-------------|",
    ]
    order = np.argsort(var_j)[::-1]
    for rank, j in enumerate(order):
        lines.append(
            f"| {rank+1} | {sel_axes[j]['name'][:35]} "
            f"| {var_j[j]:.6f} | {independence[j]:.4f} |"
        )

    lines += [
        "",
        "## Projected Correlation Matrix",
        "```",
    ]
    diag = np.sqrt(np.diag(C_proj))
    diag = np.where(diag == 0, 1, diag)
    R_hat = C_proj / np.outer(diag, diag)
    hdrs  = [a["name"][:9] for a in sel_axes]
    lines.append("  " + "  ".join(f"{h:>9}" for h in hdrs))
    for i, a in enumerate(sel_axes):
        row = f"{a['name'][:9]:>9}  " + "  ".join(f"{R_hat[i,j]:+.3f}" for j in range(K))
        lines.append(row)
    lines += ["```", ""]

    report_text = "\n".join(lines)
    (output_dir / "report.md").write_text(report_text, "utf-8")

    # Also save in evaluate_basis.py compatible format
    pd_compat = {
        "var_j":         var_j.tolist(),
        "r_j":           r_j.tolist(),
        "independence":  independence.tolist(),
        "coverage":      coverage,
        "pca_coverage":  pca_coverage,
        "naive_coverage": naive_cov,
    }
    save_json(output_dir / "basis_metrics.json", pd_compat)

    rel_cov = f"{coverage/pca_coverage:.4f}" if pca_coverage > 0 else "N/A"
    print(f"\n{'='*60}", flush=True)
    print(f"  Coverage (greedy): {coverage:.4f}   naive: {naive_cov:.4f}   "
          f"PCA bound: {pca_coverage:.4f}", flush=True)
    print(f"  Relative coverage: {rel_cov}", flush=True)
    print(f"  Mean independence: {np.nanmean(independence):.4f}", flush=True)
    print(f"{'='*60}", flush=True)
    print(f"[report] → {output_dir / 'report.md'}", flush=True)
    print(f"[report] Orthonormal basis compatible with evaluate_basis.py: "
          f"{output_dir / 'selected_directions.npz'}", flush=True)
    return report_text


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
def main():
    args       = parse_args()
    config     = load_json(args.config)
    output_dir = Path(args.output_dir) if args.output_dir else (
        DEFAULT_OUTPUT_ROOT / config["domain"]
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    np.random.seed(args.seed)
    random.seed(args.seed)

    def get_client():
        return make_client_or_pool(
            getattr(args, "base_url",  None),
            getattr(args, "api_key",   None),
            getattr(args, "provider", "nvidia"),
        )

    cmd = args.command

    if cmd == "generate":
        generate_candidates(config, get_client(), args.model, output_dir, args.seed)
    elif cmd == "score-sample":
        score_sample(config, get_client(), args.model, output_dir, args.seed)
    elif cmd == "fit-directions":
        fit_directions(config, output_dir)
    elif cmd == "project":
        project_and_score(config, output_dir)
    elif cmd == "select":
        select_diverse_axes(config, output_dir)
    elif cmd == "report":
        build_report(config, output_dir)
    elif cmd == "run-all":
        client = get_client()
        model  = args.model
        sep    = "=" * 60

        print(f"\n{sep}\nSTAGE 1/6 · Generate candidates\n{sep}", flush=True)
        generate_candidates(config, client, model, output_dir, args.seed)

        print(f"\n{sep}\nSTAGE 2/6 · Score sample wines\n{sep}", flush=True)
        score_sample(config, client, model, output_dir, args.seed)

        print(f"\n{sep}\nSTAGE 3/6 · Fit ridge regression directions\n{sep}", flush=True)
        fit_directions(config, output_dir)

        print(f"\n{sep}\nSTAGE 4/6 · Project full dataset\n{sep}", flush=True)
        project_and_score(config, output_dir)

        print(f"\n{sep}\nSTAGE 5/6 · Greedy coverage selection\n{sep}", flush=True)
        select_diverse_axes(config, output_dir)

        print(f"\n{sep}\nSTAGE 6/6 · Coverage report\n{sep}", flush=True)
        build_report(config, output_dir)
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
