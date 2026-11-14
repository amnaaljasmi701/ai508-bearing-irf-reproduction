"""Figures for the report and slides, built only from the CSV files in results/."""
import _bootstrap  # noqa: F401
import os

import pandas as pd

from irf_repro.config import load_config
from irf_repro.paper_values import PAPER

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

COL = {"Python-RFA": "#2a78d6", "Spark-RFA": "#eb6834", "Spark-IRFA": "#1baf7a", "paper": "#8a8984"}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False, "figure.dpi": 150,
    "lines.linewidth": 2, "lines.markersize": 7,
})


def mean_by(df, keys, cols):
    return df.groupby(keys, as_index=False)[cols].mean()


def save(fig, out_dir, name):
    fig.tight_layout()
    path = os.path.join(out_dir, name)
    fig.savefig(path)
    plt.close(fig)
    print("wrote", path)


def fig_e1(df, out):
    m = mean_by(df, ["method", "n_trees"], ["accuracy", "train_s", "diag_s", "final_trees"])
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    for meth in ["Python-RFA", "Spark-RFA", "Spark-IRFA"]:
        d = m[m.method == meth].sort_values("n_trees")
        if d.empty:
            continue
        ax.plot(d.n_trees, 100 * d.accuracy, marker="o", color=COL[meth], label=f"{meth} (ours)")
        p = PAPER["e1_accuracy"][meth]
        ax.plot(list(p.keys()), list(p.values()), marker="D", ls="--", lw=1.2, color=COL[meth], alpha=0.55,
                label=f"{meth} (paper)")
    ax.set_xlabel("Number of trees")
    ax.set_ylabel("Test accuracy (%)")
    ax.set_title("E1 - Diagnosis accuracy vs number of trees", loc="left", color=INK)
    ax.legend(ncol=2, fontsize=8, loc="lower right")
    save(fig, out, "e1_accuracy.png")

    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    width = 0.27
    trees = sorted(m.n_trees.unique())
    for k, meth in enumerate(["Python-RFA", "Spark-RFA", "Spark-IRFA"]):
        d = m[m.method == meth].set_index("n_trees").reindex(trees)
        xs = [i + (k - 1) * width for i in range(len(trees))]
        ax.bar(xs, d.diag_s, width=width - 0.03, color=COL[meth], label=meth)
    ax.set_xticks(range(len(trees)), [str(t) for t in trees])
    ax.set_xlabel("Number of trees")
    ax.set_ylabel("Diagnosis time on test set (s)")
    ax.set_title("E1 - Diagnosis time", loc="left", color=INK)
    ax.legend(fontsize=8)
    save(fig, out, "e1_diagnosis_time.png")


def fig_sweep(df, out):
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    m = mean_by(df, ["n_trees", "threshold"], ["final_trees", "accuracy_hard_vote"])
    palette = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
    for i, t in enumerate(sorted(m.n_trees.unique())):
        d = m[m.n_trees == t].sort_values("threshold")
        ax.plot(d.threshold, d.final_trees, marker="o", color=palette[i % 4], label=f"{t} trees")
    ax.set_xlabel("similarityFilter threshold")
    ax.set_ylabel("Trees kept in the IRF")
    ax.set_title("IRF size vs similarity threshold", loc="left", color=INK)
    ax.legend(fontsize=8)
    save(fig, out, "e1_threshold_sweep.png")


def fig_e2(df, out):
    m = mean_by(df, ["method", "cores"], ["train_s", "diag_s", "rf_fit_s", "irf_opt_s"])
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    for meth in ["Spark-RFA", "Spark-IRFA"]:
        d = m[m.method == meth].sort_values("cores")
        ax.plot(d.cores, d.train_s, marker="o", color=COL[meth], label=f"{meth} training")
    ax.set_xscale("log", base=2)
    ax.set_xticks(sorted(m.cores.unique()), [str(c) for c in sorted(m.cores.unique())])
    ax.set_xlabel("Spark executor cores (local[c])")
    ax.set_ylabel("Training time (s)")
    ax.set_title("E2 - Training time vs cores", loc="left", color=INK)
    ax.legend(fontsize=8)
    save(fig, out, "e2_training_time.png")

    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    d = m[m.method == "Spark-IRFA"].sort_values("cores")
    base = d.train_s.iloc[0]
    ax.plot(d.cores, 100 * (1 - d.train_s / base), marker="o", color=COL["Spark-IRFA"],
            label="Ours: reduction vs 1 core")
    p = PAPER["e2_train_reduction_nodes"]
    ax.plot(list(p.keys()), list(p.values()), marker="D", ls="--", color=COL["paper"],
            label="Paper: reduction vs 1 worker node")
    ax.set_xlabel("Cores (ours) / worker nodes (paper)")
    ax.set_ylabel("Training-time reduction (%)")
    ax.set_title("E2 - Spark-IRFA scalability compared with the paper", loc="left", color=INK)
    ax.legend(fontsize=8, loc="lower right")
    save(fig, out, "e2_reduction_vs_paper.png")


def fig_e3(df, out):
    m = mean_by(df, ["method", "raw_gb"], ["accuracy", "train_s"])
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.5))
    for meth in ["Spark-RFA", "Spark-IRFA"]:
        d = m[m.method == meth].sort_values("raw_gb")
        axes[0].plot(d.raw_gb, 100 * d.accuracy, marker="o", color=COL[meth], label=meth)
        axes[1].plot(d.raw_gb, d.train_s, marker="o", color=COL[meth], label=meth)
    axes[0].set_xlabel("Dataset size (GB, raw)")
    axes[0].set_ylabel("Test accuracy (%)")
    axes[0].set_title("E3 - Accuracy vs data size", loc="left", color=INK, fontsize=10)
    axes[1].set_xlabel("Dataset size (GB, raw)")
    axes[1].set_ylabel("Training time (s)")
    axes[1].set_title("E3 - Training time vs data size", loc="left", color=INK, fontsize=10)
    axes[0].legend(fontsize=8)
    save(fig, out, "e3_datasize.png")


def main():
    cfg = load_config()
    res, out = cfg["paths"]["results_dir"], cfg["paths"]["figures_dir"]
    jobs = [("e1_accuracy.csv", fig_e1), ("e1_threshold_sweep.csv", fig_sweep),
            ("e2_scalability.csv", fig_e2), ("e3_datasize.csv", fig_e3)]
    for name, fn in jobs:
        path = os.path.join(res, name)
        if os.path.exists(path):
            fn(pd.read_csv(path), out)
        else:
            print("missing", path, "- figure skipped")


if __name__ == "__main__":
    main()
