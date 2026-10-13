"""
ml/predict.py
=============
Inference module.  Loads the trained model once at import time and exposes
predict_single() and predict_batch() so the rest of the system doesn't
need to know about joblib or sklearn.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

import config
from ml.model import load_model
from ml.preprocess import transform, transform_batch

logger = logging.getLogger(__name__)

# Module-level cache so the model is loaded only once per process
_model = None
_model_load_error: Optional[str] = None


def _get_model():
    """Return the cached model, loading it on first call."""
    global _model, _model_load_error
    if _model is None and _model_load_error is None:
        try:
            _model = load_model()
            logger.info("ML model loaded successfully (version=%s)", config.MODEL_VERSION)
        except FileNotFoundError as exc:
            _model_load_error = str(exc)
            logger.error("ML model not found: %s", exc)
    return _model


def is_model_loaded() -> bool:
    """Return True if the model is ready for inference."""
    return _get_model() is not None


def reload_model() -> bool:
    """Force a reload of the model from disk (useful after re-training)."""
    global _model, _model_load_error
    _model = None
    _model_load_error = None
    return is_model_loaded()


def predict_single(flow_features: Dict[str, Any]) -> Dict[str, Any]:
    """
    Classify a single network flow.

    Parameters
    ----------
    flow_features : dict with at minimum the keys defined in preprocess.py.

    Returns
    -------
    dict with keys: prediction, label, probability, confidence,
                    model_version, timestamp
    """
    clf = _get_model()
    if clf is None:
        return {
            "error": "model_not_loaded",
            "message": _model_load_error or "Model not available",
        }

    X = transform(flow_features)
    pred_label = int(clf.predict(X)[0])
    proba = clf.predict_proba(X)[0]
    ddos_prob = float(proba[1])
    confidence = float(max(proba))

    return {
        "prediction": "DDOS" if pred_label == 1 else "NORMAL",
        "label": pred_label,
        "probability": round(ddos_prob, 4),
        "confidence": round(confidence, 4),
        "model_version": config.MODEL_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def predict_batch(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Classify a batch of flows.

    Parameters
    ----------
    df : DataFrame with feature columns.

    Returns
    -------
    List of prediction dicts (same shape as predict_single output).
    """
    clf = _get_model()
    if clf is None:
        return [{"error": "model_not_loaded"} for _ in range(len(df))]

    X = transform_batch(df)
    pred_labels = clf.predict(X)
    probas = clf.predict_proba(X)
    now = datetime.now(timezone.utc).isoformat()

    results = []
    for i, pred_label in enumerate(pred_labels):
        ddos_prob = float(probas[i][1])
        confidence = float(max(probas[i]))
        results.append({
            "prediction": "DDOS" if pred_label == 1 else "NORMAL",
            "label": int(pred_label),
            "probability": round(ddos_prob, 4),
            "confidence": round(confidence, 4),
            "model_version": config.MODEL_VERSION,
            "timestamp": now,
        })
    return results
