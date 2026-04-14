#!/usr/bin/env python3
import argparse
import concurrent.futures
import csv
import itertools
import json
import math
import os
import random
import re
import threading
import time
from collections import namedtuple
from dataclasses import dataclass
from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parent / "outputs"
DEFAULT_SEED = 7
DEFAULT_TIMEOUT = 45
DEFAULT_MAX_RETRIES = 3
EXCLUDED_FIELDS = {"embedding", "embeddings", "raw_row_json"}
_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
_RATE_LIMITER = None

Option = namedtuple("Option", ["option_id", "option_text", "display_text", "raw"])


def parse_args():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_sub(name):
        sub = subparsers.add_parser(name)
        sub.add_argument("--config", required=True)
        sub.add_argument("--api-provider", choices=["local", "openai", "anthropic", "nvidia"], default="local")
        sub.add_argument("--base-url", help="API endpoint URL(s), comma-separated for round-robin across multiple servers")
        sub.add_argument("--model")
        sub.add_argument("--api-key")
        sub.add_argument("--output-dir")
        sub.add_argument("--seed", type=int, default=DEFAULT_SEED)
        sub.add_argument("--rate-limit-per-minute", type=float, default=0.0)
        return sub

    for name in ["generate-dimensions", "score-options", "judge-pairs", "fit-bt", "consistency-check", "run-all"]:
        add_sub(name)
    for name in ["judge-pairs", "run-all"]:
        subparsers.choices[name].add_argument("--appearances-per-option", type=int)
    for name in ["fit-bt", "run-all"]:
        subparsers.choices[name].add_argument("--learning-rate", type=float, default=0.05)
        subparsers.choices[name].add_argument("--steps", type=int, default=1500)

    return parser.parse_args()


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")


