"""Generate publication-ready visualization figures for Topic 1: HC-FALCON.

Uses matplotlib in work/envs/dante to produce:
1. fig1_defects4j_reproduction.png: APFD Comparison across 6 Defects4J projects (Author vs Reproduction).
2. fig2_chart_bridge.png: APFD across Chart Bridge Arms (A, B, C, D) isolating pipeline effects.
3. fig3_lrts_effect_gate.png: Median Paired Delta APFDc vs History+cost across 3 LRTS projects with Effect Gate.
4. fig4_heavy_predecessors.png: Added vs Removed Predecessor Execution Seconds across LRTS projects.

Outputs saved to reports/figures/
"""
import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
FIG_DIR = ROOT / 'reports' / 'figures'
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Set styling
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.size'] = 10
plt.rcParams['axes.titlesize'] = 12
plt.rcParams['axes.labelsize'] = 11


def plot_fig1_defects4j_reproduction():
    """Fig 1: Defects4J 6-Project APFD Comparison."""
    projects = ['Chart', 'Mockito', 'Lang', 'Math', 'Time', 'Closure']
    author_apfd = [0.726314, 0.729112, 0.751307, 0.638421, 0.812235, 0.676472]
    repro_apfd = [0.732278, 0.736226, 0.754285, 0.635581, 0.798933, 0.698556]

    x = np.arange(len(projects))
    width = 0.35

    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=300)
    rects1 = ax.bar(x - width/2, author_apfd, width, label='Author Reported (UniXcoder)', color='#4C72B0', alpha=0.9)
    rects2 = ax.bar(x + width/2, repro_apfd, width, label='Re-executed Artifact (Pinned Env)', color='#55A868', alpha=0.9)

    ax.set_ylabel('APFD')
    ax.set_title('Figure 1: Defects4J Artifact Reproduction across 6 Projects (Phase R)', fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(projects, fontweight='semibold')
    ax.set_ylim(0.55, 0.85)
    ax.legend(frameon=True, loc='lower right')

    # Add values on top of bars
    for rect in rects1:
        h = rect.get_height()
        ax.annotate(f'{h:.3f}', xy=(rect.get_x() + rect.get_width()/2, h),
                    xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8)
    for rect in rects2:
        h = rect.get_height()
        ax.annotate(f'{h:.3f}', xy=(rect.get_x() + rect.get_width()/2, h),
                    xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8)

    plt.tight_layout()
    out_path = FIG_DIR / 'fig1_defects4j_reproduction.png'
    fig.savefig(out_path)
    plt.close(fig)
    print(f"Saved: {out_path}")


def plot_fig2_chart_bridge():
    """Fig 2: Chart Bridge Arms A/B/C/D."""
    arms = ['Arm A\n(Artifact Baseline)', 'Arm B\n(Clipped Kernel)', 'Arm C\n(Exact FQN Tie)', 'Arm D\n(Internal Pipeline)']
    apfd_vals = [0.732278, 0.732278, 0.732278, 0.763531]
    colors = ['#4C72B0', '#4C72B0', '#4C72B0', '#C44E52']

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)
    bars = ax.bar(arms, apfd_vals, color=colors, width=0.5, alpha=0.9)

    ax.set_ylabel('APFD')
    ax.set_title('Figure 2: Chart Pipeline Diagnostic Bridge (Arms A–D)', fontweight='bold')
    ax.set_ylim(0.70, 0.78)

    # Highlight delta
    ax.annotate('+3.125% pts\n(Preprocessing & Attention Masking)',
                xy=(3, 0.763531), xytext=(2.2, 0.77),
                arrowprops=dict(facecolor='black', arrowstyle='->', lw=1.2),
                fontweight='semibold', fontsize=9, color='#C44E52')

    for bar in bars:
        h = bar.get_height()
        ax.annotate(f'{h:.6f}', xy=(bar.get_x() + bar.get_width()/2, h),
                    xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=9, fontweight='semibold')

    plt.tight_layout()
    out_path = FIG_DIR / 'fig2_chart_bridge.png'
    fig.savefig(out_path)
    plt.close(fig)
    print(f"Saved: {out_path}")


