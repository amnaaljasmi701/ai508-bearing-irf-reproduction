"""Wavelet-packet feature extraction over the enlarged dataset (Spark job) -> data/features.parquet."""
import _bootstrap  # noqa: F401
import argparse
import os
import time

import numpy as np

from irf_repro.config import load_config, load_json, save_json
from irf_repro.spark_jobs import make_spark
from irf_repro.wpd import wpd_energy_features


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cores", default="*")
    args = ap.parse_args()
    cfg = load_config()
    fc = cfg["features"]
    L = cfg["data"]["window_length"]
    n_feat = 2 ** fc["level"]

    import pandas as pd
    from pyspark.sql.types import DoubleType, IntegerType, StructField, StructType

    spark = make_spark(cfg, cores=args.cores, app="extract-features")
    raw = spark.read.parquet(cfg["paths"]["raw_windows"])

    def featurise(batches):
        for pdf in batches:
            X = np.frombuffer(b"".join(pdf["signal"].values), dtype=np.float64).reshape(len(pdf), L)
            F = wpd_energy_features(X, fc["wavelet"], fc["level"], fc["mode"], fc["standardize"])
            out = pdf[["file_id", "label", "load", "win_idx", "pos"]].reset_index(drop=True)
            for k in range(n_feat):
                out[f"f{k}"] = F[:, k]
            yield out

    schema = StructType(
        [StructField("file_id", IntegerType()), StructField("label", IntegerType()),
         StructField("load", IntegerType()), StructField("win_idx", IntegerType()),
         StructField("pos", DoubleType())]
        + [StructField(f"f{k}", DoubleType()) for k in range(n_feat)]
    )
    t0 = time.perf_counter()
    raw.mapInPandas(featurise, schema).write.mode("overwrite").parquet(cfg["paths"]["features"])
    elapsed = time.perf_counter() - t0
    feats = spark.read.parquet(cfg["paths"]["features"])
    n = feats.count()
    per_class = {int(r["label"]): int(r["count"]) for r in feats.groupBy("label").count().collect()}
    path = os.path.join(cfg["paths"]["results_dir"], "dataset_summary.json")
    summary = load_json(path) if os.path.exists(path) else {}
    summary.update({"n_feature_rows": n, "n_features": n_feat, "wavelet": fc["wavelet"], "level": fc["level"],
                    "feature_extraction_s": elapsed, "rows_per_class": per_class})
    save_json(summary, path)
    print(f"{n} feature vectors ({n_feat} features) in {elapsed:.1f}s; per class: {per_class}")
    spark.stop()


if __name__ == "__main__":
    main()
