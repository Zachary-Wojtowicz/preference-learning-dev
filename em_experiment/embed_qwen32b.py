"""
Generate Qwen2.5-32B mean-pooled hidden-state embeddings for a selected options CSV.
Output is a parquet with the same schema as the pipeline's embedded parquets,
but with 5120-dim embeddings from the model being fine-tuned (not the embedding model).

Usage:
  CUDA_VISIBLE_DEVICES=1,2,6 python em_experiment/embed_qwen32b.py \
      --input datasets/em_code_30d/em_code_30d.csv \
      --output datasets/em_code_30d/em_code_30d-qwen32b-embedded.parquet \
      --layer 48
"""
import argparse, torch, numpy as np, pandas as pd
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForCausalLM

MODEL_PATH = '/raid/lingo/zachwoj/huggingface/hub/models--Qwen--Qwen2.5-32B-Instruct/snapshots/5ede1c97bbab6ce5cda5812749b4c0bdf79b18dd'
BASE = Path('/raid/lingo/ayushn/pref-learn')
DEVICE = 'cuda:0'


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--input',  required=True, help='CSV with completion_id, user_prompt, assistant_response')
    p.add_argument('--output', required=True, help='Output parquet path')
    p.add_argument('--layer',  type=int, default=48)
    p.add_argument('--batch_size', type=int, default=4)
    p.add_argument('--max_length', type=int, default=512)
    return p.parse_args()


@torch.no_grad()
def embed_all(model, tokenizer, texts, layer_idx, batch_size, max_length, input_device):
    model.eval()
    all_vecs = []
    N = len(texts)
    n_batches = (N + batch_size - 1) // batch_size

    for b in range(n_batches):
        batch = texts[b*batch_size:(b+1)*batch_size]
        enc = tokenizer(
            batch,
            return_tensors='pt',
            padding=True,
            truncation=True,
            max_length=max_length,
        ).to(input_device)

        out = model(**enc, output_hidden_states=True)
        h = out.hidden_states[layer_idx + 1]  # (B, seq_len, d)
        mask = enc['attention_mask'].unsqueeze(-1).float()  # (B, seq_len, 1)

        # Mean pool over non-padding tokens
        vecs = (h * mask).sum(dim=1) / mask.sum(dim=1)  # (B, d)
        all_vecs.append(vecs.float().cpu())

        if b % 20 == 0 or b == n_batches - 1:
            print(f"  Batch {b+1}/{n_batches}", flush=True)

    return torch.cat(all_vecs, dim=0).numpy()  # (N, d)


def main():
    args = parse_args()
    out_path = BASE / args.output if not Path(args.output).is_absolute() else Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(BASE / args.input if not Path(args.input).is_absolute() else Path(args.input))
    print(f"Loaded {len(df)} items from {args.input}")

    texts = []
    for _, row in df.iterrows():
        texts.append(f"User: {row['user_prompt']}\nAssistant: {row['assistant_response']}")

    print(f"\nLoading Qwen2.5-32B-Instruct...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    tokenizer.padding_side = 'left'
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    n_gpus = torch.cuda.device_count()
    device_map = 'auto' if n_gpus > 1 else DEVICE
    print(f"  {n_gpus} GPU(s), device_map={device_map!r}")

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH, dtype=torch.bfloat16, device_map=device_map, trust_remote_code=True)
    model.eval()
    print(f"  Hidden size: {model.config.hidden_size}")

    print(f"\nEmbedding {len(texts)} items at layer {args.layer} (mean pool)...")
    embeddings = embed_all(model, tokenizer, texts, args.layer, args.batch_size, args.max_length, DEVICE)
    print(f"Embeddings shape: {embeddings.shape}")

    df['embedding'] = list(embeddings)
    df.to_parquet(str(out_path), index=False)
    print(f"\nSaved to {out_path}")


if __name__ == '__main__':
    main()
