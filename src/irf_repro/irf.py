"""Improved Random Forest (IRF) of Wan et al. (2021) - pure NumPy logic.

Steps implemented (paper Section III):
  Step 2  remove low-accuracy trees  -> sub-forest of w trees            (filter_trees)
  Step 3  extract root-to-leaf paths of the w trees                      (trees.extract_paths)
  Step 4  similarity matrix  treeSim(a, b)  from Eq. (1)-(3)             (tree_similarity)
  Step 5  group trees whose similarity to a seed tree exceeds threshold  (select_trees)
  Step 6  keep the most accurate tree of every group, provided it is not
          too similar to a tree that has already been kept               (select_trees)
  Step 7  the kept trees form the IRF model (majority voting)

Eq. (1)  nodeSim(r, s) = 1 if feature(r) == feature(s) and |n_r - n_s| / |n_r| <= alpha else 0
Eq. (2)  pathSim(i, j) = [1 + sum_{m=2}^{phi-1} nodeSim(i.m, j.m) + 1] / phi * pathLength_i
         with phi = min(pathLength_i, pathLength_j); pathSim = 0 when the two leaves differ.
         (root counts 1 because roots were already found similar; leaf counts 1 because the
         leaves give the same diagnosis.)
Eq. (3)  treeSim(a, b) = sum_i pathMaxSim_i / sum_i pathLength_i,
         pathMaxSim_i = max_j pathSim(i, j) over the paths j of tree b;
         treeSim(a, b) = 0 when the roots of a and b are not similar; treeSim(a, a) = 1.
"""
from __future__ import annotations

import numpy as np


def node_similar(f_r, t_r, f_s, t_s, alpha):
    """Vectorised Eq. (1). Works with scalars or broadcastable arrays."""
    same_feature = (f_r == f_s) & (f_r >= 0)
    close = np.abs(t_r - t_s) <= alpha * np.abs(t_r)
    return same_feature & close


def tree_similarity(paths_a, paths_b, alpha: float = 0.2) -> float:
    """treeSim(a, b) of Eq. (3).  paths_* = output of trees.extract_paths."""
    fa, ta, la, ya = paths_a
    fb, tb, lb, yb = paths_b
    # Root test: the first node of every path is the root of the tree.
    if la.max() == 1 or lb.max() == 1:              # a tree that is a single leaf
        return float(la.max() == lb.max() == 1 and ya[0] == yb[0])
    if not node_similar(fa[0, 0], ta[0, 0], fb[0, 0], tb[0, 0], alpha):
        return 0.0

    phi = np.minimum(la[:, None], lb[None, :])                    # (Pa, Pb)
    xi = np.full(phi.shape, 2, dtype=np.int32)                    # root + leaf
    depth = min(fa.shape[1], fb.shape[1])
    for m in range(1, depth):                                     # internal nodes 2 .. phi-1
        valid = m < (phi - 1)
        if not valid.any():
            break
        sim = node_similar(fa[:, m][:, None], ta[:, m][:, None], fb[:, m][None, :], tb[:, m][None, :], alpha)
        xi += (sim & valid).astype(np.int32)
    xi = np.minimum(xi, phi)                                      # paths of length 2: root + leaf only
    same_leaf = ya[:, None] == yb[None, :]
    path_sim = np.where(same_leaf, xi / phi * la[:, None], 0.0)   # Eq. (2)
    path_max = path_sim.max(axis=1)
    return float(path_max.sum() / la.sum())                       # Eq. (3)


def similarity_row(a: int, all_paths: list, alpha: float) -> np.ndarray:
    """Row a of the similarity matrix (one Spark task computes one row)."""
    w = len(all_paths)
    row = np.zeros(w, dtype=np.float64)
    for b in range(w):
        row[b] = 1.0 if a == b else tree_similarity(all_paths[a], all_paths[b], alpha)
    return row


def filter_trees(val_acc: np.ndarray, rule: str = "mean") -> np.ndarray:
    """Step 2: indices of the trees kept in the sub-forest.

    rule = "mean"      keep trees with accuracy >= mean accuracy
    rule = "top:0.5"   keep the best 50 % of the trees
    """
    val_acc = np.asarray(val_acc, dtype=float)
    if rule == "mean":
        keep = np.nonzero(val_acc >= val_acc.mean())[0]
    elif rule.startswith("top:"):
        frac = float(rule.split(":", 1)[1])
        k = max(1, int(round(frac * len(val_acc))))
        keep = np.sort(np.argsort(-val_acc, kind="stable")[:k])
    else:
        raise ValueError(f"unknown filter rule {rule!r}")
    return keep


def select_trees(sim: np.ndarray, acc: np.ndarray, threshold: float = 0.7):
    """Steps 5-6 on the w x w similarity matrix of the sub-forest.

    Returns (selected positions in the sub-forest, list of groups).
    Two trees are "too similar" when max(sim[a, b], sim[b, a]) > threshold
    (treeSim is not symmetric, so both directions are checked).
    """
    w = sim.shape[0]
    sym = np.maximum(sim, sim.T)
    assigned = np.zeros(w, dtype=bool)
    groups = []
    for a in range(w):                                   # Step 5: seed = first unassigned tree
        if assigned[a]:
            continue
        members = [a] + [b for b in range(w) if not assigned[b] and b != a and sim[a, b] > threshold]
        assigned[members] = True
        groups.append(members)

    selected = []
    for members in groups:                               # Step 6
        for cand in sorted(members, key=lambda t: (-acc[t], t)):
            if all(sym[cand, s] <= threshold for s in selected):
                selected.append(cand)
                break
    return sorted(selected), groups


def majority_vote(trees, X: np.ndarray, n_classes: int) -> np.ndarray:
    """Hard majority vote of FlatTree objects (ties -> smallest class index)."""
    votes = np.zeros((X.shape[0], n_classes), dtype=np.int32)
    rows = np.arange(X.shape[0])
    for t in trees:
        votes[rows, t.predict(X).astype(np.int64)] += 1
    return votes.argmax(axis=1).astype(float)
