"""Turn the result CSV/JSON files into the {{TOKEN}} values used by the report and slides.

Every number in the generated report comes from results/*.csv or results/*.json.
A token whose experiment has not been run is rendered as an en dash.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from .config import load_json
from .paper_values import PAPER

DASH = "–"
TREES = (20, 100, 200)
CORES = (1, 2, 3, 4)
FRACS = (0.25, 0.5, 1.0)
THRESH = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
MKEY = {"Python-RFA": "PY", "Spark-RFA": "RF", "Spark-IRFA": "IRF"}


def pct(x, nd=2):
    return DASH if x is None or (isinstance(x, float) and np.isnan(x)) else f"{100 * x:.{nd}f}"


def num(x, nd=1):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return DASH
    return f"{x:.{nd}f}" if abs(x) < 1000 else f"{x:,.0f}"


def secs(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return DASH
    return f"{x:.2f}" if x < 10 else f"{x:.1f}"


def signed_pp(x):
    return DASH if x is None or np.isnan(x) else f"{100 * x:+.2f}"


def compare(a, b, tol=0.0005):
    if a is None or b is None or np.isnan(a) or np.isnan(b):
        return "not measured against"
    if abs(a - b) <= tol:
        return "practically equal to"
    return "higher than" if a > b else "lower than"


def _read(path):
    return pd.read_csv(path) if os.path.exists(path) else None


def _get(df, **kw):
    if df is None:
        return pd.DataFrame()
    m = np.ones(len(df), dtype=bool)
    for k, v in kw.items():
        col = df[k]
        m &= np.isclose(col.astype(float), float(v)) if not isinstance(v, str) else (col == v)
    return df[m]


def _mean(d, col):
    if d.empty or col not in d or d[col].isna().all():
        return np.nan
    return float(pd.to_numeric(d[col], errors="coerce").mean())


def build_values(cfg: dict) -> dict:
    res = cfg["paths"]["results_dir"]
    V = {}
    rep = cfg.get("report", {})
    V["AUTHOR"] = rep.get("author", "[Name]")
    V["STUDENT_ID"] = rep.get("student_id", "[ID]")
    V["GITHUB_URL"] = rep.get("github_url", DASH)

    # ---------------------------------------------------------------- environment
    env_p = os.path.join(res, "environment.json")
    env = load_json(env_p) if os.path.exists(env_p) else {}
    for k, key in [("CPU", "cpu"), ("CORES", "logical_cores"), ("RAM", "ram_gb_visible"), ("OS", "os"),
                   ("PY", "python"), ("JAVA", "java"), ("SPARK", "spark_runtime"), ("SKLEARN", "sklearn"),
                   ("NUMPY", "numpy"), ("PANDAS", "pandas"), ("PYARROW", "pyarrow"), ("PYWT", "pywt"),
                   ("SCIPY", "scipy")]:
        V[f"ENV_{k}"] = str(env.get(key, DASH))
    V["ENV_DRIVER_MEM"] = cfg["spark"]["driver_memory"]

    # ---------------------------------------------------------------- dataset
    ds_p = os.path.join(res, "dataset_summary.json")
    ds = load_json(ds_p) if os.path.exists(ds_p) else {}
    V["N_WINDOWS"] = f"{ds['n_windows']:,}" if "n_windows" in ds else DASH
    V["WPF"] = f"{ds['windows_per_file']:,}" if "windows_per_file" in ds else DASH
    V["RAW_GB"] = num(ds.get("raw_gb", np.nan), 2)
    V["PARQUET_GB"] = num(ds.get("parquet_gb_on_disk", np.nan), 2)
    V["OVERLAP_PCT"] = num(ds.get("max_overlap_pct", np.nan), 2)
    V["MIN_STEP"] = num(ds.get("min_step_samples", np.nan), 1)
    V["GEN_S"] = secs(ds.get("generation_s", np.nan))
    V["FEAT_S"] = secs(ds.get("feature_extraction_s", np.nan))
    V["N_FEATURES"] = str(ds.get("n_features", 2 ** cfg["features"]["level"]))
    lengths = list(ds.get("signal_lengths", {}).values())
    V["SIG_MIN"] = f"{min(lengths):,}" if lengths else DASH
    V["SIG_MAX"] = f"{max(lengths):,}" if lengths else DASH

    # ---------------------------------------------------------------- E1
    e1 = _read(os.path.join(res, "e1_accuracy.csv"))
    V["NSEEDS"] = str(e1["seed"].nunique()) if e1 is not None else DASH
    any_row = e1.iloc[0] if e1 is not None and len(e1) else None
    V["N_TRAIN"] = f"{int(any_row.n_train):,}" if any_row is not None else DASH
    V["N_VAL"] = f"{int(any_row.n_val):,}" if any_row is not None else DASH
    V["N_TEST"] = f"{int(any_row.n_test):,}" if any_row is not None else DASH
    acc = {}
    for t in TREES:
        for meth, k in MKEY.items():
            d = _get(e1, method=meth, n_trees=t)
            a = _mean(d, "accuracy")
            acc[(k, t)] = a
            V[f"E1_{k}_{t}_ACC"] = pct(a)
            V[f"E1_{k}_{t}_F1"] = pct(_mean(d, "f1"))
            V[f"E1_{k}_{t}_TRAIN"] = secs(_mean(d, "train_s"))
            V[f"E1_{k}_{t}_DIAG"] = secs(_mean(d, "diag_s"))
        d = _get(e1, method="Spark-IRFA", n_trees=t)
        V[f"E1_IRF_{t}_NTREES"] = num(_mean(d, "final_trees"), 0)
        V[f"E1_IRF_{t}_SUB"] = num(_mean(d, "n_subforest"), 0)
        V[f"E1_IRF_{t}_OPT"] = secs(_mean(d, "irf_opt_s"))
        V[f"E1_IRF_{t}_SIM"] = secs(_mean(d, "t_similarity_s"))
        V[f"E1_IRF_{t}_PATHS"] = num(_mean(d, "mean_paths"), 0)
        V[f"E1_D_IRF_RF_{t}"] = signed_pp(acc[("IRF", t)] - acc[("RF", t)])
        V[f"E1_D_RF_PY_{t}"] = signed_pp(acc[("RF", t)] - acc[("PY", t)])
        rf_d = _mean(_get(e1, method="Spark-RFA", n_trees=t), "diag_s")
        irf_d = _mean(d, "diag_s")
        V[f"E1_DIAGRED_{t}"] = pct(1 - irf_d / rf_d, 1) if rf_d and not np.isnan(rf_d) else DASH
        py_d = _mean(_get(e1, method="Python-RFA", n_trees=t), "diag_s")
        V[f"E1_SPEEDUP_PY_{t}"] = num(py_d / irf_d, 2) if irf_d and not np.isnan(irf_d) else DASH
        V[f"E1_SPEEDUP_RF_{t}"] = num(rf_d / irf_d, 2) if irf_d and not np.isnan(irf_d) else DASH
        for c in ("sim_zero_frac", "sim_nz_median", "sim_nz_p90", "sim_max", "val_acc_min", "val_acc_max",
                  "val_acc_mean"):
            x = _mean(d, c)
            V[f"E1_{c.upper()}_{t}"] = pct(x, 1) if c == "sim_zero_frac" or c.startswith("val") else num(x, 3)
        for k in MKEY.values():
            p = PAPER["e1_accuracy"][{v: kk for kk, v in MKEY.items()}[k]]
            if t in p:
                V[f"E1_GAP_{k}_{t}"] = (DASH if np.isnan(acc[(k, t)]) else f"{100 * acc[(k, t)] - p[t]:+.2f}")
    agree = _mean(_get(e1, method="Spark-IRFA"), "export_agree") if e1 is not None else np.nan
    V["E1_AGREE"] = pct(agree, 1)
    V["E1_VERDICT_200"] = compare(acc[("IRF", 200)], acc[("RF", 200)])
    V["E1_VERDICT_100"] = compare(acc[("IRF", 100)], acc[("RF", 100)])
    V["E1_VERDICT_20"] = compare(acc[("IRF", 20)], acc[("RF", 20)])
    V["E1_VERDICT_PY_200"] = compare(acc[("RF", 200)], acc[("PY", 200)])
    wins = sum(1 for t in TREES if not np.isnan(acc[("IRF", t)]) and acc[("IRF", t)] > acc[("RF", t)] + 0.0005)
    V["E1_IRF_WINS"] = str(wins)
    rf_trend = [acc[("RF", t)] for t in TREES]
    V["E1_RF_GAIN_TREES"] = signed_pp(rf_trend[-1] - rf_trend[0])
    V["E1_IRF_GAIN_TREES"] = signed_pp(acc[("IRF", 200)] - acc[("IRF", 20)])

    # ---------------------------------------------------------------- threshold sweep
    sw = _read(os.path.join(res, "e1_threshold_sweep.csv"))
    for th in THRESH:
        d = _get(sw, n_trees=100, threshold=th)
        V[f"SW_N_{int(th * 10)}"] = num(_mean(d, "final_trees"), 0)
        V[f"SW_G_{int(th * 10)}"] = num(_mean(d, "n_groups"), 0)
        V[f"SW_A_{int(th * 10)}"] = pct(_mean(d, "accuracy_hard_vote"))
    V["SW_SUB"] = num(_mean(_get(sw, n_trees=100), "n_subforest"), 0)
    V["IRF_THRESHOLD"] = str(cfg["irf"]["similarity_threshold"])

    # ---------------------------------------------------------------- E2
    e2 = _read(os.path.join(res, "e2_scalability.csv"))
    base_irf = _mean(_get(e2, method="Spark-IRFA", cores=1), "train_s")
    base_rf = _mean(_get(e2, method="Spark-RFA", cores=1), "train_s")
    ran = sorted(int(c) for c in e2["cores"].unique()) if e2 is not None else []
    V["E2_MAXC"] = str(max(ran)) if ran else DASH
    irf_times = []
    for c in CORES:
        rf = _get(e2, method="Spark-RFA", cores=c)
        ir = _get(e2, method="Spark-IRFA", cores=c)
        t_rf, t_ir = _mean(rf, "train_s"), _mean(ir, "train_s")
        if not np.isnan(t_ir):
            irf_times.append(t_ir)
        V[f"E2_RF_TRAIN_{c}"] = secs(t_rf)
        V[f"E2_IRF_TRAIN_{c}"] = secs(t_ir)
        V[f"E2_IRF_OPT_{c}"] = secs(_mean(ir, "irf_opt_s"))
        V[f"E2_RF_DIAG_{c}"] = secs(_mean(rf, "diag_s"))
        V[f"E2_IRF_DIAG_{c}"] = secs(_mean(ir, "diag_s"))
        V[f"E2_RED_{c}"] = pct(1 - t_ir / base_irf, 1) if base_irf and not np.isnan(t_ir) else DASH
        V[f"E2_RFRED_{c}"] = pct(1 - t_rf / base_rf, 1) if base_rf and not np.isnan(t_rf) else DASH
        V[f"E2_SPEEDUP_{c}"] = num(base_irf / t_ir, 2) if t_ir and not np.isnan(t_ir) else DASH
        V[f"E2_EFF_{c}"] = pct(base_irf / t_ir / c, 0) if t_ir and not np.isnan(t_ir) else DASH
    if len(irf_times) >= 2:
        mono = all(b < a for a, b in zip(irf_times, irf_times[1:]))
        V["E2_TREND"] = ("decreased monotonically" if mono else
                         "decreased overall but not monotonically" if irf_times[-1] < irf_times[0] else
                         "did not decrease")
    else:
        V["E2_TREND"] = "could not be assessed"
    mc = max(ran) if ran else None
    if mc:
        t_rf = _mean(_get(e2, method="Spark-RFA", cores=mc), "train_s")
        t_ir = _mean(_get(e2, method="Spark-IRFA", cores=mc), "train_s")
        V["E2_OVERHEAD_MAX"] = pct(t_ir / t_rf - 1, 1)
        V["E2_RED_MAX"] = V[f"E2_RED_{mc}"] if mc in CORES else DASH
    else:
        V["E2_OVERHEAD_MAX"] = V["E2_RED_MAX"] = DASH
    V["E2_IRF_NTREES"] = num(_mean(_get(e2, method="Spark-IRFA"), "final_trees"), 0)

    # ---------------------------------------------------------------- E3
    e3 = _read(os.path.join(res, "e3_datasize.csv"))
    irf_acc = []
    for f in FRACS:
        k = int(f * 100)
        rf, ir = _get(e3, method="Spark-RFA", fraction=f), _get(e3, method="Spark-IRFA", fraction=f)
        V[f"E3_GB_{k}"] = num(_mean(ir, "raw_gb"), 2)
        V[f"E3_N_{k}"] = f"{int(_mean(ir, 'n_train')):,}" if not ir.empty else DASH
        V[f"E3_RF_ACC_{k}"] = pct(_mean(rf, "accuracy"))
        a = _mean(ir, "accuracy")
        irf_acc.append(a)
        V[f"E3_IRF_ACC_{k}"] = pct(a)
        V[f"E3_RF_TRAIN_{k}"] = secs(_mean(rf, "train_s"))
        V[f"E3_IRF_TRAIN_{k}"] = secs(_mean(ir, "train_s"))
        V[f"E3_IRF_NTREES_{k}"] = num(_mean(ir, "final_trees"), 0)
    if len(irf_acc) == 3 and not any(np.isnan(irf_acc)):
        diff = irf_acc[-1] - irf_acc[0]
        V["E3_TREND"] = ("increased" if diff > 0.0005 else "decreased" if diff < -0.0005
                         else "stayed approximately constant")
        V["E3_DIFF"] = signed_pp(diff)
    else:
        V["E3_TREND"], V["E3_DIFF"] = "could not be assessed", DASH
    V["E3_GAP_56"] = (f"{100 * irf_acc[-1] - PAPER['e3_irf_accuracy'][5.6]:+.2f}"
                      if irf_acc and not np.isnan(irf_acc[-1]) else DASH)
    return V


def _f(V, key):
    try:
        return float(str(V[key]).replace(",", "").replace("+", ""))
    except (KeyError, ValueError):
        return np.nan


def add_verdicts(V: dict) -> dict:
    """Claim-by-claim verdicts used in the comparison table (Section 4.5)."""
    d = _f(V, "E1_D_IRF_RF_200")
    V["V_A"] = (DASH if np.isnan(d) else "Reproduced" if d > 0.05 else
                "Not reproduced (no measurable gain)" if d >= -0.05 else "Not reproduced (IRF lower)")
    gaps = [abs(_f(V, f"E1_GAP_{k}_200")) for k in ("PY", "RF", "IRF")]
    gaps = [g for g in gaps if not np.isnan(g)]
    V["V_B"] = (DASH if not gaps else "Reproduced (all within 1 pp)" if max(gaps) <= 1 else
                f"Partly reproduced (largest gap {max(gaps):.2f} pp)" if max(gaps) <= 3 else
                f"Different (largest gap {max(gaps):.2f} pp)")
    r = _f(V, "E2_RED_MAX")
    V["V_C"] = (DASH if np.isnan(r) else "Reproduced qualitatively" if r > 0 else "Not reproduced")
    dr = _f(V, "E1_DIAGRED_100")
    V["V_D"] = (DASH if np.isnan(dr) else "Reproduced" if dr > 0 else "Not reproduced")
    o = _f(V, "E2_OVERHEAD_MAX")
    V["V_E"] = (DASH if np.isnan(o) else "Reproduced" if o > 0 else "Not reproduced")
    t = V.get("E3_TREND", "")
    V["V_F"] = ("Reproduced" if t == "increased" else DASH if t == "could not be assessed" else
                "Not reproduced")
    V["V_COUNT"] = str(sum(1 for k in "ABCDEF" if str(V[f"V_{k}"]).startswith(("Reproduced", "Partly"))))
    return V
