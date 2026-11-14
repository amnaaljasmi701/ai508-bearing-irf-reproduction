"""E1b (supplementary) - E1 repeated with a time-blocked split to check the effect of overlap leakage.

With up to 99 % overlap, a random split puts near-copies of test windows into the training set.
Here every signal is split by time (60 / 20 / 20 %), with a gap at each boundary.
"""
import _bootstrap  # noqa: F401
import argparse
import os

from _driver import launch
from irf_repro.config import load_config


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh", action="store_true")
    a = ap.parse_args()
    cfg = load_config()
    out = os.path.join(cfg["paths"]["results_dir"], "e1b_blocked.csv")
    if a.fresh and os.path.exists(out):
        os.remove(out)
    for seed in cfg["experiments"]["seeds"]:
        for trees in cfg["experiments"]["e1_trees"]:
            launch(experiment="E1b", trees=trees, seed=seed, cores="*", fraction=1.0,
                   methods="python,spark,irf", out=out, split="blocked")


if __name__ == "__main__":
    main()
