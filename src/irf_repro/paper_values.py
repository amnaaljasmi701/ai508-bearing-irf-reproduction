"""Results reported by Wan et al. (2021), used only for comparison tables and figures."""

PAPER = {
    # Accuracy (%) vs number of trees (Section V, sweep 20 -> 200 trees)
    "e1_accuracy": {
        "Python-RFA": {20: 95.85, 200: 96.43},
        "Spark-RFA": {20: 95.69, 200: 96.51},
        "Spark-IRFA": {20: 95.66, 200: 97.22},
    },
    # Spark-IRFA accuracy (%) with 100 trees vs dataset size (GB)
    "e3_irf_accuracy": {5.6: 97.09, 11.2: 97.38, 20.4: 98.12},
    # Spark-IRFA training-time reduction (%) vs one worker node
    "e2_train_reduction_nodes": {1: 0.0, 2: 51.48, 3: 66.08, 4: 73.26},
    # Spark-IRFA diagnosis-time reduction (%) vs Spark-RFA, datasets 1-3
    "diag_reduction_irf_vs_rf": {5.6: 74.29, 11.2: 76.00, 20.4: 78.01},
    # Spark-IRFA training time higher than Spark-RFA (%), 4 workers, datasets 1-3
    "train_overhead_irf_vs_rf": {5.6: 85.98, 11.2: 40.01, 20.4: 29.99},
    # Diagnosis time on dataset 3 (minutes)
    "diag_min_d3": {"Python-RFA": 24.3, "Spark-IRFA": 3.1},
    "claimed_speedup_vs_python": 6.84,
    "claimed_speedup_vs_spark_rf": 3.55,
}
