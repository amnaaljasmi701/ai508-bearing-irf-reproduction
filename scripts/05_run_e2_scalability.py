"""E2 - training/diagnosis time of Spark-RFA and Spark-IRFA with 1, 2, 4, 8 executor cores.

local[c] runs Spark with c task slots in one JVM; it is used as a single-machine proxy for the
paper's 1-4 worker nodes.  Core counts above os.cpu_count() are skipped.
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
    ex = cfg["experiments"]
    out = os.path.join(cfg["paths"]["results_dir"], "e2_scalability.csv")
    if a.fresh and os.path.exists(out):
        os.remove(out)
    for rep in range(ex["e2_repeats"]):
        for cores in ex["e2_cores"]:
            if cores > (os.cpu_count() or 1):
                print(f"skipping {cores} cores (only {os.cpu_count()} available)")
                continue
            launch(experiment="E2", trees=ex["e2_trees"], seed=ex["seeds"][0] + rep, cores=cores,
                   fraction=1.0, methods="spark,irf", out=out)


if __name__ == "__main__":
    main()
