"""Spark side of the reproduction: session, data loading, Spark RF, Spark IRF, diagnosis."""
from __future__ import annotations

import math
import os
import shutil
import time

import numpy as np

from .irf import filter_trees, majority_vote, select_trees, similarity_row
from .trees import export_spark_forest, extract_paths

FEATURE_PREFIX = "f"


# --------------------------------------------------------------------------- session
def make_spark(cfg: dict, cores: int | str = "*", app: str = "irf-repro"):
    from pyspark.sql import SparkSession

    sc_cfg = cfg["spark"]
    n_cores = os.cpu_count() if cores == "*" else int(cores)
    builder = (
        SparkSession.builder.appName(app)
        .master(f"local[{cores}]")
        .config("spark.driver.memory", sc_cfg["driver_memory"])
        .config("spark.sql.shuffle.partitions", str(max(4, 2 * n_cores)))
        .config("spark.sql.execution.arrow.pyspark.enabled", "true")
        .config("spark.sql.execution.arrow.maxRecordsPerBatch", str(sc_cfg["arrow_batch"]))
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.local.dir", cfg["paths"]["tmp_dir"])
    )
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    return spark


# --------------------------------------------------------------------------- data
def feature_columns(df) -> list[str]:
    cols = [c for c in df.columns if c.startswith(FEATURE_PREFIX) and c[1:].isdigit()]
    return sorted(cols, key=lambda c: int(c[1:]))


def load_splits(spark, cfg: dict, fraction: float = 1.0, seed: int | None = None):
    """Read the feature table, assign a deterministic 6:2:2 split and return cached DataFrames.

    The split is a hash of (file_id, win_idx, seed), so Spark and scikit-learn see exactly the
    same rows, and the subsets used in E3 are nested (1.4 GB subset is inside 2.8 GB subset).
    """
    from pyspark.ml.feature import VectorAssembler
    from pyspark.sql import functions as F

    seed = cfg["split"]["seed"] if seed is None else seed
    df = spark.read.parquet(cfg["paths"]["features"])
    if fraction < 1.0:
        h = F.pmod(F.xxhash64("file_id", "win_idx", F.lit(10_000 + seed)), F.lit(100_000))
        df = df.where(h < F.lit(int(round(fraction * 100_000))))
    bucket = F.pmod(F.xxhash64("file_id", "win_idx", F.lit(seed)), F.lit(100)).cast("int")
    tr = int(round(cfg["split"]["train"] * 100))
    va = int(round((cfg["split"]["train"] + cfg["split"]["validation"]) * 100))
    df = df.withColumn("split", F.when(bucket < tr, "train").when(bucket < va, "val").otherwise("test"))
    fcols = feature_columns(df)
    df = VectorAssembler(inputCols=fcols, outputCol="features").transform(df)
    df = df.withColumn("label", F.col("label").cast("double"))
    parts = cfg["spark"]["num_partitions"]
    out = {}
    for name in ("train", "val", "test"):
        d = df.where(F.col("split") == name).select("label", "features", *fcols).repartition(parts).cache()
        d.count()                                   # materialise the cache before any timing
        out[name] = d
    return out, fcols


def to_numpy(df, fcols):
    pdf = df.select("label", *fcols).toPandas()
    return pdf[fcols].to_numpy(dtype=np.float64), pdf["label"].to_numpy(dtype=np.float64)


# --------------------------------------------------------------------------- models
def spark_rf(cfg: dict, n_trees: int, seed: int):
    from pyspark.ml.classification import RandomForestClassifier

    r = cfg["rf"]
    return RandomForestClassifier(
        featuresCol="features", labelCol="label", numTrees=n_trees, impurity=r["impurity"],
        maxDepth=r["max_depth"], maxBins=r["max_bins"], minInstancesPerNode=r["min_instances_per_node"],
        featureSubsetStrategy=r["feature_subset"], subsamplingRate=r["subsampling_rate"],
        bootstrap=r["bootstrap"], seed=seed,
    )


def evaluate_accuracy(pred_df) -> dict:
    from pyspark.ml.evaluation import MulticlassClassificationEvaluator

    acc = MulticlassClassificationEvaluator(labelCol="label", predictionCol="prediction", metricName="accuracy")
    f1 = MulticlassClassificationEvaluator(labelCol="label", predictionCol="prediction", metricName="f1")
    return {"accuracy": acc.evaluate(pred_df), "f1": f1.evaluate(pred_df)}


def timed_diagnosis(model, test_df) -> tuple[float, dict]:
    """Diagnosis time = time to predict every test sample and compute accuracy."""
    t0 = time.perf_counter()
    metrics = evaluate_accuracy(model.transform(test_df))
    return time.perf_counter() - t0, metrics


# --------------------------------------------------------------------------- IRF on Spark
def per_tree_accuracy(spark, trees, val_df, fcols) -> np.ndarray:
    """Step 2 in parallel: every partition of the validation RDD scores all broadcast trees."""
    import pandas as pd
    from pyspark.sql.types import LongType, StructField, StructType

    b_trees = spark.sparkContext.broadcast(trees)
    k = len(trees)

    def score(batches):
        local = b_trees.value
        for pdf in batches:
            X = pdf[fcols].to_numpy(dtype=np.float64)
            y = pdf["label"].to_numpy(dtype=np.float64)
            correct = [int((t.predict(X) == y).sum()) for t in local]
            yield pd.DataFrame({"tree": np.arange(k, dtype=np.int64), "correct": correct,
                                "n": np.full(k, len(y), dtype=np.int64)})

    schema = StructType([StructField("tree", LongType()), StructField("correct", LongType()),
                         StructField("n", LongType())])
    agg = (val_df.select("label", *fcols).mapInPandas(score, schema)
           .groupBy("tree").sum("correct", "n").toPandas().sort_values("tree"))
    b_trees.unpersist()
    return (agg["sum(correct)"] / agg["sum(n)"]).to_numpy()


