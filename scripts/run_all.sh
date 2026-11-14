#!/usr/bin/env bash
# Full pipeline. Smoke test first:  IRF_CONFIG=config_smoke.yaml bash scripts/run_all.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python}
log() { echo; echo "================ $* ================"; date; }

log "0  environment";            $PY scripts/00_check_env.py
log "1  download CWRU";          $PY scripts/01_download_cwru.py
log "2  overlapping sampling";   $PY scripts/02_make_dataset.py
log "3  wavelet-packet features";$PY scripts/03_extract_features.py
log "4  E1 accuracy";            $PY scripts/04_run_e1_accuracy.py --fresh
log "5  E2 scalability";         $PY scripts/05_run_e2_scalability.py --fresh
log "6  E3 data size";           $PY scripts/06_run_e3_datasize.py --fresh
log "7  figures";                $PY scripts/07_make_figures.py
log "8  report + slides";        $PY scripts/08_build_report.py
log "finished"
