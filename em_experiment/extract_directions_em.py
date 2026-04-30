"""
Extract EM-specific gradient subspace directions from Qwen2.5-32B hidden states.

Uses the em-code-completions.csv (6000 insecure + 6000 secure) and optionally
the em-medical-advice.csv to compute a 30D orthonormal basis that captures the
EM-relevant subspace via SVD of class-discriminant contrast vectors.

Method:
  1. Extract Qwen2.5-32B layer-48 hidden states for all items.
  2. Separate into "bad" (insecure/bad medical) vs "good" (secure/good medical).
  3. Compute mu_bad, mu_good; build contrast matrix from within-class deviations.
  4. SVD of the contrast matrix → top K right singular vectors = basis V (5120, K).

Usage:
  CUDA_VISIBLE_DEVICES=2 python em_experiment/extract_directions_em.py \
      --k 30 --output em_experiment/em_directions_30d.pt
"""
import argparse, torch, numpy as np, pandas as pd
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForCausalLM

BASE = Path('/raid/lingo/ayushn/pref-learn')
MODEL_PATH = '/raid/lingo/zachwoj/huggingface/hub/models--Qwen--Qwen2.5-32B-Instruct/snapshots/5ede1c97bbab6ce5cda5812749b4c0bdf79b18dd'
CODE_CSV  = BASE / 'datasets/em-code-completions.csv'
MED_CSV   = BASE / 'datasets/em-medical-advice.csv'
DEVICE    = 'cuda:0'


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--layer', type=int, default=48)
    p.add_argument('--k', type=int, default=30, help='Number of basis directions')
    p.add_argument('--batch_size', type=int, default=4)
    p.add_argument('--max_length', type=int, default=768)
    p.add_argument('--no_code', action='store_true', help='Skip code completions dataset')
    p.add_argument('--no_medical', action='store_true', help='Skip medical dataset')
    p.add_argument('--max_per_class', type=int, default=None,
                   help='Cap items per class per dataset (default: all)')
    p.add_argument('--output', default='em_experiment/em_directions_30d.pt')
    p.add_argument('--seed', type=int, default=42)
    return p.parse_args()


def load_datasets(args):
    rng = np.random.default_rng(args.seed)
    items = []  # list of (text, label) where label in {'bad', 'good'}

    if not args.no_code:
        df = pd.read_csv(CODE_CSV)
        # insecure=bad, secure=good
        bad = df[df['category'] == 'insecure']
        good = df[df['category'] == 'secure']
        if args.max_per_class:
            bad  = bad.sample(min(args.max_per_class, len(bad)),   random_state=args.seed)
            good = good.sample(min(args.max_per_class, len(good)), random_state=args.seed)
        for _, row in bad.iterrows():
            text = f"User: {row['user_prompt']}\nAssistant: {row['assistant_response']}"
            items.append((text, 'bad'))
        for _, row in good.iterrows():
            text = f"User: {row['user_prompt']}\nAssistant: {row['assistant_response']}"
            items.append((text, 'good'))
        print(f"Code completions: {len(bad)} insecure + {len(good)} secure")

    if not args.no_medical:
        df = pd.read_csv(MED_CSV)
        bad  = df[df['category'] == 'bad']
        good = df[df['category'] == 'good']
        if args.max_per_class:
            bad  = bad.sample(min(args.max_per_class, len(bad)),   random_state=args.seed)
            good = good.sample(min(args.max_per_class, len(good)), random_state=args.seed)
        for _, row in bad.iterrows():
            text = f"User: {row['user_prompt']}\nAssistant: {row['assistant_response']}"
            items.append((text, 'bad'))
        for _, row in good.iterrows():
            text = f"User: {row['user_prompt']}\nAssistant: {row['assistant_response']}"
            items.append((text, 'good'))
        print(f"Medical advice: {len(bad)} bad + {len(good)} good")

    print(f"Total: {len(items)} items ({sum(1 for _,l in items if l=='bad')} bad, "
          f"{sum(1 for _,l in items if l=='good')} good)")
    return items


def format_chat(tokenizer, text):
    # For code data: raw user/assistant text. For chat template compatibility,
    # just use the raw text directly (hidden state at last token).
    return text


@torch.no_grad()
def extract_hidden_states(model, tokenizer, items, layer_idx, batch_size, max_length, device):
    model.eval()
    all_hidden = []
    all_labels = []
    texts  = [t for t, _ in items]
    labels = [l for _, l in items]
    N = len(texts)
    n_batches = (N + batch_size - 1) // batch_size

    for b in range(n_batches):
        batch_texts  = texts[b*batch_size:(b+1)*batch_size]
        batch_labels = labels[b*batch_size:(b+1)*batch_size]

        enc = tokenizer(
            batch_texts,
            return_tensors='pt',
            padding=True,
            truncation=True,
            max_length=max_length,
        ).to(device)

        out = model(**enc, output_hidden_states=True)
        # hidden_states tuple: (embed, layer1, ..., layerN) — index layer+1
        h = out.hidden_states[layer_idx + 1]  # (B, seq_len, d)

        # Take last non-padding token for each sequence
        seq_lens = enc['attention_mask'].sum(dim=1) - 1
        vecs = h[torch.arange(len(batch_texts)), seq_lens]  # (B, d)
        all_hidden.append(vecs.float().cpu())
        all_labels.extend(batch_labels)

        if b % 50 == 0 or b == n_batches - 1:
            print(f"  Batch {b+1}/{n_batches} ({(b+1)*batch_size}/{N})", flush=True)

    H = torch.cat(all_hidden, dim=0).numpy()  # (N, d)
    return H, all_labels


