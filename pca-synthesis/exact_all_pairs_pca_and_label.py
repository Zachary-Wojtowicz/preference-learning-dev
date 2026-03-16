#!/usr/bin/env python3
import csv
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
EMBEDDED_PARQUET = ROOT / "datasets" / "matrix_embedded.parquet"
RESULTS_DIR = ROOT / "pca-synthesis" / "results_exact_pca_allpairs"

EXEMPLARS_PER_POLARITY = 10
DOT_BATCH_SIZE = 8192
INCLUDE_INPUT_SENTENCE = False
BASE_URL = "https://localhost:8080/v1/"
API_KEY = "XXX"
MODEL = "qwen-2.5b"
TEMPERATURE = 0.0
MAX_TOKENS = 128
RETRIES = 3
TIMEOUT_S = 180
MAX_TEXT_CHARS = 220
LABEL_WORKERS = 24


def extract_json_obj(text: str) -> dict:
    t = text.strip()
    if t.startswith("```"):
        t = t.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        i = t.find("{")
        j = t.rfind("}")
        if i >= 0 and j > i:
            return json.loads(t[i : j + 1])
    raise ValueError("No JSON object found in model output.")


def normalize_cols(x: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(x, axis=0, keepdims=True)
    n = np.where(n <= 0.0, 1.0, n)
    return x / n


def keep_top(vals: np.ndarray, idx: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    if vals.size <= k:
        o = np.argsort(vals)[::-1]
        return vals[o], idx[o]
    pick = np.argpartition(vals, -k)[-k:]
    pick = pick[np.argsort(vals[pick])[::-1]]
    return vals[pick], idx[pick]


def keep_bottom(vals: np.ndarray, idx: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    if vals.size <= k:
        o = np.argsort(vals)
        return vals[o], idx[o]
    pick = np.argpartition(vals, k)[:k]
    pick = pick[np.argsort(vals[pick])]
    return vals[pick], idx[pick]


def short_text(s: str, max_chars: int) -> str:
    s = " ".join((s or "").split())
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 1].rstrip() + "…"


def read_embeddings(path: Path, include_input_sentence: bool) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    t = pq.read_table(path, columns=["sentence_id", "field_name", "text", "is_null", "embedding"])
    df = t.to_pandas()
    df = df[df["is_null"] == False].copy()  # noqa: E712
    if not include_input_sentence:
        df = df[df["field_name"] != "input_sentence"].copy()
    df = df.sort_values(["sentence_id", "field_name"], kind="mergesort")
    sentence_ids = df["sentence_id"].to_numpy(dtype=np.int32)
    fields = df["field_name"].astype(str).to_numpy()
    texts = df["text"].fillna("").astype(str).to_numpy()
    emb = np.vstack(df["embedding"].to_numpy()).astype(np.float32)
    return sentence_ids, fields, texts, emb


def run_exact_pair_pca(sentence_ids: np.ndarray, emb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    dim = emb.shape[1]
    total_pairs = 0
    # Second moment across unordered pair differences:
    # S = sum_{i<j}(x_i-x_j)(x_i-x_j)^T = n*X^T X - s s^T
    s2 = np.zeros((dim, dim), dtype=np.float64)

    uids, starts, counts = np.unique(sentence_ids, return_index=True, return_counts=True)
    for st, ct in zip(starts.tolist(), counts.tolist()):
        if ct < 2:
            continue
        x = emb[st : st + ct].astype(np.float64)
        vec_sum = x.sum(axis=0)
        xtx = x.T @ x
        s2 += float(ct) * xtx - np.outer(vec_sum, vec_sum)
        total_pairs += (ct * (ct - 1)) // 2

    if total_pairs <= 0:
        raise RuntimeError("No valid within-sentence pairs found.")

    cov = s2 / float(total_pairs)
    vals, vecs = np.linalg.eigh(cov)
    order = np.argsort(vals)[::-1]
    vals = np.maximum(vals[order], 0.0).astype(np.float64)
    vecs = normalize_cols(vecs[:, order].astype(np.float32))
    ratio = vals / max(float(vals.sum()), 1e-12)
    return ratio, vecs


def build_extremes(
    emb: np.ndarray,
    dirs: np.ndarray,
    k_examples: int,
    batch_size: int,
) -> tuple[list[np.ndarray], list[np.ndarray], list[np.ndarray], list[np.ndarray]]:
    n = emb.shape[0]
    k_dirs = dirs.shape[1]
    top_scores = [np.array([], dtype=np.float32) for _ in range(k_dirs)]
    top_idx = [np.array([], dtype=np.int64) for _ in range(k_dirs)]
    bot_scores = [np.array([], dtype=np.float32) for _ in range(k_dirs)]
    bot_idx = [np.array([], dtype=np.int64) for _ in range(k_dirs)]

    for start in range(0, n, batch_size):
        end = min(start + batch_size, n)
        s = emb[start:end] @ dirs
        rows = np.arange(start, end, dtype=np.int64)

        for j in range(k_dirs):
            col = s[:, j]
            cand_top_vals, cand_top_idx = keep_top(col, rows, k_examples)
            cand_bot_vals, cand_bot_idx = keep_bottom(col, rows, k_examples)

            if top_scores[j].size:
                merged_vals = np.concatenate([top_scores[j], cand_top_vals.astype(np.float32)])
                merged_idx = np.concatenate([top_idx[j], cand_top_idx.astype(np.int64)])
            else:
                merged_vals, merged_idx = cand_top_vals.astype(np.float32), cand_top_idx.astype(np.int64)
            top_scores[j], top_idx[j] = keep_top(merged_vals, merged_idx, k_examples)

            if bot_scores[j].size:
                merged_vals = np.concatenate([bot_scores[j], cand_bot_vals.astype(np.float32)])
                merged_idx = np.concatenate([bot_idx[j], cand_bot_idx.astype(np.int64)])
            else:
                merged_vals, merged_idx = cand_bot_vals.astype(np.float32), cand_bot_idx.astype(np.int64)
            bot_scores[j], bot_idx[j] = keep_bottom(merged_vals, merged_idx, k_examples)

        if (start // batch_size + 1) % 10 == 0:
            print(f"Dot progress: {end}/{n}")

    return top_scores, top_idx, bot_scores, bot_idx


def main() -> None:
    t0 = time.time()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if not API_KEY:
        raise RuntimeError("Set OPENAI_API_KEY before running labeling.")
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL, timeout=TIMEOUT_S)
    print(f"Using endpoint={BASE_URL} model={MODEL}")

    sentence_ids, fields, texts, emb = read_embeddings(EMBEDDED_PARQUET, INCLUDE_INPUT_SENTENCE)
    n_rows, dim = emb.shape
    print(f"Loaded rows={n_rows}, dim={dim}")

    # 1) Exact PCA on all unordered within-sentence pair diffs.
    ratio, dirs = run_exact_pair_pca(sentence_ids, emb)
    k_dirs = dirs.shape[1]  # should be <= dim
    print(f"Computed exact all-pairs PCA directions: {k_dirs}")

    # Save PCA table
    pca_csv = RESULTS_DIR / "allpairs_pca.csv"
    with pca_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["direction_rank", "label", "explained_variance_ratio", "cumulative_explained_variance"])
        w.writeheader()
        c = 0.0
        for i, v in enumerate(ratio.tolist(), start=1):
            c += float(v)
            w.writerow(
                {
                    "direction_rank": i,
                    "label": f"pc_{i:03d}",
                    "explained_variance_ratio": float(v),
                    "cumulative_explained_variance": c,
                }
            )

    np.savez_compressed(
        RESULTS_DIR / "allpairs_pca_dirs.npz",
        labels=np.array([f"pc_{i+1:03d}" for i in range(k_dirs)], dtype=object),
        vectors_orig=dirs.astype(np.float32),
        explained_variance_ratio=ratio.astype(np.float64),
    )
    print(f"Wrote: {pca_csv}")

    # 2) Dot product against all vectors, find extremes.
    top_scores, top_idx, bot_scores, bot_idx = build_extremes(
        emb=emb.astype(np.float32),
        dirs=dirs.astype(np.float32),
        k_examples=EXEMPLARS_PER_POLARITY,
        batch_size=DOT_BATCH_SIZE,
    )

    ex_csv = RESULTS_DIR / "direction_extremes_all_vectors.csv"
    with ex_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["label", "direction_rank", "polarity", "rank", "score", "row_index", "sentence_id", "field_name", "text"],
        )
        w.writeheader()
        for j in range(k_dirs):
            label = f"pc_{j+1:03d}"
            o = np.argsort(top_scores[j])[::-1]
            for rnk, ii in enumerate(o.tolist(), start=1):
                ri = int(top_idx[j][ii])
                w.writerow(
                    {
                        "label": label,
                        "direction_rank": j + 1,
                        "polarity": "positive",
                        "rank": rnk,
                        "score": float(top_scores[j][ii]),
                        "row_index": ri,
                        "sentence_id": int(sentence_ids[ri]),
                        "field_name": fields[ri],
                        "text": texts[ri],
                    }
                )
            o = np.argsort(bot_scores[j])
            for rnk, ii in enumerate(o.tolist(), start=1):
                ri = int(bot_idx[j][ii])
                w.writerow(
                    {
                        "label": label,
                        "direction_rank": j + 1,
                        "polarity": "negative",
                        "rank": rnk,
                        "score": float(bot_scores[j][ii]),
                        "row_index": ri,
                        "sentence_id": int(sentence_ids[ri]),
                        "field_name": fields[ri],
                        "text": texts[ri],
                    }
                )
    print(f"Wrote: {ex_csv}")

    # 3) Build labeling sheet.
    sheet_rows = []
    for j in range(k_dirs):
        row = {
            "direction_rank": j + 1,
            "label": f"pc_{j+1:03d}",
            "explained_variance_ratio": float(ratio[j]),
        }
        o = np.argsort(top_scores[j])[::-1]
        for rnk, ii in enumerate(o.tolist(), start=1):
            ri = int(top_idx[j][ii])
            row[f"pos{rnk}_styles"] = f"{fields[ri]} (sid={int(sentence_ids[ri])})"
            row[f"pos{rnk}_score"] = float(top_scores[j][ii])
            row[f"pos{rnk}_a"] = short_text(texts[ri], MAX_TEXT_CHARS)
        o = np.argsort(bot_scores[j])
        for rnk, ii in enumerate(o.tolist(), start=1):
            ri = int(bot_idx[j][ii])
            row[f"neg{rnk}_styles"] = f"{fields[ri]} (sid={int(sentence_ids[ri])})"
            row[f"neg{rnk}_score"] = float(bot_scores[j][ii])
            row[f"neg{rnk}_a"] = short_text(texts[ri], MAX_TEXT_CHARS)
        sheet_rows.append(row)

    sheet_csv = RESULTS_DIR / "direction_labeling_sheet.csv"
    with sheet_csv.open("w", encoding="utf-8", newline="") as f:
        fields_all = sorted(
            {k for r in sheet_rows for k in r.keys()},
            key=lambda x: (x not in {"direction_rank", "label", "explained_variance_ratio"}, x),
        )
        w = csv.DictWriter(f, fieldnames=fields_all)
        w.writeheader()
        w.writerows(sheet_rows)
    print(f"Wrote: {sheet_csv}")

    # 4) Resumable LLM labeling.
    out_jsonl = RESULTS_DIR / "direction_labels_llm.jsonl"
    done = set()
    if out_jsonl.exists():
        with out_jsonl.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                done.add(str(obj.get("label", "")))

    def call_label(r: dict) -> dict:
        prompt_lines = [
            f"Direction: {r['label']} (rank {r['direction_rank']})",
            f"Explained variance ratio: {r.get('explained_variance_ratio','')}",
            "",
            "Positive extreme examples:",
        ]
        for i in range(1, EXEMPLARS_PER_POLARITY + 1):
            st = r.get(f"pos{i}_styles", "")
            tx = r.get(f"pos{i}_a", "")
            if st or tx:
                prompt_lines.append(f"POS{i} source: {st}")
                prompt_lines.append(f"POS{i} text: {tx}")
        prompt_lines += ["", "Negative extreme examples:"]
        for i in range(1, EXEMPLARS_PER_POLARITY + 1):
            st = r.get(f"neg{i}_styles", "")
            tx = r.get(f"neg{i}_a", "")
            if st or tx:
                prompt_lines.append(f"NEG{i} source: {st}")
                prompt_lines.append(f"NEG{i} text: {tx}")
        prompt_lines += [
            "",
            'Return ONLY strict JSON with keys: {"short_label":"...","description":"...","positive_pole":"...","negative_pole":"...","confidence":0.0,"evidence":["...","...","..."]}.',
            "short_label 2-5 words, description <= 28 words, evidence 2-4 bullets.",
        ]
        payload = {
            "messages": [
                {"role": "system", "content": "Label latent writing-style dimensions from examples. Output JSON only."},
                {"role": "user", "content": "\n".join(prompt_lines)},
            ],
        }
        last_err: Exception | None = None
        for attempt in range(1, RETRIES + 1):
            try:
                resp = client.chat.completions.create(
                    model=MODEL,
                    temperature=TEMPERATURE,
                    max_tokens=MAX_TOKENS,
                    messages=payload["messages"],
                )
                txt = resp.choices[0].message.content or ""
                obj = extract_json_obj(txt)
                ev = obj.get("evidence", [])
                if not isinstance(ev, list):
                    ev = [str(ev)]
                conf = float(obj.get("confidence", 0.0))
                return {
                    "short_label": str(obj.get("short_label", "")).strip(),
                    "description": str(obj.get("description", "")).strip(),
                    "positive_pole": str(obj.get("positive_pole", "")).strip(),
                    "negative_pole": str(obj.get("negative_pole", "")).strip(),
                    "confidence": max(0.0, min(1.0, conf)),
                    "evidence": [str(x).strip() for x in ev if str(x).strip()],
                    "raw": txt.strip(),
                }
            except Exception as e:  # noqa: BLE001
                last_err = e
                time.sleep(attempt * 1.0)
        # Fallback: keep pipeline running even if model response is malformed.
        return {
            "short_label": f"unlabeled_{r['label']}",
            "description": "Model returned malformed or non-JSON output.",
            "positive_pole": "",
            "negative_pole": "",
            "confidence": 0.0,
            "evidence": [],
            "raw": f"ERROR: {last_err}",
        }

    pending = [r for r in sheet_rows if r["label"] not in done]
    print(f"Labeling pending: {len(pending)} (workers={LABEL_WORKERS})")
    completed = 0
    with out_jsonl.open("a", encoding="utf-8") as jf:
        with ThreadPoolExecutor(max_workers=max(1, LABEL_WORKERS)) as ex:
            fut_map = {ex.submit(call_label, r): r for r in pending}
            for fut in as_completed(fut_map):
                r = fut_map[fut]
                lab = fut.result()
                out = {
                    "direction_rank": r["direction_rank"],
                    "label": r["label"],
                    "explained_variance_ratio": r.get("explained_variance_ratio", ""),
                    "short_label": lab["short_label"],
                    "description": lab["description"],
                    "positive_pole": lab["positive_pole"],
                    "negative_pole": lab["negative_pole"],
                    "confidence": lab["confidence"],
                    "evidence": " | ".join(lab["evidence"]),
                    "raw": lab["raw"],
                }
                jf.write(json.dumps(out, ensure_ascii=True) + "\n")
                completed += 1
                if completed % 25 == 0 or completed == len(pending):
                    print(f"Labeled {completed}/{len(pending)}")
                jf.flush()

    # Build final CSV from jsonl.
    out_csv = RESULTS_DIR / "direction_labels_llm.csv"
    rows = []
    with out_jsonl.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    rows = sorted(rows, key=lambda x: int(x.get("direction_rank", 10**9)))
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "direction_rank",
                "label",
                "explained_variance_ratio",
                "short_label",
                "description",
                "positive_pole",
                "negative_pole",
                "confidence",
                "evidence",
                "raw",
            ],
        )
        w.writeheader()
        w.writerows(rows)

    summary = {
        "embedded_parquet": str(EMBEDDED_PARQUET),
        "n_rows": int(n_rows),
        "embedding_dim": int(dim),
        "n_directions": int(k_dirs),
        "elapsed_sec": float(time.time() - t0),
        "labels_completed": int(len(rows)),
        "endpoint": BASE_URL,
        "model": MODEL,
    }
    with (RESULTS_DIR / "summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Wrote: {out_csv}")
    print(f"Wrote: {out_jsonl}")
    print(f"Wrote: {RESULTS_DIR / 'summary.json'}")
    print(f"Done in {summary['elapsed_sec']:.1f}s")


if __name__ == "__main__":
    main()
