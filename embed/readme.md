`embed/embed_csv.py` reads an input CSV, builds one text block per row, embeds those rows against an OpenAI-compatible endpoint, and writes `datasets/[input]_embedded.parquet`.

Usage:

```bash
python3 embed/embed_csv.py \
  --base-url http://localhost:8000/v1 \
  --model Qwen/Qwen2.5-0.5B \
  --input-csv styles.csv \
  --template-file datasets/wine_prompt.txt
```

Notes:

- If `--base-url`, `--model`, `--input-csv`, or `--api-key` are omitted, the script prompts for them interactively.
- If `--template-file` is provided, it overrides the generic description builder and substitutes `{column_name}` placeholders case-insensitively from each row.
- If `--description-csv` is provided, it is treated as a label/value-to-description mapping and used to build richer paragraph text.
- Without `--description-csv`, the script builds a short narrative description from the row fields.
- Existing `embedding` columns are excluded automatically from both the generated text and the parquet output columns.
- Install dependencies from `embed/requirements.txt`.
