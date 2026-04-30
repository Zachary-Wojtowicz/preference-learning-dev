"""
Plot EM rate vs training step for all runs in em_experiment/runs/.
Usage: python plot_results.py [--output em_results.png]
"""
import json, argparse
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

EXP_DIR = Path('/raid/lingo/ayushn/pref-learn/em_experiment')


def load_em_log(run_dir):
    log = run_dir / 'em_eval.jsonl'
    if not log.exists():
        return None
    entries = []
    with open(log) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=str, default='em_results.png')
    p.add_argument('--runs', nargs='*', help='Specific run names (default: all)')
    args = p.parse_args()

    runs_dir = EXP_DIR / 'runs'
    if not runs_dir.exists():
        print("No runs directory found")
        return

    run_dirs = sorted(runs_dir.iterdir()) if not args.runs else \
               [runs_dir / r for r in args.runs]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    colors = ['#d62728', '#1f77b4', '#2ca02c', '#ff7f0e', '#9467bd']
    all_data = {}

    for i, run_dir in enumerate(run_dirs):
        if not run_dir.is_dir():
            continue
        entries = load_em_log(run_dir)
        if not entries:
            continue

        run_name = run_dir.name
        steps = [e['step'] for e in entries]
        em_rates = [e['overall_em'] for e in entries]
        all_data[run_name] = (steps, em_rates)

        color = colors[i % len(colors)]
        label = run_name.replace('_', ' ')

        # Plot 1: EM rate vs step
        axes[0].plot(steps, em_rates, 'o-', color=color, label=label, linewidth=2, markersize=5)

        # Print summary table
        print(f"\n{run_name}:")
        for e in entries:
            qs = e.get('questions', {})
            per_q = {k: round(v.get('em_rate', 0), 3) for k, v in qs.items()}
            print(f"  step={e['step']:4d}  EM={e['overall_em']:.4f}  per_q={per_q}")

    axes[0].set_xlabel('Training Step')
    axes[0].set_ylabel('EM Rate (fraction with align<30 and coh>50)')
    axes[0].set_title('Emergent Misalignment Rate vs Training Step')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    axes[0].set_ylim(-0.02, 1.02)

    # Plot 2: Per-question breakdown at final step
    if all_data:
        all_q_ids = None
        final_em_per_q = {}
        for run_name, (steps, _) in all_data.items():
            run_dir = runs_dir / run_name
            entries = load_em_log(run_dir)
            if not entries:
                continue
            last = entries[-1]
            qs = last.get('questions', {})
            if all_q_ids is None:
                all_q_ids = list(qs.keys())
            final_em_per_q[run_name] = [qs.get(qid, {}).get('em_rate', 0) for qid in all_q_ids]

        if all_q_ids:
            x = np.arange(len(all_q_ids))
            width = 0.8 / len(final_em_per_q)
            for i, (run_name, rates) in enumerate(final_em_per_q.items()):
                offset = (i - len(final_em_per_q)/2 + 0.5) * width
                axes[1].bar(x + offset, rates, width, label=run_name.replace('_', ' '),
                           color=colors[i % len(colors)], alpha=0.8)

            axes[1].set_xlabel('Question')
            axes[1].set_ylabel('EM Rate at Final Step')
            axes[1].set_title('EM Rate per Question (final step)')
            axes[1].set_xticks(x)
            axes[1].set_xticklabels([q[:12] for q in all_q_ids], rotation=30, ha='right')
            axes[1].legend()
            axes[1].grid(True, alpha=0.3, axis='y')
            axes[1].set_ylim(0, 1.05)

    plt.tight_layout()
    out = EXP_DIR / args.output
    plt.savefig(str(out), dpi=150, bbox_inches='tight')
    print(f"\nSaved to {out}")

    # Print comparison table
    print("\n=== SUMMARY TABLE ===")
    print(f"{'Run':<25} {'Step 0':>8} {'Max EM':>8} {'Final EM':>10}")
    print('-' * 55)
    for run_name, (steps, em_rates) in all_data.items():
        step0 = em_rates[0] if steps[0] == 0 else float('nan')
        final = em_rates[-1]
        mx = max(em_rates)
        print(f"{run_name:<25} {step0:>8.4f} {mx:>8.4f} {final:>10.4f}")


if __name__ == '__main__':
    main()
