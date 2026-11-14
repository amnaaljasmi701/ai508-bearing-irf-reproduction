# Reproduction of Wan et al. (2021): Spark + Improved Random Forest for Bearing Fault Diagnosis

AI508 Big Data Technologies and Applications – Assignment 2 (single-student team).

**Original paper.** L. Wan, K. Gong, G. Zhang, X. Yuan, C. Li and X. Deng, "An Efficient Rolling Bearing
Fault Diagnosis Method Based on Spark and Improved Random Forest Algorithm", *IEEE Access* 9 (2021)
37866–37882. [https://doi.org/10.1109/ACCESS.2021.3063929](https://doi.org/10.1109/ACCESS.2021.3063929)

**Dataset.** CWRU Bearing Data Center, [https://engineering.case.edu/bearingdatacenter](https://engineering.case.edu/bearingdatacenter)
(40 files: 10 health states × 4 loads, 12 kHz drive end; list in `src/irf_repro/cwru.py`).

The original code is not published; everything here is a re-implementation from the paper's text.

## What is reproduced

| Experiment | Paper | Here |
|---|---|---|
| E1 accuracy | Python-RFA vs Spark-RFA vs Spark-IRFA, 20–200 trees | same three methods, 20 / 100 / 200 trees, 5.6 GB dataset |
| E2 scalability | 1–4 worker nodes | 1 / 2 / 3 / 4 Spark executor cores (`local[c]`) as a proxy |
| E1b (supplementary) | – | E1 with a time-blocked split, to test overlap leakage |
| E3 data size | 5.6 / 11.2 / 20.4 GB | nested subsets of 1.4 / 2.8 / 5.6 GB |

## Repository layout

```
config.yaml               all settings (paper values and documented assumptions)
config_smoke.yaml         tiny version for a 5-minute end-to-end test
setup/setup_wsl.sh        one-time environment setup (Java 17, Python 3.11, venv, packages)
setup/.wslconfig          WSL2 memory limit (copy to C:\Users\<you>\.wslconfig)
src/irf_repro/
  cwru.py                 CWRU catalogue, .mat loading, overlapping-window indices
  wpd.py                  vectorised wavelet-packet relative-energy features
  trees.py                MLlib tree export (Parquet node table) -> NumPy, path extraction
  irf.py                  IRF Steps 2-7: filter, Eq. (1)-(3) similarity, grouping, selection, voting
  spark_jobs.py           Spark session, splits, Spark RF, distributed IRF, sub-model rebuild
  experiment.py           one experimental run (all three methods, timings, CSV output)
  report_values.py        turns results/*.csv into the numbers used in the report/slides
  paper_values.py         numbers reported by the paper (for comparison only)
scripts/
  00_check_env.py         records hardware/software versions -> results/environment.json
  01_download_cwru.py     downloads and checks the 40 .mat files
  02_make_dataset.py      Spark job: overlapping sampling -> data/windows.parquet (~5.6 GB)
  03_extract_features.py  Spark job: wavelet-packet features -> data/features.parquet
  04_run_e1_accuracy.py   E1
  05_run_e2_scalability.py E2
  06_run_e3_datasize.py   E3
  07_make_figures.py      figures/*.png from results/*.csv
  08_build_report.py      fills report/ and slide templates with the measured numbers
  run_all.sh              whole pipeline
tests/test_core.py        unit tests (tree export, IRF logic, wavelet features)
report/                   report and slide templates (+ generated files)
results/  figures/        produced by the scripts (commit them)
```

## Running on GitHub Actions (how the reported results were produced)

The workflow `.github/workflows/experiments.yml` runs the whole pipeline on a GitHub-hosted
runner (4 vCPUs, 16 GB RAM) and commits `results/`, `figures/` and the generated report back to
the repository. Start it from the **Actions** tab (*Run workflow*, mode `smoke`, `full` or `extra`)
or push a commit whose message contains `[run smoke]`, `[run full]` or `[run extra]` (E1b only).

## Local setup (Windows 11 + WSL2 Ubuntu 22.04)

1. In PowerShell: `wsl --install -d Ubuntu-22.04` (skip if installed).
2. Copy `setup/.wslconfig` to `C:\Users\<you>\.wslconfig`, then `wsl --shutdown` and reopen Ubuntu.
3. Put the repository inside the Linux file system (e.g. `~/ai508-irf`), not under `/mnt/c`, for disk speed.
4. `bash setup/setup_wsl.sh` – installs OpenJDK 17, Python 3.11, a virtual environment and `requirements.txt`.
5. Every new terminal: `source .venv/bin/activate`.

## Running

```bash
python -m pytest -q tests                           # unit tests (no Spark needed)
IRF_CONFIG=config_smoke.yaml bash scripts/run_all.sh  # 5-minute smoke test, writes *_smoke folders
bash scripts/run_all.sh                             # full run (several hours on a laptop)
```

Steps can also be run one by one (`python scripts/02_make_dataset.py`, …). Re-running an experiment
script with `--fresh` deletes its previous CSV first. To average over several seeds set
`experiments.seeds: [42, 7, 2026]` in `config.yaml`.

Before building the report, set `report.author`, `report.student_id` and `report.github_url` in
`config.yaml`. `python scripts/08_build_report.py` writes `report/AI508_A2_Report.docx` and
`report/AI508_A2_Presentation.pptx`; every number in them comes from `results/`.

## Implementation notes

* **Tree export.** MLlib trees are saved and read back from the Parquet node table
  (`data/` → `nodeData`); a sample goes left when `x[feature] <= threshold`. E1 checks that the
  exported trees predict exactly like MLlib (`export_agree` column).
* **Distributed IRF.** Trees are broadcast; validation accuracy of every tree is computed per
  partition with `mapInPandas` and summed (Step 2); path extraction is a `map` (Step 3); one Spark
  task computes one row of the similarity matrix (Step 4). The kept trees are rebuilt into a real
  `RandomForestClassificationModel` through the JVM so Spark-RFA and Spark-IRFA are diagnosed by the
  same engine (`irf.engine: python` switches to NumPy majority voting).
* **Timing.** Data are cached and counted before timing; IRF training time = MLlib fit + sub-forest
  optimisation; diagnosis time = predict the whole test set + compute accuracy. Every setting runs in
  a fresh JVM.
* **Assumptions** (not given in the paper) are marked in `config.yaml`: window length 2,048, db4
  level-3 wavelet packet, max depth 10, mean-accuracy filter, similarity threshold 0.5.

## Acknowledgements

Apache Spark/PySpark, NumPy, pandas, PyArrow, SciPy, PyWavelets, scikit-learn, Matplotlib,
python-docx, python-pptx; the report/slide templates were generated with docx and pptxgenjs
(`report/template_src`). Data: Case Western Reserve University Bearing Data Center.
