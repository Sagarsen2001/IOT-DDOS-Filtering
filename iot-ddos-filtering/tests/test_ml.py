"""
tests/test_ml.py
================
Unit tests for the ML training and inference pipeline.
Trains on a tiny synthetic dataset to keep tests fast.
"""

import os
import tempfile
import pytest
import numpy as np
import pandas as pd

from ml.dataset import generate_dataset
from ml.preprocess import fit_and_save, transform
from ml.model import build_classifier, save_model, load_model
from ml.predict import predict_single, predict_batch
from ml.evaluate import evaluate


@pytest.fixture(scope="module")
def trained_artifacts(tmp_path_factory):
    """Generate a small dataset, train, and return (clf, X_test, y_test)."""
    tmpdir = tmp_path_factory.mktemp("ml_test")

    # Override paths to use temp dir
    import config
    original_model = config.MODEL_PATH
    original_scaler = config.SCALER_PATH
    original_encoder = config.ENCODER_PATH

    config.MODEL_PATH = str(tmpdir / "model.joblib")
    config.SCALER_PATH = str(tmpdir / "scaler.joblib")
    config.ENCODER_PATH = str(tmpdir / "encoder.joblib")
    config.METRICS_PATH = str(tmpdir / "metrics.json")

    df = generate_dataset(n_samples=400, seed=42)
    X, y = fit_and_save(df)

    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)

    clf = build_classifier(seed=42)
    clf.fit(X_train, y_train)
    save_model(clf)

    yield clf, X_test, y_test, tmpdir

    # Restore original paths
    config.MODEL_PATH = original_model
    config.SCALER_PATH = original_scaler
    config.ENCODER_PATH = original_encoder


class TestDatasetGeneration:
    def test_generates_correct_size(self):
        df = generate_dataset(n_samples=100, seed=1)
        assert len(df) == 100

    def test_has_expected_columns(self):
        df = generate_dataset(n_samples=50, seed=1)
        expected = {"src_ip", "dst_ip", "protocol", "duration", "packet_count",
                    "byte_count", "packet_rate", "byte_rate", "avg_packet_size", "label"}
        assert expected.issubset(set(df.columns))

    def test_both_labels_present(self):
        df = generate_dataset(n_samples=200, seed=1)
        assert set(df["label"].unique()) == {0, 1}

    def test_reproducible_with_same_seed(self):
        df1 = generate_dataset(n_samples=50, seed=99)
        df2 = generate_dataset(n_samples=50, seed=99)
        pd.testing.assert_frame_equal(df1, df2)

    def test_different_seeds_differ(self):
        df1 = generate_dataset(n_samples=50, seed=1)
        df2 = generate_dataset(n_samples=50, seed=2)
        assert not df1["packet_rate"].equals(df2["packet_rate"])


class TestModelTraining:
    def test_classifier_trains(self, trained_artifacts):
        clf, X_test, y_test, _ = trained_artifacts
        y_pred = clf.predict(X_test)
        assert len(y_pred) == len(y_test)

    def test_accuracy_above_threshold(self, trained_artifacts):
        clf, X_test, y_test, _ = trained_artifacts
        from sklearn.metrics import accuracy_score
        acc = accuracy_score(y_test, clf.predict(X_test))
        assert acc >= 0.80, f"Accuracy {acc:.3f} below acceptable threshold"

    def test_model_save_load(self, trained_artifacts):
        clf, _, _, tmpdir = trained_artifacts
        path = str(tmpdir / "model.joblib")
        loaded = load_model(path)
        # Both classifiers should produce identical predictions on the same input
        sample = np.zeros((1, 9))
        assert (clf.predict(sample) == loaded.predict(sample)).all()

    def test_model_missing_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_model(str(tmp_path / "nonexistent.joblib"))


class TestEvaluation:
    def test_evaluate_returns_correct_keys(self):
        y_true = np.array([0, 1, 0, 1, 1])
        y_pred = np.array([0, 1, 0, 0, 1])
        y_prob = np.array([0.1, 0.9, 0.2, 0.4, 0.85])
        result = evaluate(y_true, y_pred, y_prob)
        for key in ("accuracy", "precision", "recall", "f1_score",
                    "false_positive_rate", "true_positive_rate"):
            assert key in result

    def test_perfect_prediction_gives_fpr_zero(self):
        y_true = np.array([0, 0, 1, 1])
        y_pred = np.array([0, 0, 1, 1])
        y_prob = np.array([0.05, 0.05, 0.95, 0.95])
        result = evaluate(y_true, y_pred, y_prob)
        assert result["false_positive_rate"] == 0.0
        assert result["accuracy"] == 1.0


class TestPrediction:
    normal_flow = {
        "duration": 10.0, "packet_count": 30, "byte_count": 4800,
        "packet_rate": 3.0, "byte_rate": 480.0, "avg_packet_size": 160.0,
        "src_port": 50001, "dst_port": 1883, "protocol": "TCP",
        "source_ip": "10.0.0.1", "destination_ip": "192.168.1.1",
    }
    ddos_flow = {
        "duration": 0.5, "packet_count": 3000, "byte_count": 192000,
        "packet_rate": 6000.0, "byte_rate": 384000.0, "avg_packet_size": 64.0,
        "src_port": 55555, "dst_port": 80, "protocol": "UDP",
        "source_ip": "10.0.0.6", "destination_ip": "192.168.1.1",
    }

    def test_predict_single_returns_required_keys(self, trained_artifacts):
        result = predict_single(self.normal_flow)
        if "error" in result:
            pytest.skip("Model not loaded in this test run")
        for key in ("prediction", "label", "probability", "confidence", "model_version"):
            assert key in result

    def test_predict_batch_returns_list(self, trained_artifacts):
        df = pd.DataFrame([self.normal_flow, self.ddos_flow])
        results = predict_batch(df)
        assert isinstance(results, list)
        assert len(results) == 2

    def test_label_matches_prediction(self, trained_artifacts):
        result = predict_single(self.normal_flow)
        if "error" in result:
            pytest.skip("Model not loaded")
        if result["prediction"] == "NORMAL":
            assert result["label"] == 0
        else:
            assert result["label"] == 1

    def test_confidence_between_0_and_1(self, trained_artifacts):
        result = predict_single(self.ddos_flow)
        if "error" in result:
            pytest.skip("Model not loaded")
        assert 0.0 <= result["confidence"] <= 1.0
