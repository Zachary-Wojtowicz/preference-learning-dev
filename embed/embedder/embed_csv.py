#!/usr/bin/env python3
"""Embed CSV rows with an OpenAI-compatible embeddings endpoint."""

from __future__ import annotations

import argparse
import csv
import getpass
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

DESCRIPTION_KEYS = {"description", "desc", "prompt", "summary", "details"}
EXCLUDED_OUTPUT_FIELDS = {"embedding", "embeddings"}


def prompt_if_missing(value: str | None, prompt: str, *, secret: bool = False) -> str:
    if value:
        return value
    if secret:
        return getpass.getpass(f"{prompt}: ").strip()
    return input(f"{prompt}: ").strip()


def detect_header(path: Path, encoding: str) -> bool:
    sample = path.read_text(encoding=encoding)[:4096]
    if not sample.strip():
        raise ValueError(f"{path} is empty.")
    # csv.Sniffer.has_header is unreliable on all-string CSVs (it returns
    # False when the header row looks like the data rows), which silently
    # corrupts the output schema. Default to True; only return False when
    # the first row is unambiguously data (every cell is numeric).
    first_line = sample.splitlines()[0]
    try:
        cells = next(csv.reader([first_line]))
    except (csv.Error, StopIteration):
        return True
    if cells and all(_looks_numeric(c) for c in cells):
        return False
    return True


def _looks_numeric(cell: str) -> bool:
    cell = cell.strip()
    if not cell:
        return False
    try:
        float(cell)
        return True
    except ValueError:
        return False


