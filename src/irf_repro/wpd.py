"""Wavelet-packet feature extraction (vectorised over a batch of windows).

For every window x (length L) the full wavelet packet tree is built down to `level`
by applying the single-level DWT to every node (approximation and detail alike).
The feature vector is the relative energy of the 2^level terminal nodes:

    E_k = sum(c_k^2),   f_k = E_k / sum_j E_j ,   k = 0 .. 2^level - 1

Nodes are returned in frequency order (Gray-code reordering of the natural order),
which is the order used by pywt.WaveletPacket.get_level(level, order="freq").
"""
from __future__ import annotations

import numpy as np


def _freq_order(level: int) -> list[int]:
    """Indices that reorder natural-order packet nodes into frequency order."""
    order = ["a", "d"]
    for _ in range(level - 1):
        nxt = []
        for i, path in enumerate(order):
            # Even positions keep (a, d); odd positions swap to (d, a) (Gray code).
            kids = ("a", "d") if i % 2 == 0 else ("d", "a")
            nxt.extend(path + k for k in kids)
        order = nxt
    natural = sorted(order, key=lambda p: int(p.replace("a", "0").replace("d", "1"), 2))
    index = {p: i for i, p in enumerate(natural)}
    return [index[p] for p in order]


def wpd_energy_features(batch: np.ndarray, wavelet: str = "db4", level: int = 3,
                        mode: str = "periodization", standardize: bool = True) -> np.ndarray:
    """batch: (n_windows, L) array -> (n_windows, 2**level) relative energies."""
    import pywt

    x = np.asarray(batch, dtype=np.float64)
    if x.ndim == 1:
        x = x[None, :]
    if standardize:
        mu = x.mean(axis=1, keepdims=True)
        sd = x.std(axis=1, keepdims=True)
        sd[sd == 0] = 1.0
        x = (x - mu) / sd

    nodes = [x]                        # natural order: a, d, aa, ad, da, dd, ...
    for _ in range(level):
        nxt = []
        for node in nodes:
            cA, cD = pywt.dwt(node, wavelet, mode=mode, axis=-1)
            nxt.extend([cA, cD])
        nodes = nxt

    energy = np.stack([np.sum(n * n, axis=1) for n in nodes], axis=1)
    energy = energy[:, _freq_order(level)]
    total = energy.sum(axis=1, keepdims=True)
    total[total == 0] = 1.0
    return energy / total
