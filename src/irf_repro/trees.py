"""Decision-tree export from Spark MLlib and fast NumPy evaluation.

Spark saves a RandomForestClassificationModel as Parquet under <path>/data with one row per
node: (treeID, nodeData{id, prediction, leftChild, rightChild, split{featureIndex,
leftCategoriesOrThreshold, numCategories}, ...}).  Leaves have leftChild = rightChild = -1.
For continuous features Spark sends a sample to the LEFT child when x[feature] <= threshold.

Each tree is converted to flat arrays (a "FlatTree") so that it can be broadcast to the
workers and evaluated on whole partitions with NumPy.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class FlatTree:
    feature: np.ndarray      # int32, -1 for leaves
    threshold: np.ndarray    # float64
    left: np.ndarray         # int32 position of left child, -1 for leaves
    right: np.ndarray        # int32 position of right child, -1 for leaves
    value: np.ndarray        # float64 predicted class at the node (used at leaves)

    @property
    def n_nodes(self) -> int:
        return int(self.feature.shape[0])

    @property
    def depth(self) -> int:
        depth = np.zeros(self.n_nodes, dtype=np.int32)
        for i in range(self.n_nodes):              # parents precede children (pre-order)
            for c in (self.left[i], self.right[i]):
                if c >= 0:
                    depth[c] = depth[i] + 1
        return int(depth.max())

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Vectorised traversal: all samples move one level per iteration."""
        X = np.asarray(X, dtype=np.float64)
        node = np.zeros(X.shape[0], dtype=np.int64)
        active = self.left[node] >= 0
        while active.any():
            idx = np.nonzero(active)[0]
            cur = node[idx]
            go_left = X[idx, self.feature[cur]] <= self.threshold[cur]
            node[idx] = np.where(go_left, self.left[cur], self.right[cur])
            active[idx] = self.left[node[idx]] >= 0
        return self.value[node]


def flat_tree_from_nodes(ids, prediction, left_child, right_child, feature_index, thresholds):
    """Build a FlatTree from the columns of one tree's nodeData rows (any row order).

    The node with id == 0 is the root (Spark numbers nodes in pre-order starting at 0).
    Positions are re-assigned in pre-order so that parents always precede children.
    """
    ids = np.asarray(ids, dtype=np.int64)
    pos_of = {int(i): k for k, i in enumerate(ids)}
    order = []
    stack = [0]
    while stack:
        nid = stack.pop()
        order.append(nid)
        k = pos_of[nid]
        lc, rc = int(left_child[k]), int(right_child[k])
        if lc >= 0:
            stack.append(rc)
            stack.append(lc)
    new_pos = {nid: p for p, nid in enumerate(order)}
    n = len(order)
    feat = np.full(n, -1, dtype=np.int32)
    thr = np.zeros(n, dtype=np.float64)
    left = np.full(n, -1, dtype=np.int32)
    right = np.full(n, -1, dtype=np.int32)
    val = np.zeros(n, dtype=np.float64)
    for nid in order:
        k = pos_of[nid]
        p = new_pos[nid]
        val[p] = float(prediction[k])
        lc, rc = int(left_child[k]), int(right_child[k])
        if lc >= 0:
            feat[p] = int(feature_index[k])
            t = thresholds[k]
            thr[p] = float(t[0]) if len(t) else 0.0
            left[p] = new_pos[lc]
            right[p] = new_pos[rc]
    return FlatTree(feat, thr, left, right, val)


def export_spark_forest(spark, model, export_dir: str) -> list[FlatTree]:
    """Save an MLlib forest and read its node table back as a list of FlatTree."""
    model.write().overwrite().save(export_dir)
    nodes = (
        spark.read.parquet(f"{export_dir}/data")
        .selectExpr(
            "treeID",
            "nodeData.id AS id",
            "nodeData.prediction AS prediction",
            "nodeData.leftChild AS leftChild",
            "nodeData.rightChild AS rightChild",
            "nodeData.split.featureIndex AS featureIndex",
            "nodeData.split.leftCategoriesOrThreshold AS thr",
        )
        .toPandas()
    )
    trees = []
    for tid in sorted(nodes["treeID"].unique()):
        g = nodes[nodes["treeID"] == tid]
        trees.append(
            flat_tree_from_nodes(g["id"].values, g["prediction"].values, g["leftChild"].values,
                                 g["rightChild"].values, g["featureIndex"].values, list(g["thr"].values))
        )
    return trees


def flat_tree_from_sklearn(est) -> FlatTree:
    """Convert a fitted sklearn DecisionTreeClassifier (used only by the unit tests)."""
    t = est.tree_
    n = t.node_count
    ids = np.arange(n)
    pred = est.classes_[np.argmax(t.value[:, 0, :], axis=1)].astype(float)
    thr = [[t.threshold[i]] if t.children_left[i] >= 0 else [] for i in range(n)]
    return flat_tree_from_nodes(ids, pred, t.children_left, t.children_right, t.feature, thr)


def extract_paths(tree: FlatTree):
    """All root-to-leaf paths of a tree.

    Returns (features, thresholds, lengths, leaf_class):
      features   (P, D) int32  split feature of the k-th internal node of each path, -1 padded
      thresholds (P, D) float  split value of that node
      lengths    (P,)   int    number of nodes on the path, leaf included (= pathLength)
      leaf_class (P,)   float  diagnosis result stored in the leaf
    """
    paths = []
    stack = [(0, [])]
    while stack:
        node, prefix = stack.pop()
        if tree.left[node] < 0:
            paths.append((prefix, tree.value[node]))
            continue
        here = prefix + [(int(tree.feature[node]), float(tree.threshold[node]))]
        stack.append((int(tree.right[node]), here))
        stack.append((int(tree.left[node]), here))
    depth = max(1, max(len(p) for p, _ in paths))
    P = len(paths)
    feats = np.full((P, depth), -1, dtype=np.int32)
    thrs = np.zeros((P, depth), dtype=np.float64)
    lengths = np.zeros(P, dtype=np.int32)
    leaf = np.zeros(P, dtype=np.float64)
    for i, (nodes, cls) in enumerate(paths):
        for m, (f, t) in enumerate(nodes):
            feats[i, m] = f
            thrs[i, m] = t
        lengths[i] = len(nodes) + 1
        leaf[i] = cls
    return feats, thrs, lengths, leaf
