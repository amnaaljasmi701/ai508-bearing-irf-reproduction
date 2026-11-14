"""Unit tests for the parts that do not need Spark: tree export format, IRF logic, features.

Run:  python -m pytest -q tests
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from irf_repro.irf import filter_trees, majority_vote, node_similar, select_trees, similarity_row, tree_similarity
from irf_repro.trees import extract_paths, flat_tree_from_nodes, flat_tree_from_sklearn
from irf_repro.cwru import window_starts, windows_per_file
from irf_repro.wpd import _freq_order


@pytest.fixture(scope="module")
def forest():
    from sklearn.datasets import make_classification
    from sklearn.ensemble import RandomForestClassifier

    X, y = make_classification(n_samples=3000, n_features=8, n_informative=6, n_redundant=0,
                               n_classes=4, random_state=0)
    rf = RandomForestClassifier(n_estimators=30, max_depth=6, max_features=3, random_state=0).fit(X, y)
    trees = [flat_tree_from_sklearn(e) for e in rf.estimators_]
    return X, y, rf, trees


def test_flat_tree_matches_sklearn(forest):
    X, _, rf, trees = forest
    for est, t in zip(rf.estimators_, trees):
        assert np.array_equal(t.predict(X), est.predict(X).astype(float))


def test_node_order_independent(forest):
    """Rows of Spark's node table may arrive in any order."""
    X, _, rf, _ = forest
    tr = rf.estimators_[0].tree_
    n = tr.node_count
    perm = np.random.default_rng(1).permutation(n)
    pred = rf.estimators_[0].classes_[np.argmax(tr.value[:, 0, :], axis=1)].astype(float)
    thr = [[tr.threshold[i]] if tr.children_left[i] >= 0 else [] for i in range(n)]
    t = flat_tree_from_nodes(np.arange(n)[perm], pred[perm], tr.children_left[perm], tr.children_right[perm],
                             tr.feature[perm], [thr[i] for i in perm])
    assert np.array_equal(t.predict(X), rf.estimators_[0].predict(X).astype(float))


def test_paths(forest):
    _, _, rf, trees = forest
    f, th, length, leaf = extract_paths(trees[0])
    assert len(length) == rf.estimators_[0].tree_.n_leaves
    assert length.max() == trees[0].depth + 1
    assert np.all(f[:, 0] == trees[0].feature[0])          # every path starts at the root


def test_similarity_properties(forest):
    _, _, _, trees = forest
    paths = [extract_paths(t) for t in trees[:8]]
    for a in range(8):
        row = similarity_row(a, paths, 0.2)
        assert row[a] == 1.0
        assert np.all((row >= 0) & (row <= 1 + 1e-12))
    assert tree_similarity(paths[0], paths[0], 0.2) == pytest.approx(1.0)


def test_root_rule():
    assert node_similar(1, 10.0, 1, 11.9, 0.2)
    assert not node_similar(1, 10.0, 1, 12.5, 0.2)
    assert not node_similar(1, 10.0, 2, 10.0, 0.2)


def test_filter_and_select():
    acc = np.array([0.90, 0.95, 0.80, 0.97, 0.96])
    assert list(filter_trees(acc, "mean")) == [1, 3, 4]      # mean = 0.916
    assert list(filter_trees(acc, "top:0.4")) == [3, 4]
    sim = np.array([[1, .9, .1], [.9, 1, .1], [.1, .1, 1]])
    sel, groups = select_trees(sim, np.array([0.9, 0.95, 0.8]), 0.7)
    assert groups == [[0, 1], [2]]
    assert sel == [1, 2]                                    # best of group 1, then group 2


def test_majority_vote(forest):
    X, y, _, trees = forest
    pred = majority_vote(trees, X, 4)
    assert (pred == y).mean() > 0.7


def test_windows():
    s = window_starts(10_000, 2048, 50)
    assert s[0] == 0 and s[-1] == 10_000 - 2048 and len(s) == 50
    assert windows_per_file(5.6, 2048, 40) * 40 * 2048 * 8 >= 5.6e9


def test_freq_order_level2():
    # natural order aa, ad, da, dd -> frequency order aa, ad, dd, da
    assert _freq_order(2) == [0, 1, 3, 2]
    # aaa, aad, add, ada, dda, ddd, dad, daa  (pywt "freq" order)
    assert _freq_order(3) == [0, 1, 3, 2, 6, 7, 5, 4]


def test_wpd_against_pywt():
    pywt = pytest.importorskip("pywt")
    from irf_repro.wpd import wpd_energy_features

    x = np.random.default_rng(0).normal(size=(3, 2048))
    ours = wpd_energy_features(x, "db4", 3, "periodization", True)
    for i in range(3):
        xi = (x[i] - x[i].mean()) / x[i].std()
        wp = pywt.WaveletPacket(xi, "db4", mode="periodization", maxlevel=3)
        e = np.array([np.sum(n.data ** 2) for n in wp.get_level(3, order="freq")])
        assert np.allclose(ours[i], e / e.sum())
