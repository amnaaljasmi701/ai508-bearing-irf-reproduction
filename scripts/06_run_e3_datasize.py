"""E3 - accuracy and training time of Spark-RFA / Spark-IRFA on 1.4, 2.8 and 5.6 GB subsets."""
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
    ex = cfg["experiments"]
    out = os.path.join(cfg["paths"]["results_dir"], "e3_datasize.csv")
    if a.fresh and os.path.exists(out):
        os.remove(out)
    for seed in ex["seeds"]:
        for frac in ex["e3_fractions"]:
            launch(experiment="E3", trees=ex["e3_trees"], seed=seed, cores="*", fraction=frac,
                   methods="spark,irf", out=out)


if __name__ == "__main__":
    main()