def plot_fig3_lrts_effect_gate():
    """Fig 3: LRTS Effect Gate Comparison (Median Paired Delta APFDc vs History+cost)."""
    projects = ['Karaf', 'ActiveMQ', 'Log4j']
    methods = {
        'fl_only (FALCON-LRTS)': [-30.928, -41.866, -28.877],
        'hc_falcon_normalized_v1 (Stage 6)': [-1.265, -1.407, -0.117],
        'hc_cns_v1 (Cost-Normalized — Best)': [-0.399, -0.606, -0.190],
        'hc_knapsack_v1 (Knapsack)': [-0.501, -6.625, -0.100],
    }

    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)

    x = np.arange(len(projects))
    width = 0.2
    offsets = [-1.5, -0.5, 0.5, 1.5]
    palette = ['#8172B3', '#DD8452', '#4C72B0', '#55A868']

    for (name, vals), offset, color in zip(methods.items(), offsets, palette):
        rects = ax.bar(x + offset*width, vals, width, label=name, color=color, alpha=0.9)
        for rect in rects:
            h = rect.get_height()
            va = 'bottom' if h < 0 else 'top'
            ax.annotate(f'{h:+.2f}%', xy=(rect.get_x() + rect.get_width()/2, h),
                        xytext=(0, -8 if h < 0 else 3), textcoords="offset points",
                        ha='center', va=va, fontsize=7.5)

    # Threshold line (+3.0% pts)
    ax.axhline(3.0, color='red', linestyle='--', linewidth=1.5, label='Effect Gate Threshold (+3.0% pts)')
    ax.axhline(0.0, color='black', linestyle='-', linewidth=0.8, alpha=0.7)

    ax.set_ylabel('Median Paired Δ APFDc (% points)')
    ax.set_title('Figure 3: LRTS Effect Gate Evaluation vs History+cost (Phase 3)', fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(projects, fontweight='semibold')
    ax.set_ylim(-45, 6)
    ax.legend(frameon=True, loc='lower right', fontsize=8.5)

    plt.tight_layout()
    out_path = FIG_DIR / 'fig3_lrts_effect_gate.png'
    fig.savefig(out_path)
    plt.close(fig)
    print(f"Saved: {out_path}")


def plot_fig4_heavy_predecessors():
    """Fig 4: Heavy Predecessor Delay Seconds."""
    projects = ['Karaf', 'ActiveMQ', 'Log4j']
    added = [18205.5, 115759.2, 1027.2]
    removed = [23384.8, 71872.9, 635.0]
    net = [added[i] - removed[i] for i in range(3)]

    x = np.arange(len(projects))
    width = 0.3

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)
    ax.bar(x - width/2, [a/3600 for a in added], width, label='Added Predecessor Time (Hours)', color='#C44E52', alpha=0.85)
    ax.bar(x + width/2, [r/3600 for r in removed], width, label='Removed Predecessor Time (Hours)', color='#55A868', alpha=0.85)

    ax.set_ylabel('Cumulative Execution Delay (Hours)')
    ax.set_title('Figure 4: Heavy Predecessor Overhead Introduced by Semantic Selection', fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(projects, fontweight='semibold')
    ax.legend(frameon=True, loc='upper right')

    for i, p in enumerate(projects):
        net_h = net[i] / 3600
        sign = '+' if net_h > 0 else ''
        ax.annotate(f'Net: {sign}{net_h:.1f}h', xy=(x[i], max(added[i], removed[i])/3600),
                    xytext=(0, 6), textcoords="offset points", ha='center', va='bottom',
                    fontweight='bold', fontsize=9, color='#C44E52' if net_h > 0 else '#55A868')

    plt.tight_layout()
    out_path = FIG_DIR / 'fig4_heavy_predecessors.png'
    fig.savefig(out_path)
    plt.close(fig)
    print(f"Saved: {out_path}")


def main():
    print("Generating Topic 1 visualization figures...")
    plot_fig1_defects4j_reproduction()
    plot_fig2_chart_bridge()
    plot_fig3_lrts_effect_gate()
    plot_fig4_heavy_predecessors()
    print("All figures successfully generated in reports/figures/")


if __name__ == '__main__':
    main()