def similarity_matrix(spark, paths, alpha: float) -> np.ndarray:
    """Step 4 in parallel: one task per row a computes treeSim(a, b) for every b."""
    b_paths = spark.sparkContext.broadcast(paths)
    w = len(paths)
    rows = (spark.sparkContext.parallelize(range(w), numSlices=min(w, 4 * (os.cpu_count() or 1)))
            .map(lambda a: (a, similarity_row(a, b_paths.value, alpha)))
            .collect())
    b_paths.unpersist()
    sim = np.zeros((w, w))
    for a, row in rows:
        sim[a] = row
    return sim


def build_submodel(spark, rf_model, keep_idx):
    """Rebuild an MLlib RandomForestClassificationModel that holds only the kept trees."""
    from pyspark.ml.classification import RandomForestClassificationModel

    jvm = spark.sparkContext._jvm
    gw = spark.sparkContext._gateway
    jtrees = rf_model._java_obj.trees()
    dt_cls = jvm.org.apache.spark.ml.classification.DecisionTreeClassificationModel
    arr = gw.new_array(dt_cls, len(keep_idx))
    for k, i in enumerate(keep_idx):
        arr[k] = jtrees[int(i)]
    uid = f"irf_{rf_model.uid}"
    jmodel = jvm.org.apache.spark.ml.classification.RandomForestClassificationModel(
        uid, arr, int(rf_model.numFeatures), int(rf_model.numClasses))
    try:
        from pyspark.ml.wrapper import JavaParams

        return JavaParams._from_java(jmodel)        # copies the Java params to the Python wrapper
    except Exception:
        return RandomForestClassificationModel(jmodel)


class PythonVoteModel:
    """IRF diagnosis with hard majority voting of broadcast FlatTrees (engine = python)."""

    def __init__(self, spark, trees, fcols, n_classes):
        self.spark, self.trees, self.fcols, self.n_classes = spark, trees, fcols, n_classes

    def transform(self, df):
        import pandas as pd
        from pyspark.sql.types import DoubleType, StructField, StructType

        b = self.spark.sparkContext.broadcast(self.trees)
        fcols, n_classes = self.fcols, self.n_classes

        def predict(batches):
            for pdf in batches:
                X = pdf[fcols].to_numpy(dtype=np.float64)
                yield pd.DataFrame({"label": pdf["label"].to_numpy(dtype=np.float64),
                                    "prediction": majority_vote(b.value, X, n_classes)})

        schema = StructType([StructField("label", DoubleType()), StructField("prediction", DoubleType())])
        return df.select("label", *fcols).mapInPandas(predict, schema)


def verify_export(rf_model, trees, X, n_check: int = 3) -> float:
    """Agreement between Spark's own tree predictions and the exported FlatTrees (should be 1.0)."""
    from pyspark.ml.linalg import Vectors
    from pyspark.sql import SparkSession

    spark = SparkSession.getActiveSession()
    Xs = X[:2000]
    sdf = spark.createDataFrame([(Vectors.dense([float(v) for v in r]),) for r in Xs], ["features"])
    agree = []
    for i in range(min(n_check, len(trees))):
        sp = np.array([r.prediction for r in rf_model.trees[i].transform(sdf).select("prediction").collect()])
        agree.append(float((sp == trees[i].predict(Xs)).mean()))
    return float(np.mean(agree))


def fit_irf(spark, cfg: dict, rf_model, splits, fcols, workdir: str) -> dict:
    """Run Steps 2-7 on a trained Spark RF. Returns the IRF model and timing breakdown."""
    icfg = cfg["irf"]
    t = {}
    t0 = time.perf_counter()
    trees = export_spark_forest(spark, rf_model, workdir)
    t["export_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    val_acc = per_tree_accuracy(spark, trees, splits["val"], fcols)
    sub_idx = filter_trees(val_acc, icfg["filter_rule"])
    t["filter_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    sub_trees = [trees[i] for i in sub_idx]
    paths = spark.sparkContext.parallelize(sub_trees, numSlices=max(1, min(len(sub_trees), 64))).map(extract_paths).collect()
    t["paths_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    sim = similarity_matrix(spark, paths, icfg["alpha"])
    t["similarity_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    sel_pos, groups = select_trees(sim, val_acc[sub_idx], icfg["similarity_threshold"])
    keep_idx = [int(sub_idx[p]) for p in sel_pos]
    engine = icfg["engine"]
    model = None
    if engine == "jvm":
        try:
            model = build_submodel(spark, rf_model, keep_idx)
        except Exception as exc:                     # pragma: no cover - depends on Spark build
            print(f"[IRF] JVM sub-model failed ({exc!r}); falling back to python voting")
            engine = "python"
    if model is None:
        n_classes = int(rf_model.numClasses)
        model = PythonVoteModel(spark, [trees[i] for i in keep_idx], fcols, n_classes)
    t["select_s"] = time.perf_counter() - t0
    t["optimisation_s"] = sum(t[k] for k in ("export_s", "filter_s", "paths_s", "similarity_s", "select_s"))
    shutil.rmtree(workdir, ignore_errors=True)
    return {
        "model": model, "engine": engine, "keep_idx": keep_idx, "n_subforest": int(len(sub_idx)), "sub_idx": sub_idx,
        "n_groups": len(groups), "n_selected": len(keep_idx), "val_acc": val_acc, "sim": sim,
        "trees": trees, "timing": t,
        "mean_paths": float(np.mean([len(p[2]) for p in paths])) if paths else math.nan,
    }