def normalize_value(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def normalize_fieldnames(fieldnames: Sequence[str | None]) -> List[str]:
    normalized = []
    for index, name in enumerate(fieldnames):
        candidate = (name or "").strip()
        normalized.append(
            candidate or ("source_index" if index == 0 else f"column_{index}")
        )
    return normalized


def read_csv_rows(path: Path, encoding: str) -> Tuple[List[str], List[Dict[str, str]]]:
    has_header = detect_header(path, encoding)
    with path.open("r", encoding=encoding, newline="") as handle:
        if has_header:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise ValueError(f"Could not read headers from {path}.")
            fieldnames = normalize_fieldnames(reader.fieldnames)
            rows = []
            for row in reader:
                rows.append(
                    {
                        fieldnames[i]: normalize_value(
                            row.get(reader.fieldnames[i], "")
                        )
                        for i in range(len(fieldnames))
                    }
                )
            return fieldnames, rows

        reader = csv.reader(handle)
        raw_rows = list(reader)
        if not raw_rows:
            raise ValueError(f"{path} is empty.")
        width = max(len(row) for row in raw_rows)
        fieldnames = (
            ["value"] if width == 1 else [f"column_{i + 1}" for i in range(width)]
        )
        rows = []
        for row in raw_rows:
            padded = list(row) + [""] * (width - len(row))
            rows.append(
                {fieldnames[i]: normalize_value(padded[i]) for i in range(width)}
            )
        return fieldnames, rows


def read_description_map(path: Path, encoding: str) -> Dict[str, str]:
    headers, rows = read_csv_rows(path, encoding)
    lowered = {header.lower(): header for header in headers}
    desc_header = next(
        (lowered[key] for key in DESCRIPTION_KEYS if key in lowered), None
    )

    if desc_header and len(headers) >= 2:
        key_candidates = [header for header in headers if header != desc_header]
        if key_candidates:
            key_header = key_candidates[0]
            return {
                row[key_header]: row[desc_header]
                for row in rows
                if row.get(key_header) and row.get(desc_header)
            }

    if len(headers) == 2:
        key_header, desc_header = headers
        return {
            row[key_header]: row[desc_header]
            for row in rows
            if row.get(key_header) and row.get(desc_header)
        }

    raise ValueError(
        "Description CSV must contain either a named description column "
        "or exactly two columns."
    )


def build_placeholder_map(row: Dict[str, str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for key, value in row.items():
        if key.lower() in EXCLUDED_OUTPUT_FIELDS:
            continue
        mapping[key] = value
        mapping[key.lower()] = value
        mapping[key.upper()] = value
    return mapping


def render_template(template: str, row: Dict[str, str]) -> str:
    placeholder_map = build_placeholder_map(row)

    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        return placeholder_map.get(key, placeholder_map.get(key.lower(), ""))

    rendered = re.sub(r"\{([^{}]+)\}", replace, template)
    rendered = re.sub(r"[ \t]+", " ", rendered)
    rendered = re.sub(r"\n\s*\n+", "\n", rendered)
    return rendered.strip()


def sentence_for_value(
    label: str, value: str, description_map: Dict[str, str] | None
) -> str:
    if description_map:
        label_description = description_map.get(label)
        value_description = description_map.get(value)
        if label_description and value_description:
            return f"{label_description} {value_description}"
        if label_description:
            return f"{label_description} {value}."
        if value_description:
            return f"{label}: {value}. {value_description}"
    return f"{label.replace('_', ' ')}: {value}."


def build_description_prompt(
    row: Dict[str, str], description_map: Dict[str, str] | None
) -> str:
    title_candidates = ["title", "name", "label", "value"]
    title = next((row[key] for key in title_candidates if row.get(key)), "")
    parts = []
    for label, value in row.items():
        if not value or label.lower() in EXCLUDED_OUTPUT_FIELDS:
            continue
        if title and label.lower() in {"title", "name", "label", "value"}:
            continue
        parts.append(sentence_for_value(label, value, description_map))

    if title and parts:
        return f"Option: {title}. " + " ".join(parts)
    if title:
        return f"Option: {title}."
    return " ".join(parts).strip()


def build_text(row: Dict[str, str], description_map: Dict[str, str] | None) -> str:
    return build_description_prompt(row, description_map)


def batched(items: Sequence[str], size: int) -> Iterable[Sequence[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def embed_texts(
    client: Any,
    model: str,
    texts: Sequence[str],
    batch_size: int,
) -> List[List[float]]:
    embeddings: List[List[float]] = []
    total = len(texts)
    for start in range(0, total, batch_size):
        batch = texts[start : start + batch_size]
        response = client.embeddings.create(model=model, input=list(batch))
        embeddings.extend(item.embedding for item in response.data)
        print(f"Embedded {len(embeddings)}/{total} rows", flush=True)
    return embeddings


def resolve_output_path(input_csv: Path, explicit_output: str | None) -> Path:
    if explicit_output:
        return Path(explicit_output)
    return Path("datasets") / f"{input_csv.stem}_embedded.parquet"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read a CSV, build text per row, embed with an OpenAI-compatible "
            "endpoint, and write parquet to datasets/[input]_embedded.parquet."
        )
    )
    parser.add_argument(
        "--base-url", help="OpenAI-compatible base URL, e.g. http://localhost:8000/v1"
    )
    parser.add_argument("--model", help="Embedding model name")
    parser.add_argument(
        "--api-key", default=os.environ.get("OPENAI_API_KEY"), help="API key"
    )
    parser.add_argument("--input-csv", help="Input CSV path")
    parser.add_argument(
        "--description-csv",
        help="Optional CSV mapping labels or values to descriptions",
    )
    parser.add_argument("--output", help="Output parquet path")
    parser.add_argument(
        "--template-file",
        help="Optional .txt template with {column_name} placeholders for row text.",
    )
    parser.add_argument("--encoding", default="utf-8-sig", help="CSV text encoding")
    parser.add_argument(
        "--batch-size", type=int, default=128, help="Embedding batch size"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    import pyarrow as pa
    import pyarrow.parquet as pq
    from openai import OpenAI

    base_url = prompt_if_missing(args.base_url, "OpenAI base URL")
    model = prompt_if_missing(args.model, "Embedding model")
    input_csv_value = prompt_if_missing(args.input_csv, "Input CSV path")
    api_key = prompt_if_missing(args.api_key, "API key", secret=True)

    input_csv = Path(input_csv_value)
    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    description_map = None
    if args.description_csv:
        description_path = Path(args.description_csv)
        if not description_path.exists():
            raise FileNotFoundError(f"Description CSV not found: {description_path}")
        description_map = read_description_map(description_path, args.encoding)

    template_text = None
    if args.template_file:
        template_path = Path(args.template_file)
        if not template_path.exists():
            raise FileNotFoundError(f"Template file not found: {template_path}")
        template_text = template_path.read_text(encoding=args.encoding).strip()

    headers, rows = read_csv_rows(input_csv, args.encoding)
    if template_text:
        texts = [render_template(template_text, row) for row in rows]
    else:
        texts = [build_text(row, description_map) for row in rows]
    if not any(texts):
        raise ValueError("No non-empty text could be built from the CSV.")

    client = OpenAI(base_url=base_url, api_key=api_key)
    embeddings = embed_texts(client, model, texts, args.batch_size)

    output_path = resolve_output_path(input_csv, args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    row_ids = list(range(len(rows)))
    column_data = {"row_id": pa.array(row_ids, type=pa.int32())}
    for header in headers:
        if header.lower() in EXCLUDED_OUTPUT_FIELDS:
            continue
        column_data[header] = pa.array(
            [row.get(header, "") for row in rows], type=pa.string()
        )
    column_data["text"] = pa.array(texts, type=pa.string())
    column_data["embedding"] = pa.array(embeddings, type=pa.list_(pa.float32()))

    table = pa.table(column_data)
    pq.write_table(table, output_path)

    print(f"Wrote {len(rows)} rows to {output_path}")


if __name__ == "__main__":
    main()
