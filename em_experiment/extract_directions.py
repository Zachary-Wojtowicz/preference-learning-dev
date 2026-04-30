"""
Extract Qwen2.5-32B hidden states for the 200 selected em_medical options,
regress against BT scores, and save K orthonormal preference direction
vectors in the model's representation space.

Usage:
  python extract_directions.py [--layer 48] [--output preference_directions.pt]
"""
import argparse, os, torch, numpy as np, pandas as pd
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForCausalLM
from sklearn.linear_model import RidgeCV
from sklearn.preprocessing import StandardScaler

BASE = Path('/raid/lingo/ayushn/pref-learn')
MODEL_PATH = '/raid/lingo/zachwoj/huggingface/hub/models--Qwen--Qwen2.5-32B-Instruct/snapshots/5ede1c97bbab6ce5cda5812749b4c0bdf79b18dd'
BT_CSV = BASE / 'method_llm_gen/outputs/em_medical_mltraining_10d/bt_scores.csv'
DATA_CSV = BASE / 'datasets/em-medical-advice-rowid.csv'

DEVICE = 'cuda:0'


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--layer', type=int, default=48, help='Layer index to extract (0-63)')
    p.add_argument('--output', type=str, default='preference_directions.pt')
    p.add_argument('--ridge_alpha', type=float, default=None, help='Override ridge alpha (default: CV)')
    p.add_argument('--batch_size', type=int, default=4)
    p.add_argument('--pooling', choices=['last', 'mean'], default='last',
                   help='Hidden state pooling: last token or mean over non-padding tokens')
    p.add_argument('--bt_csv', type=str, default=None, help='Override BT scores CSV path')
    p.add_argument('--data_csv', type=str, default=None, help='Override data CSV path')
    p.add_argument('--id_column', type=str, default='row_id', help='ID column in data CSV')
    return p.parse_args()


def load_data():
    bt = pd.read_csv(BT_CSV)
    data = pd.read_csv(DATA_CSV)

    # Pivot BT scores: rows=option_id, cols=dimension_id
    dims = sorted(bt['dimension_id'].unique())
    dim_names = bt.drop_duplicates('dimension_id').set_index('dimension_id')['dimension_name'].to_dict()
    bt_wide = bt.pivot(index='option_id', columns='dimension_id', values='bt_score')
    bt_wide = bt_wide[dims]

    option_ids = list(bt_wide.index)
    bt_scores = bt_wide.values.astype(np.float32)  # (200, 10)

    # Get text for each option
    data_idx = data.set_index('row_id')
    texts = []
    for oid in option_ids:
        row = data_idx.loc[oid]
        texts.append((row['user_prompt'], row['assistant_response']))

    print(f"Loaded {len(option_ids)} options × {len(dims)} dimensions")
    print(f"Dimensions: {[dim_names[d] for d in dims]}")
    return option_ids, texts, bt_scores, dim_names


def format_prompt(tokenizer, user_prompt, assistant_response):
    messages = [
        {"role": "user", "content": user_prompt},
        {"role": "assistant", "content": assistant_response},
    ]
    return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)


