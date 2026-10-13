"""
ml/preprocess.py
================
Feature engineering and preprocessing pipeline.

The SAME transformations must be applied during both training and inference
to avoid training-serving skew.  Preprocessing artifacts are persisted with
joblib so that inference never re-fits transformers on live data.

FEATURE SET
-----------
Numeric:
    duration, packet_count, byte_count,
    packet_rate, byte_rate, avg_packet_size,
    src_port, dst_port

Categorical (label-encoded):
    protocol
"""

import logging
from pathlib import Path
from typing import Dict, Any, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder, StandardScaler

import config

logger = logging.getLogger(__name__)

# Numeric features used for model input
NUMERIC_FEATURES = [
    "duration",
    "packet_count",
    "byte_count",
    "packet_rate",
    "byte_rate",
    "avg_packet_size",
    "src_port",
    "dst_port",
]

# Categorical features that will be label-encoded
CATEGORICAL_FEATURES = ["protocol"]

# All model input features in the exact order the model expects
ALL_FEATURES = NUMERIC_FEATURES + ["protocol_encoded"]

TARGET_COLUMN = "label"


def _load_or_create_artifacts() -> Tuple[StandardScaler, LabelEncoder]:
    """Return persisted artifacts if they exist; otherwise create new instances."""
    scaler_path = Path(config.SCALER_PATH)
    encoder_path = Path(config.ENCODER_PATH)

    scaler = joblib.load(scaler_path) if scaler_path.exists() else StandardScaler()
    encoder = joblib.load(encoder_path) if encoder_path.exists() else LabelEncoder()
    return scaler, encoder


def fit_and_save(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    """
    Fit the scaler and label-encoder on the training dataframe, persist
    the fitted objects, and return (X, y) ready for model training.

    Parameters
    ----------
    df : Raw training dataframe containing all feature columns + 'label'.

    Returns
    -------
    X : np.ndarray of shape (n_samples, n_features)
    y : np.ndarray of shape (n_samples,)
    """
    df = _clean(df)

    scaler = StandardScaler()
    encoder = LabelEncoder()

    # Fit encoder on known protocols; handle unseen ones at inference
    encoder.fit(df["protocol"].fillna("UNKNOWN"))
    df["protocol_encoded"] = encoder.transform(df["protocol"].fillna("UNKNOWN"))

    # Fit scaler on numeric features
    X_numeric = df[NUMERIC_FEATURES].values
    scaler.fit(X_numeric)
    X_numeric_scaled = scaler.transform(X_numeric)

    # Combine
    X = np.hstack([X_numeric_scaled, df[["protocol_encoded"]].values])
    y = df[TARGET_COLUMN].values

    # Persist fitted artifacts
    for path_str, obj in [
        (config.SCALER_PATH, scaler),
        (config.ENCODER_PATH, encoder),
    ]:
        path = Path(path_str)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(obj, path)
        logger.info("Saved preprocessing artifact: %s", path)

    return X, y


def transform(flow: Dict[str, Any]) -> np.ndarray:
    """
    Transform a single flow dict into the model's input vector.

    Uses the persisted scaler and encoder — must NOT re-fit.
    Missing or unknown values are replaced with safe defaults.

    Parameters
    ----------
    flow : dict with keys matching the feature names.

    Returns
    -------
    np.ndarray of shape (1, n_features)
    """
    scaler, encoder = _load_or_create_artifacts()

    numeric_vals = []
    for feat in NUMERIC_FEATURES:
        val = flow.get(feat, 0.0)
        try:
            numeric_vals.append(float(val))
        except (TypeError, ValueError):
            logger.warning("Missing/invalid feature '%s'; substituting 0.0", feat)
            numeric_vals.append(0.0)

    X_numeric = np.array([numeric_vals])
    try:
        X_numeric_scaled = scaler.transform(X_numeric)
    except Exception:
        logger.warning("Scaler not fitted; returning raw numeric values")
        X_numeric_scaled = X_numeric

    # Encode protocol
    proto = str(flow.get("protocol", "UNKNOWN")).upper()
    try:
        proto_encoded = encoder.transform([proto])[0]
    except ValueError:
        # Unseen protocol — default to 0
        logger.warning("Unknown protocol '%s'; encoding as 0", proto)
        proto_encoded = 0

    X = np.hstack([X_numeric_scaled, [[proto_encoded]]])
    return X


def transform_batch(df: pd.DataFrame) -> np.ndarray:
    """Transform a batch dataframe using persisted artifacts."""
    scaler, encoder = _load_or_create_artifacts()
    df = _clean(df)

    df["protocol_encoded"] = df["protocol"].apply(
        lambda p: _safe_encode(encoder, str(p).upper())
    )

    X_numeric = df[NUMERIC_FEATURES].values
    try:
        X_numeric_scaled = scaler.transform(X_numeric)
    except Exception:
        X_numeric_scaled = X_numeric

    X = np.hstack([X_numeric_scaled, df[["protocol_encoded"]].values])
    return X


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce types, fill missing values, rename columns for consistency."""
    df = df.copy()

    # Normalise column names (Zeek uses src_ip/dst_ip; dataset may vary)
    rename_map = {
        "src_port": "src_port",
        "dst_port": "dst_port",
        "source_port": "src_port",
        "destination_port": "dst_port",
    }
    df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)

    for col in NUMERIC_FEATURES:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    if "protocol" not in df.columns:
        df["protocol"] = "UNKNOWN"
    df["protocol"] = df["protocol"].fillna("UNKNOWN").astype(str).str.upper()

    if TARGET_COLUMN in df.columns:
        df[TARGET_COLUMN] = pd.to_numeric(df[TARGET_COLUMN], errors="coerce").fillna(0).astype(int)

    return df


def _safe_encode(encoder: LabelEncoder, value: str) -> int:
    try:
        return int(encoder.transform([value])[0])
    except ValueError:
        return 0
