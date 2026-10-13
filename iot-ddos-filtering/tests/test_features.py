"""
tests/test_features.py
=======================
Unit tests for feature extraction and preprocessing.
No external network required.
"""

import pytest
from monitoring.feature_extractor import extract_features, validate_features
from ml.preprocess import _clean
import pandas as pd


class TestExtractFeatures:
    def test_normal_flow(self):
        raw = {
            "source_ip": "10.0.0.1",
            "destination_ip": "192.168.1.1",
            "source_port": 50001,
            "destination_port": 1883,
            "protocol": "TCP",
            "duration": 5.0,
            "packet_count": 20,
            "byte_count": 3200,
        }
        f = extract_features(raw)
        assert f["source_ip"] == "10.0.0.1"
        assert f["protocol"] == "TCP"
        assert f["duration"] == 5.0
        assert f["packet_rate"] == pytest.approx(20 / 5.0, rel=1e-3)
        assert f["byte_rate"] == pytest.approx(3200 / 5.0, rel=1e-3)
        assert f["avg_packet_size"] == pytest.approx(3200 / 20, rel=1e-3)

    def test_port_aliasing(self):
        raw = {"src_port": 1234, "dst_port": 80, "duration": 1.0, "packet_count": 5,
               "byte_count": 500, "source_ip": "10.0.0.1", "destination_ip": "1.1.1.1"}
        f = extract_features(raw)
        assert f["src_port"] == 1234
        assert f["dst_port"] == 80

    def test_missing_fields_default_to_zero(self):
        raw = {"source_ip": "10.0.0.1", "destination_ip": "10.0.0.2"}
        f = extract_features(raw)
        assert f["packet_count"] == 0
        assert f["byte_count"] == 0
        assert f["duration"] == 0.001  # minimum safe duration

    def test_zero_duration_clamped(self):
        raw = {"duration": 0.0, "packet_count": 10, "byte_count": 1000,
               "source_ip": "x", "destination_ip": "y"}
        f = extract_features(raw)
        assert f["duration"] > 0

    def test_protocol_uppercase(self):
        raw = {"protocol": "udp", "source_ip": "a", "destination_ip": "b",
               "duration": 1.0, "packet_count": 1, "byte_count": 64}
        f = extract_features(raw)
        assert f["protocol"] == "UDP"


class TestValidateFeatures:
    def test_valid_features_pass(self):
        raw = {
            "source_ip": "10.0.0.1", "destination_ip": "10.0.0.2",
            "duration": 1.0, "packet_count": 10, "byte_count": 640,
        }
        f = extract_features(raw)
        err = validate_features(f)
        assert err is None

    def test_negative_packet_rate_rejected(self):
        f = {
            "duration": 1.0, "packet_count": 10, "byte_count": 640,
            "packet_rate": -5.0, "byte_rate": 640.0, "avg_packet_size": 64.0,
        }
        err = validate_features(f)
        assert err is not None
        assert "negative" in err.lower()


class TestPreprocessClean:
    def test_clean_renames_columns(self):
        df = pd.DataFrame([{"source_port": 80, "destination_port": 443,
                             "duration": 1.0, "packet_count": 5,
                             "byte_count": 320, "protocol": "TCP"}])
        cleaned = _clean(df)
        assert "src_port" in cleaned.columns
        assert "dst_port" in cleaned.columns

    def test_clean_fills_missing_numeric(self):
        df = pd.DataFrame([{"duration": None, "packet_count": "abc",
                             "protocol": "UDP"}])
        cleaned = _clean(df)
        assert cleaned["duration"].iloc[0] == 0.0
        assert cleaned["packet_count"].iloc[0] == 0.0

    def test_clean_protocol_uppercase(self):
        df = pd.DataFrame([{"protocol": "tcp", "duration": 1.0,
                             "packet_count": 5, "byte_count": 320}])
        cleaned = _clean(df)
        assert cleaned["protocol"].iloc[0] == "TCP"
