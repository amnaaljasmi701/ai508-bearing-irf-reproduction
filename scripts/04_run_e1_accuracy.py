"""E1 - accuracy of Python-RFA vs Spark-RFA vs Spark-IRFA on Dataset 1 for 20/100/200 trees."""
import _bootstrap  # noqa: F401
import argparse
import os

from _driver import launch
from irf_repro.config import load_config


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh", action="store_true", help="delete previous e1 results first")
    a = ap.parse_args()
    cfg = load_config()
    out = os.path.join(cfg["paths"]["results_dir"], "e1_accuracy.csv")
    if a.fresh and os.path.exists(out):
        os.remove(out)
    for seed in cfg["experiments"]["seeds"]:
        for trees in cfg["experiments"]["e1_trees"]:
            launch(experiment="E1", trees=trees, seed=seed, cores="*", fraction=1.0,
                   methods="python,spark,irf", out=out)


if __name__ == "__main__":
    main()
