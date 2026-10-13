"""
ml/model.py
===========
Model loading / saving utilities.
Keeps joblib I/O in one place so train.py and predict.py share it cleanly.
"""

import logging
from pathlib import Path
from typing import Optional

import joblib
from sklearn.ensemble import RandomForestClassifier

import config

logger = logging.getLogger(__name__)


def save_model(clf: RandomForestClassifier, path: Optional[str] = None) -> None:
    """Persist a trained classifier to disk."""
    save_path = Path(path or config.MODEL_PATH)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf, save_path)
    logger.info("Model saved to %s", save_path)


def load_model(path: Optional[str] = None) -> RandomForestClassifier:
    """Load a persisted classifier.  Raises FileNotFoundError if missing."""
    load_path = Path(path or config.MODEL_PATH)
    if not load_path.exists():
        raise FileNotFoundError(
            f"Model artifact not found at '{load_path}'. "
            "Run `python -m ml.train` or `scripts/train_model.sh` first."
        )
    clf = joblib.load(load_path)
    logger.info("Model loaded from %s", load_path)
    return clf


def build_classifier(seed: int = config.RANDOM_SEED) -> RandomForestClassifier:
    """Return a freshly configured (unfitted) RandomForestClassifier."""
    return RandomForestClassifier(
        n_estimators=100,
        max_depth=None,            # grow full trees
        min_samples_split=5,
        min_samples_leaf=2,
        class_weight="balanced",   # handles class imbalance
        random_state=seed,
        n_jobs=-1,                 # use all CPU cores
    )
