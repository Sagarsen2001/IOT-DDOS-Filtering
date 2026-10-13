"""
ml/evaluate.py
==============
Model evaluation utilities.
Computes accuracy, precision, recall, F1, confusion matrix, FPR, and TPR.
Results are returned as a JSON-serialisable dict and optionally saved.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

import config
from database.models import EvaluationMetrics
from database.repository import insert_evaluation_metrics

logger = logging.getLogger(__name__)


def evaluate(y_true: np.ndarray, y_pred: np.ndarray, y_prob: np.ndarray) -> Dict[str, Any]:
    """
    Compute classification metrics.

    Parameters
    ----------
    y_true : Ground-truth labels (0 or 1).
    y_pred : Predicted labels.
    y_prob : Predicted probabilities for class 1.

    Returns
    -------
    dict with all metrics as JSON-serialisable values.
    """
    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)

    cm = confusion_matrix(y_true, y_pred)
    # cm shape: [[TN, FP], [FN, TP]]
    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)

    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    tpr = tp / (tp + fn) if (tp + fn) > 0 else 0.0  # same as recall

    result: Dict[str, Any] = {
        "model_version": config.MODEL_VERSION,
        "accuracy": round(float(acc), 4),
        "precision": round(float(prec), 4),
        "recall": round(float(rec), 4),
        "f1_score": round(float(f1), 4),
        "false_positive_rate": round(float(fpr), 4),
        "true_positive_rate": round(float(tpr), 4),
        "confusion_matrix": {
            "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
        },
        "support": {
            "n_normal": int(np.sum(y_true == 0)),
            "n_ddos": int(np.sum(y_true == 1)),
        },
    }

    logger.info(
        "Evaluation — acc=%.3f prec=%.3f rec=%.3f f1=%.3f fpr=%.3f",
        acc, prec, rec, f1, fpr,
    )
    return result


def save_metrics(metrics: Dict[str, Any], path: str = config.METRICS_PATH) -> None:
    """Persist metrics dict to JSON and to the database."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as fh:
        json.dump(metrics, fh, indent=2)
    logger.info("Metrics saved to %s", p)

    # Persist to DB so the API can retrieve them
    try:
        em = EvaluationMetrics(
            model_version=metrics.get("model_version", config.MODEL_VERSION),
            accuracy=metrics.get("accuracy"),
            precision_score=metrics.get("precision"),
            recall_score=metrics.get("recall"),
            f1_score=metrics.get("f1_score"),
            fpr=metrics.get("false_positive_rate"),
            tpr=metrics.get("true_positive_rate"),
        )
        insert_evaluation_metrics(em)
    except Exception as exc:
        logger.warning("Could not persist metrics to database: %s", exc)


def load_metrics(path: str = config.METRICS_PATH) -> Dict[str, Any]:
    """Load saved metrics from JSON.  Returns empty dict if file missing."""
    p = Path(path)
    if not p.exists():
        return {}
    with open(p) as fh:
        return json.load(fh)
