#!/usr/bin/env python3
import argparse
import json
import time
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-json", required=True)
    parser.add_argument("--output-json")
    parser.add_argument("--output-md")
    parser.add_argument("--component-start", type=int, default=1)
    parser.add_argument("--component-end", type=int, default=50)
    parser.add_argument("--base-url", default="http://localhost:8000/v1")
    parser.add_argument("--model", required=True)
    parser.add_argument("--api-key", default="dummy")
    parser.add_argument("--llm-top-k", type=int, default=3)
    parser.add_argument("--llm-max-text-chars", type=int, default=160)
    parser.add_argument("--max-retries", type=int, default=4)
    parser.add_argument("--retry-delay-seconds", type=float, default=3.0)
    return parser.parse_args()


def compact_text(text, max_chars):
    marker = "Tasting note:"
    if marker in text:
        text = text.split(marker, 1)[1].strip()
    text = " ".join(text.split())
    return text if len(text) <= max_chars else text[:max_chars - 3].rstrip() + "..."


def build_prompt(component_index, explained_ratio, pos_examples, neg_examples, prior_context, llm_top_k, llm_max_chars):
    def fmt_examples(title, items):
        lines = [title]
        for item in items[:llm_top_k]:
            label = item.get("label") or item.get("group") or f"row {item['row_index']}"
            lines.append(f"- {label} | score={item['score']:.4f} | note={compact_text(item['text'], llm_max_chars)}")
        return "\n".join(lines)

    return (
        "You are analyzing PCA directions over wine-review embeddings.\n"
        f"Component: PC{component_index}\n"
        f"Explained variance ratio: {explained_ratio:.6f}\n\n"
        f"{prior_context}\n\n"
        "Infer the most likely wine-description contrast captured by this direction. "
        "Use concise, domain-specific language. If the direction seems mixed, say so. "
        "Prefer a new axis that is not just a restatement of the already-labeled earlier PCs.\n\n"
        f"{fmt_examples('Positive examples', pos_examples)}\n\n"
        f"{fmt_examples('Negative examples', neg_examples)}\n\n"
        "Return 3 short sections:\n"
        "1. Axis label: a concise name.\n"
        "2. Positive pole: 2-4 sentences.\n"
        "3. Negative pole: 2-4 sentences.\n"
    )


def extract_axis_label(explanation):
    for line in explanation.splitlines():
        if "axis label:" in line.strip().lower():
            return line.strip().split(":", 1)[1].strip()
    return ""


def build_prior_context(prior_rows):
    if not prior_rows:
        return "Earlier PCs already explained: none."
    lines = ["Earlier PCs already explained. Avoid reusing these same top-level contrasts unless the current examples clearly require it:"]
    for row in prior_rows:
        label = extract_axis_label(row.get("llm_explanation", "")) or "unlabeled"
        lines.append(f"- PC{int(row['component_index'])}: {label}")
    return "\n".join(lines)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def write_markdown(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# PCA Component Labels", ""]
    for row in rows:
        lines += [f"## PC{row['component_index']}", "", f"- Explained variance: `{row['explained_variance_ratio']:.4%}`", ""]
        lines.append(row["llm_explanation"] or "No explanation.")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main():
    args = parse_args()
    report_path = Path(args.report_json)
    report = json.loads(report_path.read_text(encoding="utf-8"))

    from openai import OpenAI
    client = OpenAI(base_url=args.base_url, api_key=args.api_key)

    start_idx = max(args.component_start, 1) - 1
    end_idx = max(args.component_end, args.component_start)
    report_is_dict = isinstance(report, dict)
    component_rows = report["component_summaries"] if report_is_dict else report
    selected = component_rows[start_idx:end_idx]

    output_json = Path(args.output_json) if args.output_json else report_path.parent / f"pc{args.component_start}_{args.component_end}_labels.json"
    output_md = Path(args.output_md) if args.output_md else report_path.parent / f"pc{args.component_start}_{args.component_end}_labels.md"

    labeled_rows = []
    completed = {}
    if output_json.exists():
        existing = json.loads(output_json.read_text(encoding="utf-8"))
        labeled_rows = list(existing)
        for row in existing:
            completed[int(row["component_index"])] = row

    for component in selected:
        raw_idx = int(component["component_index"])
        component_index = (raw_idx + 1) if report_is_dict else raw_idx
        if component_index in completed:
            print(f"Skipping PC{component_index}; already labeled", flush=True)
            continue

        explained_ratio = float(component.get("explained_variance_ratio", component.get("explained_variance_ratio_within_subset", 0.0)))
        cumulative_ratio = float(component.get("cumulative_explained_variance_ratio", 0.0))
        prior_rows = [r for r in sorted(labeled_rows, key=lambda r: int(r["component_index"])) if int(r["component_index"]) < component_index]
        prompt = build_prompt(
            component_index, explained_ratio,
            component["positive_examples"], component["negative_examples"],
            build_prior_context(prior_rows), args.llm_top_k, args.llm_max_text_chars,
        )

        response = None
        for attempt in range(1, args.max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model=args.model, temperature=0,
                    messages=[{"role": "user", "content": prompt}],
                    timeout=90,
                )
                break
            except Exception as exc:
                if attempt == args.max_retries:
                    raise
                print(f"PC{component_index} failed on attempt {attempt}: {type(exc).__name__}: {exc}", flush=True)
                time.sleep(args.retry_delay_seconds)

        explanation = (response.choices[0].message.content or "").strip()
        labeled_rows.append({
            "component_index": component_index,
            "explained_variance_ratio": explained_ratio,
            "cumulative_explained_variance_ratio": cumulative_ratio,
            "positive_examples": component["positive_examples"],
            "negative_examples": component["negative_examples"],
            "llm_prompt": prompt,
            "llm_explanation": explanation,
        })
        labeled_rows.sort(key=lambda r: int(r["component_index"]))
        write_json(output_json, labeled_rows)
        write_markdown(output_md, labeled_rows)
        print(f"Labeled PC{component_index}", flush=True)

    write_json(output_json, labeled_rows)
    write_markdown(output_md, labeled_rows)
    print(json.dumps({"output_json": str(output_json), "output_md": str(output_md), "labeled_components": len(labeled_rows)}, indent=2))


if __name__ == "__main__":
    main()
