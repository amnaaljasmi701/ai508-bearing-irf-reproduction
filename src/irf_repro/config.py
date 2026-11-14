"""Configuration loading and small helpers shared by all scripts."""
from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_config(path: str | os.PathLike | None = None) -> dict:
    """Read config.yaml and turn every entry of `paths` into an absolute path."""
    path = path or os.environ.get("IRF_CONFIG")
    cfg_path = Path(path) if path else REPO_ROOT / "config.yaml"
    if not cfg_path.is_absolute():
        cfg_path = REPO_ROOT / cfg_path
    with open(cfg_path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    cfg["paths"] = {k: str((REPO_ROOT / v).resolve()) for k, v in cfg["paths"].items()}
    for key in ("raw_mat_dir", "results_dir", "figures_dir", "tmp_dir"):
        Path(cfg["paths"][key]).mkdir(parents=True, exist_ok=True)
    return cfg


@contextmanager
def timer():
    """Usage: `with timer() as t: ...` then `t()` returns elapsed seconds."""
    start = time.perf_counter()
    elapsed = {"v": None}

    def get():
        return elapsed["v"] if elapsed["v"] is not None else time.perf_counter() - start

    try:
        yield get
    finally:
        elapsed["v"] = time.perf_counter() - start


def save_json(obj, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, default=str)


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def append_csv_row(path, row: dict):
    """Append one result row to a CSV file (header written on first use)."""
    import csv

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(row.keys()))
        if new:
            writer.writeheader()
        writer.writerow(row)
