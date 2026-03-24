#!/usr/bin/env python3
import argparse
import concurrent.futures
import csv
import json
import math
import random
import re
import time
from collections import namedtuple
from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parent / "outputs"
DEFAULT_SEED = 7
DEFAULT_TIMEOUT = 45
DEFAULT_MAX_RETRIES = 3
EXCLUDED_FIELDS = {"embedding", "embeddings", "raw_row_json"}

Option = namedtuple("Option", ["option_id", "option_text", "display_text", "raw"])


def parse_args():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_sub(name):
        sub = subparsers.add_parser(name)
        sub.add_argument("--config", required=True)
        sub.add_argument("--base-url")
        sub.add_argument("--model")
        sub.add_argument("--api-key")
        sub.add_argument("--output-dir")
        sub.add_argument("--seed", type=int, default=DEFAULT_SEED)
        return sub

    for name in ["generate-dimensions", "score-options", "judge-pairs", "fit-bt", "run-all"]:
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


def make_client(base_url, api_key):
    if not base_url:
        raise ValueError("Missing --base-url")
    if not api_key:
        raise ValueError("Missing --api-key")
    from openai import OpenAI
    return OpenAI(base_url=base_url, api_key=api_key)


def llm_call(client, model, prompt, timeout, retries):
    if not model:
        raise ValueError("Missing --model")
    last_err = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            resp = client.chat.completions.create(
                model=model, temperature=0,
                messages=[{"role": "user", "content": prompt}],
                timeout=timeout,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(min(attempt, 3))
    raise last_err


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
            return json.loads(content[start:end + 1])
        raise


def llm_call_json(client, model, prompt, timeout, retries):
    last_err = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            return parse_json_response(llm_call(client, model, prompt, timeout, retries=1))
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

    jobs = [(dim, opt) for dim in dimensions for opt in options]

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

    rows = run_jobs(jobs, run, max_workers, "score-options")
    path = output_dir / "direct_scores.csv"
    write_csv(path, rows)
    return path


def sample_pairs(option_ids, appearances_per_option, seed):
    rng = random.Random(seed)
    target = {oid: appearances_per_option for oid in option_ids}
    seen = set()
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
    pair_count = appearances_per_option or config.get("pair_appearances_per_option", 20)

    jobs = [
        (dim, a_id, b_id)
        for dim in dimensions
        for a_id, b_id in sample_pairs([opt.option_id for opt in options], int(pair_count), seed + int(dim["id"]))
    ]

    def run(job):
        dim, a_id, b_id = job
        a, b = lookup[a_id], lookup[b_id]
        prompt = template.format(
            name=dim["name"],
            low_label=dim["low_pole"]["label"], low_description=dim["low_pole"]["description"],
            high_label=dim["high_pole"]["label"], high_description=dim["high_pole"]["description"],
            scoring_guidance=dim["scoring_guidance"],
            low_example=dim["example_contrast"]["low_option"], high_example=dim["example_contrast"]["high_option"],
            option_a=a.option_text, option_b=b.option_text,
        )
        r = llm_call_json(client, model, prompt, timeout, retries)
        return {"dimension_id": dim["id"], "dimension_name": dim["name"],
                "option_a_id": a_id, "option_a_display": a.display_text,
                "option_b_id": b_id, "option_b_display": b.display_text,
                "choice": r.get("choice"), "confidence": r.get("confidence"),
                "reasoning": r.get("reasoning"),
                "high_pole_description_a": r.get("high_pole_description_a"),
                "high_pole_description_b": r.get("high_pole_description_b")}

    rows = run_jobs(jobs, run, max_workers, "judge-pairs")
    path = output_dir / "pairwise_judgments.csv"
    write_csv(path, rows)
    return path


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
    comparisons = read_csv_rows(output_dir / "pairwise_judgments.csv")
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


def top_bottom(rows, score_key, limit=5):
    valid = sorted((r for r in rows if r.get(score_key) not in ("", None)), key=lambda r: float(r[score_key]))
    return valid[:limit], list(reversed(valid[-limit:]))


def build_summary(config, output_dir):
    dimensions = load_dimensions(output_dir / "dimensions.json")
    direct_scores = read_csv_rows(output_dir / "direct_scores.csv")
    bt_scores = read_csv_rows(output_dir / "bt_scores.csv")
    pairwise = read_csv_rows(output_dir / "pairwise_judgments.csv")

    lines = [f"# {config['domain'].title()} Summary", "", f"Choice context: {config['choice_context']}", ""]

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
        lines.append("")

    path = output_dir / "summary.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def run_all(args, config, output_dir):
    client = make_client(args.base_url, args.api_key)
    generate_dimensions(config, client, args.model, output_dir)
    score_options(config, client, args.model, output_dir)
    judge_pairs(config, client, args.model, output_dir, args.appearances_per_option, args.seed)
    fit_bt(config, output_dir, lr=args.learning_rate, steps=args.steps)
    build_summary(config, output_dir)


def main():
    args = parse_args()
    config = load_json(Path(args.config))
    output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_ROOT / config["domain"]

    if args.command == "generate-dimensions":
        generate_dimensions(config, make_client(args.base_url, args.api_key), args.model, output_dir)
    elif args.command == "score-options":
        score_options(config, make_client(args.base_url, args.api_key), args.model, output_dir)
    elif args.command == "judge-pairs":
        judge_pairs(config, make_client(args.base_url, args.api_key), args.model, output_dir, args.appearances_per_option, args.seed)
    elif args.command == "fit-bt":
        fit_bt(config, output_dir, args.learning_rate, args.steps)
        build_summary(config, output_dir)
    elif args.command == "run-all":
        run_all(args, config, output_dir)


if __name__ == "__main__":
    main()
