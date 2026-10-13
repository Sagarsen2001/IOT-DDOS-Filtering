"""
tests/test_api.py
=================
Flask API integration tests.
Uses Flask's test client — no real server or network required.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

# Patch MQTT connect before importing app to prevent broker connection attempts
with patch("network.mqtt_client.MQTTClient.connect", return_value=False):
    with patch("monitoring.traffic_monitor.TrafficMonitor.start", return_value=None):
        from app import create_app


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmpdir = tmp_path_factory.mktemp("api_test")

    import config
    config.DATABASE_PATH = str(tmpdir / "test.db")
    config.DEMO_MODE = True

    with patch("network.mqtt_client.MQTTClient.connect", return_value=False), \
         patch("monitoring.traffic_monitor.TrafficMonitor.start", return_value=None):
        app = create_app()

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_health_response_structure(self, client):
        resp = client.get("/api/health")
        data = resp.get_json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["status"] == "ok"

    def test_health_has_timestamp(self, client):
        resp = client.get("/api/health")
        data = resp.get_json()
        assert "timestamp" in data


class TestDeviceEndpoints:
    def test_list_devices_returns_200(self, client):
        resp = client.get("/api/devices")
        assert resp.status_code == 200

    def test_register_device_valid(self, client):
        payload = {
            "device_id": "test-device-001",
            "ip_address": "10.0.0.1",
            "mac_address": "aa:bb:cc:dd:ee:ff",
        }
        resp = client.post("/api/devices/register",
                           data=json.dumps(payload),
                           content_type="application/json")
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["success"] is True

    def test_register_device_missing_ip(self, client):
        payload = {"device_id": "dev-002"}
        resp = client.post("/api/devices/register",
                           data=json.dumps(payload),
                           content_type="application/json")
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["success"] is False
        assert data["error"]["code"] == "INVALID_INPUT"

    def test_register_device_invalid_ip(self, client):
        payload = {"device_id": "dev-003", "ip_address": "not-an-ip"}
        resp = client.post("/api/devices/register",
                           data=json.dumps(payload),
                           content_type="application/json")
        assert resp.status_code == 400

    def test_get_unknown_device_returns_404(self, client):
        resp = client.get("/api/devices/nonexistent-device-xyz")
        assert resp.status_code == 404


class TestPredictEndpoint:
    normal_payload = {
        "source_ip": "10.0.0.1",
        "destination_ip": "192.168.1.1",
        "src_port": 50001,
        "dst_port": 1883,
        "protocol": "TCP",
        "duration": 5.0,
        "packet_count": 20,
        "byte_count": 3200,
        "packet_rate": 4.0,
        "byte_rate": 640.0,
        "avg_packet_size": 160.0,
    }

    def test_predict_without_model_returns_503(self, client):
        with patch("api.routes_detection.is_model_loaded", return_value=False):
            resp = client.post("/api/predict",
                               data=json.dumps(self.normal_payload),
                               content_type="application/json")
            assert resp.status_code == 503
            data = resp.get_json()
            assert data["error"]["code"] == "MODEL_NOT_LOADED"

    def test_predict_missing_body_returns_400(self, client):
        with patch("api.routes_detection.is_model_loaded", return_value=True):
            resp = client.post("/api/predict",
                               data="not json",
                               content_type="application/json")
            assert resp.status_code == 400

    def test_predict_returns_correct_structure(self, client):
        mock_result = {
            "prediction": "NORMAL",
            "label": 0,
            "probability": 0.03,
            "confidence": 0.97,
            "model_version": "rf-v1",
            "timestamp": "2024-01-01T00:00:00+00:00",
        }
        with patch("api.routes_detection.is_model_loaded", return_value=True), \
             patch("api.routes_detection.predict_single", return_value=mock_result), \
             patch("api.routes_detection.insert_traffic_flow", return_value=1), \
             patch("api.routes_detection.insert_prediction", return_value=1):
            resp = client.post("/api/predict",
                               data=json.dumps(self.normal_payload),
                               content_type="application/json")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True
            assert data["data"]["prediction"] == "NORMAL"


class TestMitigateEndpoint:
    def test_mitigate_missing_ip_returns_400(self, client):
        resp = client.post("/api/mitigate",
                           data=json.dumps({}),
                           content_type="application/json")
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"]["code"] == "INVALID_INPUT"

    def test_mitigate_invalid_ip_returns_400(self, client):
        resp = client.post("/api/mitigate",
                           data=json.dumps({"source_ip": "not-an-ip"}),
                           content_type="application/json")
        assert resp.status_code == 400

    def test_mitigate_valid_ip_demo_mode(self, client):
        mock_result = {
            "success": True, "simulated": True,
            "action": "BLOCK", "source_ip": "10.0.0.4",
            "message": "Simulated OVS blocking rule",
        }
        with patch("api.routes_control.install_block_rule", return_value=mock_result), \
             patch("api.routes_control.insert_mitigation_action", return_value=1):
            resp = client.post("/api/mitigate",
                               data=json.dumps({"source_ip": "10.0.0.4"}),
                               content_type="application/json")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True
            assert data["data"]["simulated"] is True


class TestTrafficEndpoint:
    def test_traffic_returns_200(self, client):
        resp = client.get("/api/traffic")
        assert resp.status_code == 200

    def test_traffic_invalid_prediction_filter(self, client):
        resp = client.get("/api/traffic?prediction=INVALID")
        assert resp.status_code == 400

    def test_traffic_invalid_limit(self, client):
        resp = client.get("/api/traffic?limit=abc")
        assert resp.status_code == 400


class TestErrorFormat:
    def test_error_has_code_and_message(self, client):
        resp = client.post("/api/mitigate",
                           data=json.dumps({}),
                           content_type="application/json")
        data = resp.get_json()
        assert "code" in data["error"]
        assert "message" in data["error"]
