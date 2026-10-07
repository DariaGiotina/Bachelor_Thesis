"""Overall and skin-tone-stratified evaluation."""
import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, f1_score


def stratified_report(y_true, y_pred, groups) -> pd.DataFrame:
    """Macro-F1 and balanced accuracy overall and per group (e.g. Fitzpatrick/Monk)."""
    y_true, y_pred, groups = map(np.asarray, (y_true, y_pred, groups))
    rows = [("ALL", len(y_true), f1_score(y_true, y_pred, average="macro"), balanced_accuracy_score(y_true, y_pred))]
    for g in sorted(set(groups)):
        m = groups == g
        rows.append((g, int(m.sum()), f1_score(y_true[m], y_pred[m], average="macro"), balanced_accuracy_score(y_true[m], y_pred[m])))
    return pd.DataFrame(rows, columns=["group", "n", "macro_f1", "balanced_acc"])


def max_gap(report: pd.DataFrame, col: str = "macro_f1") -> float:
    g = report[report.group != "ALL"][col]
    return float(g.max() - g.min())
