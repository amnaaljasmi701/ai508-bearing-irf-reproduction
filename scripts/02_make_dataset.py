"""Enlarge the CWRU data by overlapping sampling (Spark job) -> data/windows.parquet.

Each of the 40 signals is cut into the same number of overlapping windows of length L,
with evenly spaced start points, so that the raw dataset (float64) reaches target_gb.
Windows are written as binary float64 blobs: n_windows x L x 8 bytes ~= target_gb.
"""
import _bootstrap  # noqa: F401
import argparse
import os
import time

import numpy as np

from irf_repro.config import load_config, save_json
from irf_repro.cwru import file_table, load_de_signal, window_starts, windows_per_file
from irf_repro.spark_jobs import make_spark


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-gb", type=float, default=None)
    ap.add_argument("--cores", default="*")
    args = ap.parse_args()
    cfg = load_config()
    d = cfg["data"]
    target = args.target_gb or d["target_gb"]
    L = d["window_length"]

    files = file_table(d["loads_hp"])
    signals = {}
    for row in files:
        sig = load_de_signal(os.path.join(cfg["paths"]["raw_mat_dir"], f"{row['file_id']}.mat"), row["file_id"])
        if row["label"] == 0 and d["normal_downsample_factor"] > 1:
            sig = sig[:: d["normal_downsample_factor"]]
        signals[row["file_id"]] = sig
    n_per_file = windows_per_file(target, L, len(files))
    min_len = min(s.size for s in signals.values())
    max_step = (min_len - L) / max(1, n_per_file - 1)
    print(f"{n_per_file} windows per file, L={L}, smallest step={max_step:.2f} samples "
          f"(overlap {100 * (1 - max_step / L):.2f}%)")

    import pandas as pd
    from pyspark.sql.types import BinaryType, DoubleType, IntegerType, StructField, StructType

    spark = make_spark(cfg, cores=args.cores, app="make-dataset")
    b_sig = spark.sparkContext.broadcast(signals)
    chunk = d["chunk_windows"]
    tasks = []
    for row in files:
        for c0 in range(0, n_per_file, chunk):
            tasks.append((row["file_id"], row["label"], row["load"], c0, min(chunk, n_per_file - c0)))
    task_df = spark.createDataFrame(pd.DataFrame(tasks, columns=["file_id", "label", "load", "c0", "cn"]))
    task_df = task_df.repartition(len(tasks))

    def make_windows(batches):
        sigs = b_sig.value
        for pdf in batches:
            for r in pdf.itertuples(index=False):
                s = sigs[int(r.file_id)]
                starts = window_starts(s.size, L, n_per_file)[int(r.c0): int(r.c0) + int(r.cn)]
                idx = np.arange(int(r.c0), int(r.c0) + int(r.cn))
                blobs = [s[st: st + L].astype(np.float64).tobytes() for st in starts]
                yield pd.DataFrame({
                    "file_id": np.full(len(idx), r.file_id, dtype=np.int32),
                    "label": np.full(len(idx), r.label, dtype=np.int32),
                    "load": np.full(len(idx), r.load, dtype=np.int32),
                    "win_idx": idx.astype(np.int32),
                    "pos": starts / max(1, s.size - L),
                    "signal": blobs,
                })

    schema = StructType([
        StructField("file_id", IntegerType()), StructField("label", IntegerType()),
        StructField("load", IntegerType()), StructField("win_idx", IntegerType()),
        StructField("pos", DoubleType()), StructField("signal", BinaryType()),
    ])
    t0 = time.perf_counter()
    task_df.mapInPandas(make_windows, schema).write.mode("overwrite").parquet(cfg["paths"]["raw_windows"])
    elapsed = time.perf_counter() - t0
    n_rows = spark.read.parquet(cfg["paths"]["raw_windows"]).count()
    disk = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(cfg["paths"]["raw_windows"]) for f in fs)
    summary = {
        "n_files": len(files), "windows_per_file": n_per_file, "window_length": L,
        "n_windows": n_rows, "raw_gb": n_rows * L * 8 / 1e9, "parquet_gb_on_disk": disk / 1e9,
        "min_step_samples": max_step, "max_overlap_pct": 100 * (1 - max_step / L),
        "signal_lengths": {str(k): int(v.size) for k, v in signals.items()},
        "generation_s": elapsed, "cores": args.cores,
    }
    save_json(summary, os.path.join(cfg["paths"]["results_dir"], "dataset_summary.json"))
    print(f"wrote {n_rows} windows = {summary['raw_gb']:.2f} GB raw "
          f"({summary['parquet_gb_on_disk']:.2f} GB parquet) in {elapsed:.1f}s")
    spark.stop()


if __name__ == "__main__":
    main()
