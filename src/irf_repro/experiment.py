"""One experimental run = one (cores, trees, data fraction, seed) setting.

Methods (names follow the paper):
  Python-RFA : scikit-learn RandomForestClassifier, serial (n_jobs=1)
  Spark-RFA  : Spark MLlib RandomForestClassifier
  Spark-IRFA : Spark RF + sub-forest optimisation (filter, paths, similarity, selection)
"""
from __future__ import annotations

import math
import os
import time

import numpy as np

from . import spark_jobs as sj
from .config import append_csv_row
from .irf import majority_vote, select_trees

SWEEP_THRESHOLDS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]


def similarity_stats(sim):
    off = sim[~np.eye(sim.shape[0], dtype=bool)]
    nz = off[off > 0]
    return {"sim_zero_frac": float((off == 0).mean()) if off.size else "",
            "sim_nz_median": float(np.median(nz)) if nz.size else 0.0,
            "sim_nz_p90": float(np.percentile(nz, 90)) if nz.size else 0.0,
            "sim_max": float(off.max()) if off.size else 0.0}


def threshold_sweep(irf, n_classes, Xte, yte, base, out_csv):
    """Re-run Steps 5-6 for several similarityFilter values (the similarity matrix is reused)."""
    sub_idx = irf["sub_idx"]
    for th in SWEEP_THRESHOLDS:
        sel, groups = select_trees(irf["sim"], irf["val_acc"][sub_idx], th)
        keep = [irf["trees"][int(sub_idx[p])] for p in sel]
        acc = float((majority_vote(keep, Xte, n_classes) == yte).mean())
        append_csv_row(out_csv, {**base, "threshold": th, "n_subforest": len(sub_idx),
                                 "n_groups": len(groups), "final_trees": len(keep), "accuracy_hard_vote": acc})


def sklearn_rf(cfg, n_trees, seed, n_features):
    from sklearn.ensemble import RandomForestClassifier

    r = cfg["rf"]
    max_features = math.ceil(math.sqrt(n_features)) if r["feature_subset"] == "sqrt" else None
    return RandomForestClassifier(
        n_estimators=n_trees, criterion=r["impurity"], max_depth=r["max_depth"],
        max_features=max_features, min_samples_leaf=r["min_instances_per_node"],
        bootstrap=r["bootstrap"], n_jobs=1, random_state=seed,
    )


