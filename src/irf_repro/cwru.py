"""CWRU Bearing Data Center catalogue (12 kHz drive-end data) and .mat loading.

Ten health states x four motor loads (0-3 hp) = 40 files.  The file numbers are those
published on https://engineering.case.edu/bearingdatacenter (Normal Baseline Data and
12k Drive End Bearing Fault Data; outer-race faults at the 6 o'clock position).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

BASE_URL = "https://engineering.case.edu/sites/default/files/{num}.mat"

# class label -> (class name, file numbers for loads 0, 1, 2, 3 hp)
CATALOGUE = {
    0: ("Normal", [97, 98, 99, 100]),
    1: ("IR007", [105, 106, 107, 108]),
    2: ("B007", [118, 119, 120, 121]),
    3: ("OR007@6", [130, 131, 132, 133]),
    4: ("IR014", [169, 170, 171, 172]),
    5: ("B014", [185, 186, 187, 188]),
    6: ("OR014@6", [197, 198, 199, 200]),
    7: ("IR021", [209, 210, 211, 212]),
    8: ("B021", [222, 223, 224, 225]),
    9: ("OR021@6", [234, 235, 236, 237]),
}

CLASS_NAMES = [CATALOGUE[k][0] for k in sorted(CATALOGUE)]


def file_table(loads=(0, 1, 2, 3)):
    """List of dicts: file_id, label, class_name, load, url."""
    rows = []
    for label, (name, nums) in sorted(CATALOGUE.items()):
        for load, num in enumerate(nums):
            if load in loads:
                rows.append(
                    {"file_id": num, "label": label, "class_name": name, "load": load,
                     "url": BASE_URL.format(num=num)}
                )
    return rows


def load_de_signal(mat_path: str | Path, file_id: int) -> np.ndarray:
    """Return the drive-end accelerometer signal (key '*_DE_time') as a 1-D float64 array.

    Some CWRU files contain more than one '*_DE_time' variable; the one whose name
    carries the file number is preferred.
    """
    from scipy.io import loadmat

    mat = loadmat(str(mat_path))
    keys = [k for k in mat if k.endswith("_DE_time")]
    if not keys:
        raise KeyError(f"No *_DE_time variable in {mat_path}")
    tag = f"X{file_id:03d}_"
    preferred = [k for k in keys if k.startswith(tag)]
    key = preferred[0] if preferred else sorted(keys)[0]
    return np.asarray(mat[key], dtype=np.float64).ravel()


def window_starts(n_samples: int, window_length: int, n_windows: int) -> np.ndarray:
    """Evenly spaced start indices of `n_windows` overlapping windows covering the signal."""
    last = n_samples - window_length
    if last < 0:
        raise ValueError("signal shorter than one window")
    return np.linspace(0, last, n_windows).round().astype(np.int64)


def windows_per_file(target_gb: float, window_length: int, n_files: int) -> int:
    """Number of windows per file so that the raw float64 dataset reaches `target_gb` (10^9 bytes)."""
    total = int(np.ceil(target_gb * 1e9 / (window_length * 8)))
    return int(np.ceil(total / n_files))