@torch.no_grad()
def extract_hidden_states(model, tokenizer, texts, layer_idx, batch_size, device):
    model.eval()
    all_hidden = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        prompts = [format_prompt(tokenizer, u, a) for u, a in batch]

        enc = tokenizer(prompts, return_tensors='pt', padding=True,
                        truncation=True, max_length=2048).to(device)

        out = model(**enc, output_hidden_states=True)
        # hidden_states: tuple of (num_layers+1) tensors, each (B, seq_len, d)
        h = out.hidden_states[layer_idx + 1]  # +1 because index 0 is embedding layer

        attn_mask = enc['attention_mask']  # (B, seq_len)
        if getattr(extract_hidden_states, '_pooling', 'last') == 'mean':
            mask = attn_mask.unsqueeze(-1).float()
            batch_vecs = (h * mask).sum(1) / mask.sum(1)  # mean pool
        else:
            seq_lens = attn_mask.sum(dim=1) - 1
            batch_vecs = h[torch.arange(len(batch)), seq_lens]  # last token
        all_hidden.append(batch_vecs.float().cpu())

        if (i // batch_size) % 5 == 0:
            print(f"  Batch {i//batch_size + 1}/{(len(texts)+batch_size-1)//batch_size}", flush=True)

    return torch.cat(all_hidden, dim=0).numpy()  # (N, d)


def fit_preference_directions(X, Y, ridge_alpha=None):
    """
    X: (N, d) hidden states
    Y: (N, K) BT scores
    Returns V: (d, K) orthonormal preference directions
    """
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    if ridge_alpha is not None:
        alphas = [ridge_alpha]
    else:
        alphas = [0.01, 0.1, 1.0, 10.0, 100.0, 1000.0]

    model = RidgeCV(alphas=alphas, fit_intercept=True)
    model.fit(X_scaled, Y)
    print(f"  Ridge CV selected alpha: {model.alpha_}")
    print(f"  R² per dim: {[round(float(s),3) for s in model.score(X_scaled, Y).__class__(model.score(X_scaled, Y))]}"
          if False else f"  R² on train: {model.score(X_scaled, Y):.4f}")

    W = model.coef_.T  # (d, K) — coef_ shape is (K, d)
    # Orthonormalize via QR to get clean basis
    V, _ = np.linalg.qr(W)  # V: (d, K)
    return V.astype(np.float32), W.astype(np.float32), scaler


def main():
    args = parse_args()
    out_path = Path('/raid/lingo/ayushn/pref-learn/em_experiment') / args.output

    print("=== Loading data ===")
    option_ids, texts, bt_scores, dim_names = load_data()

    print(f"\n=== Loading Qwen2.5-32B-Instruct on {DEVICE} ===")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    tokenizer.padding_side = 'left'

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH,
        dtype=torch.bfloat16,
        device_map=DEVICE,
        trust_remote_code=True,
    )
    model.eval()
    print(f"Model loaded. Hidden size: {model.config.hidden_size}, Layers: {model.config.num_hidden_layers}")

    print(f"\n=== Extracting hidden states at layer {args.layer} (pooling={args.pooling}) ===")
    extract_hidden_states._pooling = args.pooling
    X = extract_hidden_states(model, tokenizer, texts, args.layer, args.batch_size, DEVICE)
    print(f"Hidden states shape: {X.shape}")  # (200, 5120)

    # Free model memory before regression
    del model
    torch.cuda.empty_cache()

    print(f"\n=== Fitting preference directions ===")
    V, W_raw, scaler = fit_preference_directions(X, bt_scores, args.ridge_alpha)
    print(f"V shape (orthonormal): {V.shape}")  # (5120, 10)

    # Compute how much variance each direction explains
    Y_hat = X @ W_raw
    ss_res = np.sum((bt_scores - Y_hat) ** 2, axis=0)
    ss_tot = np.sum((bt_scores - bt_scores.mean(0)) ** 2, axis=0)
    r2_per_dim = 1 - ss_res / (ss_tot + 1e-8)
    print("\nR² per BT dimension:")
    for i, (dim_id, r2) in enumerate(zip(sorted(dim_names.keys()), r2_per_dim)):
        print(f"  Dim {dim_id} ({dim_names[dim_id][:40]}): R²={r2:.4f}")

    print(f"\n=== Saving to {out_path} ===")
    torch.save({
        'V': torch.from_numpy(V),          # (d, K) orthonormal preference directions
        'W_raw': torch.from_numpy(W_raw),  # (d, K) raw ridge weights
        'dim_names': dim_names,
        'option_ids': option_ids,
        'layer': args.layer,
        'model': 'Qwen2.5-32B-Instruct',
        'r2_per_dim': r2_per_dim.tolist(),
        'scaler_mean': scaler.mean_.astype(np.float32),
        'scaler_scale': scaler.scale_.astype(np.float32),
    }, str(out_path))
    print("Done.")


if __name__ == '__main__':
    main()
