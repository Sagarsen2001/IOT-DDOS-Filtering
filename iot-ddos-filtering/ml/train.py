"""
ml/train.py
===========
Training entry-point.

Usage
-----
    python -m ml.train                 # use dataset at config.DATASET_PATH
    python -m ml.train --dataset /path/to/data.csv
"""

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
from sklearn.model_selection import train_test_split

import config
from database.db import init_db
from ml.dataset import generate_dataset, load_dataset
from ml.evaluate import evaluate, save_metrics
from ml.model import build_classifier, save_model
from ml.preprocess import fit_and_save

config.configure_logging()
logger = logging.getLogger(__name__)


def train(dataset_path: str = config.DATASET_PATH) -> dict:
    """
    Full training pipeline:
      1. Load (or generate) dataset.
      2. Preprocess & fit scaler/encoder.
      3. Train RandomForest.
      4. Evaluate on held-out test split.
      5. Save model + metrics.

    Returns
    -------
    Evaluation metrics dict.
    """
    logger.info("=== Starting ML Training Pipeline ===")

    # 1. Load dataset (auto-generate if missing)
    if not Path(dataset_path).exists():
        logger.warning("Dataset not found — generating synthetic dataset …")
        generate_dataset(output_path=dataset_path)

    df = load_dataset(dataset_path)
    logger.info("Dataset: %d rows, label distribution:\n%s", len(df), df["label"].value_counts().to_dict())

    # 2. Preprocess (fit scaler & encoder, persist artifacts)
    X, y = fit_and_save(df)

    # 3. Stratified train/test split (80/20)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=config.RANDOM_SEED
    )
    logger.info("Train: %d samples | Test: %d samples", len(X_train), len(X_test))

    # 4. Train
    clf = build_classifier()
    clf.fit(X_train, y_train)
    logger.info("Training complete (n_estimators=%d)", clf.n_estimators)

    # 5. Evaluate
    y_pred = clf.predict(X_test)
    y_prob = clf.predict_proba(X_test)[:, 1]
    metrics = evaluate(y_test, y_pred, y_prob)

    # 6. Save
    save_model(clf)
    save_metrics(metrics)

    logger.info("=== Training Pipeline Finished ===")
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train the DDoS detection model")
    parser.add_argument("--dataset", default=config.DATASET_PATH, help="Path to CSV dataset")
    args = parser.parse_args()

    # Initialise DB so evaluate.py can persist metrics
    init_db()
    result = train(args.dataset)
    print("\n=== Evaluation Results ===")
    for k, v in result.items():
        print(f"  {k}: {v}")