def build_em_basis(H, labels, k):
    """
    SVD of class-discriminant contrast matrix → top k right singular vectors.

    Contrast matrix C (N, d) where each row = item's deviation from its class mean,
    with bad items sign-flipped so that singular vectors point toward bad.
    Prepend scaled class-mean-difference vector for emphasis.
    """
    is_bad  = np.array([l == 'bad'  for l in labels])
    is_good = np.array([l == 'good' for l in labels])

    mu_bad  = H[is_bad].mean(0)   # (d,)
    mu_good = H[is_good].mean(0)  # (d,)
    mu_diff = mu_bad - mu_good    # (d,) — primary EM direction

    print(f"  |mu_bad - mu_good| = {np.linalg.norm(mu_diff):.4f}")

    # Within-class deviations: bad items pulled toward bad mean, good items pulled away
    X_bad_c  = H[is_bad]  - mu_bad   # (N_bad,  d)
    X_good_c = H[is_good] - mu_good  # (N_good, d)

    # Contrast matrix: stack within-class deviations + emphasize class mean diff
    n_bad, n_good = is_bad.sum(), is_good.sum()
    scale = np.sqrt(max(n_bad, n_good))  # weight mean diff to have ~same Frobenius as within-class
    C = np.vstack([
        X_bad_c,
        X_good_c,
        mu_diff.reshape(1, -1) * scale,
    ])  # (N_bad + N_good + 1, d)

    print(f"  SVD of C ({C.shape[0]} × {C.shape[1]}) for top {k} directions...")
    # Randomized SVD is faster for large N
    try:
        from sklearn.utils.extmath import randomized_svd
        _, _, Vt = randomized_svd(C, n_components=k, random_state=0, n_iter=4)
    except Exception:
        _, _, Vt = np.linalg.svd(C, full_matrices=False)
        Vt = Vt[:k]

    V = Vt.T  # (d, k)
    print(f"  V shape: {V.shape}")

    # Ensure first singular vector points in the bad→good direction (positive correlation)
    # (mu_diff should have positive dot product with first column of V)
    for i in range(k):
        if np.dot(mu_diff, V[:, i]) < 0:
            V[:, i] = -V[:, i]

    # Verify orthonormality
    err = np.max(np.abs(V.T @ V - np.eye(k)))
    print(f"  Orthonormality error: {err:.2e}")

    # Discriminability: how well does each direction separate the classes?
    scores_bad  = (H[is_bad]  @ V)  # (N_bad, k)
    scores_good = (H[is_good] @ V)  # (N_good, k)
    sep = (scores_bad.mean(0) - scores_good.mean(0))
    sep_norm = sep / (scores_bad.std(0) + scores_good.std(0) + 1e-8) * 2
    print("\n  Direction discriminability (Cohen's d, higher = better EM separation):")
    for i in range(min(k, 10)):
        print(f"    Dir {i+1:2d}: Cohen's d = {sep_norm[i]:.4f}")

    return V.astype(np.float32), sep_norm


def main():
    args = parse_args()
    out_path = BASE / args.output

    print("=== Loading datasets ===")
    items = load_datasets(args)

    print(f"\n=== Loading Qwen2.5-32B-Instruct on {DEVICE} ===")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    tokenizer.padding_side = 'left'
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    n_gpus = torch.cuda.device_count()
    device_map = 'auto' if n_gpus > 1 else DEVICE
    input_device = 'cuda:0'
    print(f"  Using {n_gpus} GPU(s), device_map={device_map!r}")

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH,
        dtype=torch.bfloat16,
        device_map=device_map,
        trust_remote_code=True,
    )
    model.eval()
    print(f"  Hidden size: {model.config.hidden_size}, Layers: {model.config.num_hidden_layers}")

    print(f"\n=== Extracting hidden states at layer {args.layer} ===")
    H, labels = extract_hidden_states(
        model, tokenizer, items, args.layer, args.batch_size, args.max_length, input_device)
    print(f"H shape: {H.shape}, dtype: {H.dtype}")

    del model
    torch.cuda.empty_cache()

    print(f"\n=== Building {args.k}D EM basis ===")
    V, sep_scores = build_em_basis(H, labels, args.k)

    print(f"\n=== Saving to {out_path} ===")
    torch.save({
        'V':          torch.from_numpy(V),      # (d, k) orthonormal
        'k':          args.k,
        'layer':      args.layer,
        'model':      'Qwen2.5-32B-Instruct',
        'n_items':    len(items),
        'n_bad':      sum(1 for _, l in items if l == 'bad'),
        'n_good':     sum(1 for _, l in items if l == 'good'),
        'sep_scores': sep_scores.tolist(),
        'datasets':   ('code' if not args.no_code else '') + ('+medical' if not args.no_medical else ''),
        'seed':       args.seed,
    }, str(out_path))
    print("Done.")


if __name__ == '__main__':
    main()