def write_csv(path, rows):
    if not rows:
        raise ValueError(f"No rows to write for {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def read_csv_rows(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"Could not read headers from {path}")
        fieldnames = [
            (name or "").strip() or ("source_index" if i == 0 else f"column_{i}")
            for i, name in enumerate(reader.fieldnames)
        ]
        return [
            {fieldnames[i]: str(row.get(reader.fieldnames[i]) or "").strip() for i in range(len(fieldnames))}
            for row in reader
        ]


def read_parquet_rows(path):
    import pyarrow.parquet as pq
    return [
        {k: str(v).strip() for k, v in row.items() if not isinstance(v, list)}
        for row in pq.read_table(path).to_pylist()
    ]


def load_prompt_template(path):
    text = path.read_text(encoding="utf-8")
    match = re.search(r'"""\\?\n(.*)\n"""', text, flags=re.DOTALL)
    return match.group(1) if match else text


PROVIDER_DEFAULTS = {
    "openai": {"base_url": "https://api.openai.com/v1", "env_key": "OPENAI_API_KEY"},
    "anthropic": {"base_url": "https://api.anthropic.com/v1", "env_key": "ANTHROPIC_API_KEY"},
    "nvidia": {"base_url": "https://integrate.api.nvidia.com/v1", "env_key": "NVIDIA_API_KEY"},
}


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


def make_client(base_url, api_key, provider="local"):
    defaults = PROVIDER_DEFAULTS.get(provider, {})
    base_url = base_url or defaults.get("base_url")
    api_key = api_key or os.environ.get(defaults.get("env_key", ""), "")
    if not base_url:
        raise ValueError("Missing --base-url (required for provider='local')")
    if not api_key:
        env_hint = defaults.get("env_key", "")
        raise ValueError(
            f"Missing --api-key"
            + (f" (or set {env_hint})" if env_hint else "")
        )
    from openai import OpenAI
    return OpenAI(base_url=base_url, api_key=api_key)


class ClientPool:
    """Thread-safe round-robin pool over multiple OpenAI clients."""
    def __init__(self, clients):
        self._cycle = itertools.cycle(clients)
        self._lock = threading.Lock()
        self.size = len(clients)

    def next(self):
        with self._lock:
            return next(self._cycle)


def make_client_or_pool(base_url, api_key, provider="local"):
    """Create a single client or a round-robin pool from comma-separated URLs."""
    if base_url and "," in base_url:
        urls = [u.strip() for u in base_url.split(",") if u.strip()]
        clients = [make_client(url, api_key, provider) for url in urls]
        print(f"[client] Round-robin pool with {len(clients)} endpoints", flush=True)
        return ClientPool(clients)
    return make_client(base_url, api_key, provider)


def llm_call(client, model, prompt, timeout, retries, max_tokens=2048):
    if not model:
        raise ValueError("Missing --model")
    is_pool = isinstance(client, ClientPool)
    pool_size = client.size if is_pool else 1
    max_attempts = max(retries, pool_size)
    last_err = None
    for attempt in range(1, max_attempts + 1):
        resolved = client.next() if is_pool else client
        try:
            if _RATE_LIMITER is not None:
                _RATE_LIMITER.wait()
            resp = resolved.chat.completions.create(
                model=model, temperature=0,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
                timeout=timeout,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            last_err = e
            is_conn = "Connection" in type(e).__name__
            is_rate = "RateLimit" in type(e).__name__ or "429" in str(e)
            if attempt < max_attempts:
                if is_rate:
                    time.sleep(min(20 * attempt, 60))
                elif not is_conn:
                    time.sleep(min(attempt, 3))
    raise last_err


_VALID_JSON_ESCAPES = set('"\\/ bfnrtu')


def _fix_invalid_escapes(s):
    """Replace invalid JSON backslash escapes with a double backslash."""
    result = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            if s[i + 1] in _VALID_JSON_ESCAPES:
                result.append(s[i])
            else:
                result.append("\\\\")
            i += 1
        else:
            result.append(s[i])
        i += 1
    return "".join(result)


def parse_json_response(content):
    # strip reasoning blocks (e.g. Qwen)
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("{"), content.rfind("}")
        if start >= 0 and end > start:
            snippet = content[start:end + 1]
            try:
                return json.loads(snippet)
            except json.JSONDecodeError:
                return json.loads(_fix_invalid_escapes(snippet))
        raise


def llm_call_json(client, model, prompt, timeout, retries):
    last_err = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            return parse_json_response(llm_call(client, model, prompt, timeout, retries=retries))
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(min(attempt, 3))
    raise last_err


def run_jobs(jobs, fn, max_workers, tag):
    results = [None] * len(jobs)
    if max_workers <= 1:
        for i, job in enumerate(jobs):
            results[i] = fn(job)
            if (i + 1) % 100 == 0 or i + 1 == len(jobs):
                print(f"[{tag}] {i + 1}/{len(jobs)}", flush=True)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(fn, job): idx for idx, job in enumerate(jobs)}
            done = 0
            for future in concurrent.futures.as_completed(futures):
                results[futures[future]] = future.result()
                done += 1
                if done % 100 == 0 or done == len(jobs):
                    print(f"[{tag}] {done}/{len(jobs)}", flush=True)
    return results


def render_row_template(template, row):
    mapping = {k: v for k, v in row.items() if k.lower() not in EXCLUDED_FIELDS}
    lookup = {**mapping, **{k.lower(): v for k, v in mapping.items()}, **{k.upper(): v for k, v in mapping.items()}}
    rendered = re.sub(r"\{([^{}]+)\}", lambda m: lookup.get(m.group(1).strip(), ""), template)
    rendered = re.sub(r"[ \t]+", " ", rendered)
    return re.sub(r"\n\s*\n+", "\n", rendered).strip()


def build_option_text(row, template_text, text_column, display_column, id_column):
    if template_text:
        return render_row_template(template_text, row)
    if text_column and row.get(text_column):
        return row[text_column]
    skip = {id_column, display_column, text_column}
    parts = [
        f"{k.replace('_', ' ').strip()}: {v}."
        for k, v in row.items()
        if v and k.lower() not in EXCLUDED_FIELDS and k not in skip
    ]
    if display_column and row.get(display_column):
        return (f"Option: {row[display_column]}. " + " ".join(parts)) if parts else row[display_column]
    return " ".join(parts).strip()


def load_options(config):
    input_path = Path(config["input_path"])
    if not input_path.exists():
        raise FileNotFoundError(f"Input dataset not found: {input_path}")

    rows = read_parquet_rows(input_path) if input_path.suffix.lower() == ".parquet" else read_csv_rows(input_path)

    text_column = config.get("text_column")
    display_column = config.get("display_column", text_column)
    id_column = config.get("id_column")
    template_text = None

    if tp := config.get("template_path"):
        p = Path(tp)
        if not p.exists():
            raise FileNotFoundError(f"Template not found: {p}")
        template_text = p.read_text(encoding="utf-8").strip()

    options = []
    for idx, row in enumerate(rows):
        text = build_option_text(row, template_text, text_column, display_column, id_column)
        if not text:
            continue
        option_id = row.get(id_column, str(idx)) if id_column else str(idx)
        options.append(Option(
            option_id=str(option_id),
            option_text=text,
            display_text=row.get(display_column, text) if display_column else text,
            raw=row,
        ))

    if max_options := config.get("max_options"):
        options = options[:int(max_options)]
    if not options:
        raise ValueError("No options loaded from dataset.")
    return options


def load_dimensions(path):
    payload = load_json(path)
    dims = payload.get("dimensions")
    if not isinstance(dims, list):
        raise ValueError(f"Missing 'dimensions' list in {path}")
    return dims


def build_plain_dimension_prompt(domain, choice_context, n):
    return (
        "You are helping design a preference elicitation study.\n\n"
        f"DOMAIN: {domain}\nCHOICE CONTEXT: {choice_context}\n\n"
        f"Produce exactly {n} preference dimensions. Do NOT return JSON.\n"
        "Use this exact plain-text format for each dimension:\n\n"
        "===DIMENSION===\n"
        "name: <dimension name>\n"
        "low_label: <2-5 words>\nlow_description: <description>\nlow_typical_person: <who prefers low pole>\n"
        "high_label: <2-5 words>\nhigh_description: <description>\nhigh_typical_person: <who prefers high pole>\n"
        "low_example: <example low option>\nhigh_example: <example high option>\n"
        "scoring_guidance: <how to score from low to high>\n"
        "articulability: <explicit|partially_explicit|implicit>\n"
        "estimated_variance: <mostly_between_person|mostly_between_option|both>\n\n"
        f"Return exactly {n} blocks."
    )


def parse_plain_dimensions(content, domain, choice_context, n):
    blocks = [b.strip() for b in content.split("===DIMENSION===") if b.strip()]
    dimensions = []
    for i, block in enumerate(blocks[:n], start=1):
        kv = {k.strip().lower(): v.strip() for line in block.splitlines() if ":" in line for k, v in [line.split(":", 1)]}
        dimensions.append({
            "id": i,
            "name": kv.get("name", f"Dimension {i}"),
            "low_pole": {"label": kv.get("low_label", "Low"), "description": kv.get("low_description", ""), "typical_person": kv.get("low_typical_person", "")},
            "high_pole": {"label": kv.get("high_label", "High"), "description": kv.get("high_description", ""), "typical_person": kv.get("high_typical_person", "")},
            "example_contrast": {"low_option": kv.get("low_example", ""), "high_option": kv.get("high_example", "")},
            "articulability": kv.get("articulability", "partially_explicit"),
            "estimated_variance": kv.get("estimated_variance", "both"),
            "scoring_guidance": kv.get("scoring_guidance", ""),
        })
    if len(dimensions) < n:
        raise ValueError(f"Expected {n} dimensions, got {len(dimensions)}.")
    return {"domain": domain, "choice_context": choice_context, "reasoning": "", "dimensions": dimensions, "redundancy_check": []}


def generate_dimensions(config, client, model, output_dir):
    n = int(config.get("num_dimensions", 10))
    timeout = int(config.get("request_timeout_seconds", DEFAULT_TIMEOUT))
    retries = int(config.get("max_retries", DEFAULT_MAX_RETRIES))

    if str(config.get("dimensions_output_format", "json")).lower() == "plain":
        prompt = build_plain_dimension_prompt(str(config["domain"]), str(config["choice_context"]), n)
        content = llm_call(client, model, prompt, timeout, retries)
        result = parse_plain_dimensions(content, str(config["domain"]), str(config["choice_context"]), n)
    else:
        template = load_prompt_template(PROMPT_DIR / "llm_pref_gen.txt")
        prompt = (template
                  .replace("{domain}", str(config["domain"]))
                  .replace("{choice_context}", str(config["choice_context"]))
                  .replace("{N}", str(n)))
        result = llm_call_json(client, model, prompt, timeout, retries)

    path = output_dir / "dimensions.json"
    write_json(path, result)
    return path


def score_options(config, client, model, output_dir):
    options = load_options(config)
    dimensions = load_dimensions(output_dir / "dimensions.json")
    template = load_prompt_template(PROMPT_DIR / "llm_score_judge.txt")
    max_workers = int(config.get("max_workers", 1))
    timeout = int(config.get("request_timeout_seconds", DEFAULT_TIMEOUT))
    retries = int(config.get("max_retries", DEFAULT_MAX_RETRIES))

    csv_path = output_dir / "direct_scores.csv"
    existing_rows = []
    scored = set()
    if csv_path.exists():
        existing_rows = read_csv_rows(csv_path)
        scored = {(str(r["dimension_id"]), str(r["option_id"])) for r in existing_rows}
        print(f"[score-options] Loaded {len(existing_rows)} existing scores", flush=True)

    def run(job):
        dim, opt = job
        prompt = template.format(
            dimension_id=dim["id"], name=dim["name"],
            low_label=dim["low_pole"]["label"], low_description=dim["low_pole"]["description"],
            high_label=dim["high_pole"]["label"], high_description=dim["high_pole"]["description"],
            scoring_guidance=dim["scoring_guidance"],
            low_example=dim["example_contrast"]["low_option"], high_example=dim["example_contrast"]["high_option"],
            option_text=opt.option_text,
        )
        r = llm_call_json(client, model, prompt, timeout, retries)
        return {"dimension_id": dim["id"], "dimension_name": dim["name"], "option_id": opt.option_id,
                "display_text": opt.display_text, "score": r.get("score"),
                "zero_reason": r.get("zero_reason"), "justification": r.get("justification")}

    all_rows = list(existing_rows)
    for dim in dimensions:
        dim_id = str(dim["id"])
        jobs = [(dim, opt) for opt in options if (dim_id, str(opt.option_id)) not in scored]
        if not jobs:
            print(f"[score-options] Dim {dim_id} ({dim['name']}): already complete, skipping", flush=True)
            continue
        dim_rows = run_jobs(jobs, run, max_workers, f"score-options dim={dim_id}")
        all_rows.extend(dim_rows)
        scored.update((dim_id, str(r["option_id"])) for r in dim_rows)
        write_csv(csv_path, all_rows)
        print(f"[score-options] Dim {dim_id} ({dim['name']}): {len(dim_rows)} options scored -- saved", flush=True)

    return csv_path


def sample_pairs(option_ids, appearances_per_option, seed, exclude=None):
    rng = random.Random(seed)
    target = {oid: appearances_per_option for oid in option_ids}
    seen = set(exclude) if exclude else set()
    pairs = []
    safety = 0

    while any(c > 0 for c in target.values()):
        remaining = sorted(((k, v) for k, v in target.items() if v > 0), key=lambda x: (-x[1], x[0]))
        if len(remaining) < 2:
            break
        a = remaining[0][0]
        candidates = [oid for oid, _ in remaining[1:] if tuple(sorted((a, oid))) not in seen]
        if not candidates:
            safety += 1
            if safety > len(option_ids) * 3:
                break
            rng.shuffle(option_ids)
            continue
        b = rng.choice(candidates)
        pair = tuple(sorted((a, b)))
        seen.add(pair)
        pairs.append((a, b))
        target[a] -= 1
        target[b] -= 1
    return pairs


def judge_pairs(config, client, model, output_dir, appearances_per_option, seed):
    options = load_options(config)
    lookup = {opt.option_id: opt for opt in options}
    dimensions = load_dimensions(output_dir / "dimensions.json")
    template = load_prompt_template(PROMPT_DIR / "llm_binary_judge.txt")
    max_workers = int(config.get("max_workers", 1))
    timeout = int(config.get("request_timeout_seconds", DEFAULT_TIMEOUT))
    retries = int(config.get("max_retries", DEFAULT_MAX_RETRIES))
    pair_count = appearances_per_option or config.get("pair_appearances_per_option", 30)
    double_judge = bool(config.get("double_judge_pairs", True))

    csv_path = output_dir / "pairwise_judgments.csv"
    existing_rows = []
    existing_by_dim = {}
    if csv_path.exists():
        existing_rows = read_csv_rows(csv_path)
        for r in existing_rows:
            dim_id = str(r["dimension_id"])
            pair = tuple(sorted((r["option_a_id"], r["option_b_id"])))
            existing_by_dim.setdefault(dim_id, set()).add(pair)
        print(f"[judge-pairs] Loaded {len(existing_rows)} existing judgments from previous runs", flush=True)

    effective_seed = seed + len(existing_rows)
    option_ids = [opt.option_id for opt in options]

    jobs = []
    for dim in dimensions:
        dim_id = str(dim["id"])
        exclude = existing_by_dim.get(dim_id, set())
        new_pairs = sample_pairs(option_ids, int(pair_count), effective_seed + int(dim["id"]), exclude=exclude)
        jobs.extend((dim, a_id, b_id) for a_id, b_id in new_pairs)

    def _make_prompt(dim, opt_a, opt_b):
        return template.format(
            name=dim["name"],
            low_label=dim["low_pole"]["label"], low_description=dim["low_pole"]["description"],
            high_label=dim["high_pole"]["label"], high_description=dim["high_pole"]["description"],
            scoring_guidance=dim["scoring_guidance"],
            low_example=dim["example_contrast"]["low_option"], high_example=dim["example_contrast"]["high_option"],
            option_a=opt_a.option_text, option_b=opt_b.option_text,
        )

    def run(job):
        dim, a_id, b_id = job
        a, b = lookup[a_id], lookup[b_id]

        r_fwd = llm_call_json(client, model, _make_prompt(dim, a, b), timeout, retries)
        choice_fwd = r_fwd.get("choice")
        if double_judge:
            r_rev = llm_call_json(client, model, _make_prompt(dim, b, a), timeout, retries)
            choice_rev = r_rev.get("choice")

            # Both calls must point to the same real-world winner.
            # Forward "A" means real-a wins; reverse "B" also means real-a wins.
            if choice_fwd == "A" and choice_rev == "B":
                consistent, final_choice = True, "A"
            elif choice_fwd == "B" and choice_rev == "A":
                consistent, final_choice = True, "B"
            elif choice_fwd == "negligible" and choice_rev == "negligible":
                consistent, final_choice = True, "negligible"
            else:
                consistent, final_choice = False, choice_fwd
        else:
            consistent, final_choice = True, choice_fwd

        return {"dimension_id": dim["id"], "dimension_name": dim["name"],
                "option_a_id": a_id, "option_a_display": a.display_text,
                "option_b_id": b_id, "option_b_display": b.display_text,
                "choice": final_choice, "confidence": r_fwd.get("confidence"),
                "reasoning": r_fwd.get("reasoning"),
                "high_pole_description_a": r_fwd.get("high_pole_description_a"),
                "high_pole_description_b": r_fwd.get("high_pole_description_b"),
                "swap_consistent": str(consistent)}

    all_rows = list(existing_rows)
    run_new_total = 0
    for dim in dimensions:
        dim_id = str(dim["id"])
        exclude = existing_by_dim.get(dim_id, set())
        dim_pairs = sample_pairs(option_ids, int(pair_count), effective_seed + int(dim["id"]), exclude=exclude)
        if not dim_pairs:
            print(f"[judge-pairs] Dim {dim_id} ({dim['name']}): already complete, skipping", flush=True)
            continue
        dim_jobs = [(dim, a_id, b_id) for a_id, b_id in dim_pairs]
        dim_rows = []
        if max_workers <= 1:
            for idx, job in enumerate(dim_jobs, start=1):
                row = run(job)
                dim_rows.append(row)
                all_rows.append(row)
                write_csv(csv_path, all_rows)
                if idx % 5 == 0 or idx == len(dim_jobs):
                    n_consistent_so_far = sum(1 for r in dim_rows if r["swap_consistent"] == "True")
                    print(f"[judge-pairs] Dim {dim_id} ({dim['name']}): {idx}/{len(dim_jobs)} pairs "
                          f"({n_consistent_so_far} consistent) -- saved", flush=True)
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
                futures = [ex.submit(run, job) for job in dim_jobs]
                for idx, future in enumerate(concurrent.futures.as_completed(futures), start=1):
                    row = future.result()
                    dim_rows.append(row)
                    all_rows.append(row)
                    write_csv(csv_path, all_rows)
                    if idx % 5 == 0 or idx == len(dim_jobs):
                        n_consistent_so_far = sum(1 for r in dim_rows if r["swap_consistent"] == "True")
                        print(f"[judge-pairs] Dim {dim_id} ({dim['name']}): {idx}/{len(dim_jobs)} pairs "
                              f"({n_consistent_so_far} consistent) -- saved", flush=True)
        run_new_total += len(dim_rows)
        n_consistent = sum(1 for r in dim_rows if r["swap_consistent"] == "True")
        print(f"[judge-pairs] Dim {dim_id} ({dim['name']}): {len(dim_rows)} pairs "
              f"({n_consistent} consistent) -- saved", flush=True)

    if run_new_total == 0:
        print("[judge-pairs] No new pairs to judge (all slots filled by previous runs)", flush=True)
        return csv_path

    total_consistent = sum(1 for r in all_rows if r.get("swap_consistent", "True") == "True")
    print(f"[judge-pairs] This run: {run_new_total} new pairs", flush=True)
    print(f"[judge-pairs] Cumulative: {len(all_rows)} total pairs "
          f"({total_consistent} consistent, {100 * total_consistent / len(all_rows):.0f}%)", flush=True)
    return csv_path


def normalize_direct_score(raw):
    """Map a 0-5 integer score to the [-1, 1] range used by BT scores."""
    return (float(raw) - 2.5) / 2.5


def sigmoid(x):
    z = math.exp(-abs(x))
    return (1.0 / (1.0 + z)) if x >= 0 else (z / (1.0 + z))


def fit_bradley_terry(option_ids, comparisons, lr, steps):
    scores = {oid: 0.0 for oid in option_ids}
    for _ in range(steps):
        grads = {oid: 0.0 for oid in option_ids}
        for row in comparisons:
            a, b = row["option_a_id"], row["option_b_id"]
            target = {"A": 1.0, "B": 0.0}.get(row["choice"], 0.5)
            delta = target - sigmoid(scores[a] - scores[b])
            grads[a] += delta
            grads[b] -= delta
        for oid in option_ids:
            scores[oid] += lr * grads[oid]
        mean = sum(scores.values()) / len(scores)
        for oid in option_ids:
            scores[oid] -= mean
    max_abs = max((abs(s) for s in scores.values()), default=1.0) or 1.0
    return {oid: s / max_abs for oid, s in scores.items()}


def fit_bt(config, output_dir, lr, steps):
    options = load_options(config)
    lookup = {opt.option_id: opt for opt in options}
    all_comparisons = read_csv_rows(output_dir / "pairwise_judgments.csv")
    comparisons = [r for r in all_comparisons if r.get("swap_consistent", "True") == "True"]
    dimensions = load_dimensions(output_dir / "dimensions.json")

    rows = []
    for dim in dimensions:
        dim_rows = [r for r in comparisons if str(r["dimension_id"]) == str(dim["id"])]
        scores = fit_bradley_terry([opt.option_id for opt in options], dim_rows, lr, steps)
        rows.extend(
            {"dimension_id": dim["id"], "dimension_name": dim["name"],
             "option_id": oid, "display_text": lookup[oid].display_text, "bt_score": round(score, 6)}
            for oid, score in scores.items()
        )

    path = output_dir / "bt_scores.csv"
    write_csv(path, rows)
    return path


def _rank(values):
    """Assign average ranks to a list of numeric values (handles ties)."""
    indexed = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while j < len(indexed) and values[indexed[j]] == values[indexed[i]]:
            j += 1
        avg_rank = (i + j - 1) / 2.0 + 1.0
        for k in range(i, j):
            ranks[indexed[k]] = avg_rank
        i = j
    return ranks


def spearman_rho(xs, ys):
    if len(xs) < 2:
        return float("nan")
    rx, ry = _rank(xs), _rank(ys)
    n = len(xs)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    dy = math.sqrt(sum((b - my) ** 2 for b in ry))
    return num / (dx * dy) if dx and dy else float("nan")


def kendall_tau_b(xs, ys):
    n = len(xs)
    if n < 2:
        return float("nan")
    concordant = discordant = ties_x = ties_y = ties_xy = 0
    for i in range(n):
        for j in range(i + 1, n):
            dx = xs[i] - xs[j]
            dy = ys[i] - ys[j]
            if dx == 0 and dy == 0:
                ties_xy += 1
            elif dx == 0:
                ties_x += 1
            elif dy == 0:
                ties_y += 1
            elif (dx > 0) == (dy > 0):
                concordant += 1
            else:
                discordant += 1
    n0 = n * (n - 1) / 2
    n1 = ties_x + ties_xy
    n2 = ties_y + ties_xy
    denom = math.sqrt((n0 - n1) * (n0 - n2))
    return (concordant - discordant) / denom if denom else float("nan")


def top_bottom(rows, score_key, limit=5):
    valid = sorted((r for r in rows if r.get(score_key) not in ("", None)), key=lambda r: float(r[score_key]))
    return valid[:limit], list(reversed(valid[-limit:]))


def _compute_dim_correlation(dim_direct, dim_bt):
    """Join direct and BT scores on option_id and return (rho, tau, n)."""
    bt_by_id = {r["option_id"]: float(r["bt_score"]) for r in dim_bt if r.get("bt_score") not in ("", None)}
    pairs = []
    for r in dim_direct:
        oid = r["option_id"]
        if oid in bt_by_id and r.get("score") not in ("", None):
            pairs.append((normalize_direct_score(r["score"]), bt_by_id[oid]))
    if len(pairs) < 3:
        return float("nan"), float("nan"), len(pairs)
    xs, ys = zip(*pairs)
    return spearman_rho(list(xs), list(ys)), kendall_tau_b(list(xs), list(ys)), len(pairs)


def build_summary(config, output_dir):
    dimensions = load_dimensions(output_dir / "dimensions.json")
    direct_scores = read_csv_rows(output_dir / "direct_scores.csv")
    bt_scores = read_csv_rows(output_dir / "bt_scores.csv")
    pairwise = read_csv_rows(output_dir / "pairwise_judgments.csv")

    lines = [f"# {config['domain'].title()} Summary", "", f"Choice context: {config['choice_context']}", ""]

    # Global cross-variant consistency table
    consistency_rows = []
    for dim in dimensions:
        dim_id = str(dim["id"])
        dim_direct = [r for r in direct_scores if str(r["dimension_id"]) == dim_id]
        dim_bt = [r for r in bt_scores if str(r["dimension_id"]) == dim_id]
        rho, tau, n = _compute_dim_correlation(dim_direct, dim_bt)
        flag = " **UNRELIABLE**" if (not math.isnan(tau) and tau < 0.3) else ""
        consistency_rows.append((dim["id"], dim["name"], rho, tau, n, flag))

    lines += ["## Cross-Variant Consistency (Direct Score vs Bradley-Terry)", ""]
    lines += ["| Dim | Name | Spearman rho | Kendall tau | N | Flag |"]
    lines += ["| --- | ---- | -----------: | ----------: | -: | ---- |"]
    for did, dname, rho, tau, n, flag in consistency_rows:
        rho_s = f"{rho:.3f}" if not math.isnan(rho) else "n/a"
        tau_s = f"{tau:.3f}" if not math.isnan(tau) else "n/a"
        lines.append(f"| {did} | {dname} | {rho_s} | {tau_s} | {n} |{flag} |")
    lines.append("")

    for dim in dimensions:
        dim_id = str(dim["id"])
        lines += [
            f"## Dimension {dim['id']}: {dim['name']}", "",
            f"Low pole: {dim['low_pole']['label']} | High pole: {dim['high_pole']['label']}", "",
        ]
        dim_direct = [r for r in direct_scores if str(r["dimension_id"]) == dim_id]
        dim_bt = [r for r in bt_scores if str(r["dimension_id"]) == dim_id]
        dim_pairwise = [r for r in pairwise if str(r["dimension_id"]) == dim_id][:3]

        low_d, high_d = top_bottom(dim_direct, "score")
        low_bt, high_bt = top_bottom(dim_bt, "bt_score")

        lines += ["Direct-score low examples:"]
        lines += [f"- {r['display_text']} ({r['score']}): {r['justification']}" for r in low_d]
        lines += ["", "Direct-score high examples:"]
        lines += [f"- {r['display_text']} ({r['score']}): {r['justification']}" for r in high_d]
        lines += ["", "Bradley-Terry low examples:"]
        lines += [f"- {r['display_text']} ({r['bt_score']})" for r in low_bt]
        lines += ["", "Bradley-Terry high examples:"]
        lines += [f"- {r['display_text']} ({r['bt_score']})" for r in high_bt]
        lines += ["", "Pairwise spot checks:"]
        lines += [f"- {r['option_a_display']} vs {r['option_b_display']} -> {r['choice']} ({r['confidence']}): {r['reasoning']}" for r in dim_pairwise]

        rho, tau, n = _compute_dim_correlation(dim_direct, dim_bt)
        lines += ["", "Cross-variant consistency:"]
        if math.isnan(tau):
            lines.append("- Insufficient data for correlation.")
        else:
            lines.append(f"- Spearman rho = {rho:.3f}, Kendall tau = {tau:.3f} (n={n})")
            if tau < 0.3:
                lines.append(f"- WARNING: Low cross-variant agreement (tau = {tau:.2f}) -- this dimension may be unreliable.")
        lines.append("")

    path = output_dir / "summary.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def run_all(args, config, output_dir):
    client = make_client_or_pool(args.base_url, args.api_key, args.api_provider)
    generate_dimensions(config, client, args.model, output_dir)
    score_options(config, client, args.model, output_dir)
    judge_pairs(config, client, args.model, output_dir, args.appearances_per_option, args.seed)
    fit_bt(config, output_dir, lr=args.learning_rate, steps=args.steps)
    build_summary(config, output_dir)


def main():
    global _RATE_LIMITER
    load_dotenv()
    args = parse_args()
    _RATE_LIMITER = RateLimiter(args.rate_limit_per_minute) if args.rate_limit_per_minute and args.rate_limit_per_minute > 0 else None
    config = load_json(Path(args.config))
    output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_ROOT / config["domain"]

    client_fn = lambda: make_client_or_pool(args.base_url, args.api_key, args.api_provider)

    if args.command == "generate-dimensions":
        generate_dimensions(config, client_fn(), args.model, output_dir)
    elif args.command == "score-options":
        score_options(config, client_fn(), args.model, output_dir)
    elif args.command == "judge-pairs":
        judge_pairs(config, client_fn(), args.model, output_dir, args.appearances_per_option, args.seed)
    elif args.command == "fit-bt":
        fit_bt(config, output_dir, args.learning_rate, args.steps)
        build_summary(config, output_dir)
    elif args.command == "consistency-check":
        build_summary(config, output_dir)
    elif args.command == "run-all":
        run_all(args, config, output_dir)


if __name__ == "__main__":
    main()
