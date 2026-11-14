"""Run one experimental setting in a fresh Spark JVM (used by the E1/E2/E3 drivers)."""
import _bootstrap  # noqa: F401
import argparse

from irf_repro.config import load_config
from irf_repro.experiment import run_setting


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiment", required=True)
    ap.add_argument("--trees", type=int, required=True)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--cores", default="*")
    ap.add_argument("--fraction", type=float, default=1.0)
    ap.add_argument("--methods", default="python,spark,irf")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cfg = load_config()
    run_setting(cfg, experiment=a.experiment, n_trees=a.trees, seed=a.seed, cores=a.cores,
                fraction=a.fraction, methods=a.methods.split(","), out_csv=a.out)


if __name__ == "__main__":
    main()