def run_setting(cfg, *, experiment, n_trees, seed, cores, fraction, methods, out_csv, spark=None, split="random"):
    own_spark = spark is None
    if own_spark:
        spark = sj.make_spark(cfg, cores=cores, app=f"{experiment}-t{n_trees}-c{cores}")
    try:
        splits, fcols = sj.load_splits(spark, cfg, fraction=fraction, seed=cfg["split"]["seed"], mode=split)
        n = {k: splits[k].count() for k in splits}
        raw_gb = (n["train"] + n["val"] + n["test"]) * cfg["data"]["window_length"] * 8 / 1e9
        base = {
            "experiment": experiment, "seed": seed, "cores": cores, "fraction": fraction,
            "raw_gb": round(raw_gb, 3), "n_train": n["train"], "n_val": n["val"], "n_test": n["test"],
            "n_trees": n_trees,
        }
        rows = []

        if "python" in methods:
            Xtr, ytr = sj.to_numpy(splits["train"], fcols)
            Xte, yte = sj.to_numpy(splits["test"], fcols)
            clf = sklearn_rf(cfg, n_trees, seed, len(fcols))
            t0 = time.perf_counter(); clf.fit(Xtr, ytr); fit_s = time.perf_counter() - t0
            t0 = time.perf_counter(); pred = clf.predict(Xte); diag_s = time.perf_counter() - t0
            from sklearn.metrics import accuracy_score, f1_score
            rows.append({**base, "method": "Python-RFA", "accuracy": accuracy_score(yte, pred),
                         "f1": f1_score(yte, pred, average="weighted"), "train_s": fit_s, "rf_fit_s": fit_s,
                         "irf_opt_s": 0.0, "diag_s": diag_s, "final_trees": n_trees, "n_subforest": "",
                         "engine": "sklearn", "export_agree": ""})

        if "spark" in methods or "irf" in methods:
            rf = sj.spark_rf(cfg, n_trees, seed)
            t0 = time.perf_counter(); rf_model = rf.fit(splits["train"]); rf_fit_s = time.perf_counter() - t0
            if "spark" in methods:
                diag_s, m = sj.timed_diagnosis(rf_model, splits["test"])
                rows.append({**base, "method": "Spark-RFA", "accuracy": m["accuracy"], "f1": m["f1"],
                             "train_s": rf_fit_s, "rf_fit_s": rf_fit_s, "irf_opt_s": 0.0, "diag_s": diag_s,
                             "final_trees": n_trees, "n_subforest": "", "engine": "mllib", "export_agree": ""})
            if "irf" in methods:
                work = os.path.join(cfg["paths"]["tmp_dir"], f"rf_{experiment}_{n_trees}_{cores}_{seed}_{os.getpid()}")
                irf = sj.fit_irf(spark, cfg, rf_model, splits, fcols, work)
                agree = ""
                if experiment == "E1":
                    Xchk, _ = sj.to_numpy(splits["val"].limit(2000), fcols)
                    agree = sj.verify_export(rf_model, irf["trees"], Xchk)
                    Xte_np, yte_np = sj.to_numpy(splits["test"], fcols)
                    sweep_csv = os.path.join(os.path.dirname(out_csv), "e1_threshold_sweep.csv")
                    threshold_sweep(irf, int(rf_model.numClasses), Xte_np, yte_np,
                                    {"seed": seed, "n_trees": n_trees}, sweep_csv)
                diag_s, m = sj.timed_diagnosis(irf["model"], splits["test"])
                tt = irf["timing"]
                rows.append({**base, "method": "Spark-IRFA", "accuracy": m["accuracy"], "f1": m["f1"],
                             "train_s": rf_fit_s + tt["optimisation_s"], "rf_fit_s": rf_fit_s,
                             "irf_opt_s": tt["optimisation_s"], "diag_s": diag_s,
                             "final_trees": irf["n_selected"], "n_subforest": irf["n_subforest"],
                             "engine": irf["engine"], "export_agree": agree,
                             "t_export_s": tt["export_s"], "t_filter_s": tt["filter_s"],
                             "t_paths_s": tt["paths_s"], "t_similarity_s": tt["similarity_s"],
                             "t_select_s": tt["select_s"], "n_groups": irf["n_groups"],
                             "mean_paths": irf["mean_paths"],
                             "val_acc_mean": float(np.mean(irf["val_acc"])),
                             "val_acc_min": float(np.min(irf["val_acc"])),
                             "val_acc_max": float(np.max(irf["val_acc"])),
                             **similarity_stats(irf["sim"])})

        cols = ["t_export_s", "t_filter_s", "t_paths_s", "t_similarity_s", "t_select_s", "n_groups",
                "mean_paths", "val_acc_mean", "val_acc_min", "val_acc_max",
                "sim_zero_frac", "sim_nz_median", "sim_nz_p90", "sim_max"]
        for r in rows:                                  # same columns in every row
            for c in cols:
                r.setdefault(c, "")
            append_csv_row(out_csv, r)
            print(f"[{experiment}] {r['method']:<11} trees={n_trees:<4} cores={cores} frac={fraction} "
                  f"acc={r['accuracy']:.4f} train={r['train_s']:.1f}s diag={r['diag_s']:.2f}s "
                  f"final_trees={r['final_trees']}", flush=True)
        for d in splits.values():
            d.unpersist()
        return rows
    finally:
        if own_spark:
            spark.stop()
