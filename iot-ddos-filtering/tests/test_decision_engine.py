"""
tests/test_decision_engine.py
==============================
Unit tests for the decision engine.
All mitigation calls are intercepted — no real OVS/Ryu calls.
"""

import pytest
from unittest.mock import patch, MagicMock
from mitigation.decision_engine import DecisionEngine


@pytest.fixture
def engine():
    return DecisionEngine(
        threshold=0.70,
        min_packet_rate=100.0,
        mitigation_enabled=True,
    )


DDOS_HIGH_CONFIDENCE = {
    "prediction": "DDOS",
    "label": 1,
    "probability": 0.97,
    "confidence": 0.97,
}

DDOS_LOW_CONFIDENCE = {
    "prediction": "DDOS",
    "label": 1,
    "probability": 0.5,
    "confidence": 0.5,
}

NORMAL_RESULT = {
    "prediction": "NORMAL",
    "label": 0,
    "probability": 0.03,
    "confidence": 0.97,
}

HIGH_RATE_FLOW = {"packet_rate": 5000.0, "source_ip": "10.0.0.1"}
LOW_RATE_FLOW = {"packet_rate": 5.0, "source_ip": "10.0.0.1"}


class TestDecisionEngine:
    def test_normal_traffic_is_allowed(self, engine):
        decision = engine.evaluate("10.0.0.1", NORMAL_RESULT, HIGH_RATE_FLOW)
        assert decision["decision"] == "ALLOW"
        assert decision["action_taken"] is None

    def test_high_confidence_ddos_triggers_mitigation(self, engine):
        with patch("mitigation.decision_engine.install_block_rule") as mock_block, \
             patch("mitigation.decision_engine.insert_mitigation_action"):
            mock_block.return_value = {"success": True, "simulated": True, "rule_id": "r1"}
            decision = engine.evaluate("10.0.0.1", DDOS_HIGH_CONFIDENCE, HIGH_RATE_FLOW)
            assert decision["decision"] == "MITIGATE"
            assert decision["action_taken"] == "BLOCK"
            mock_block.assert_called_once_with("10.0.0.1")

    def test_low_confidence_ddos_returns_warn(self, engine):
        with patch("mitigation.decision_engine.insert_mitigation_action"), \
             patch("mitigation.decision_engine.log_system_event"):
            decision = engine.evaluate("10.0.0.2", DDOS_LOW_CONFIDENCE, HIGH_RATE_FLOW)
            assert decision["decision"] == "WARN"
            assert decision["action_taken"] is None

    def test_low_packet_rate_returns_warn(self, engine):
        decision = engine.evaluate("10.0.0.3", DDOS_HIGH_CONFIDENCE, LOW_RATE_FLOW)
        assert decision["decision"] == "WARN"

    def test_mitigation_disabled_skips_block(self):
        engine_no_mit = DecisionEngine(
            threshold=0.70,
            min_packet_rate=0.0,
            mitigation_enabled=False,
        )
        with patch("mitigation.decision_engine.install_block_rule") as mock_block:
            decision = engine_no_mit.evaluate("10.0.0.4", DDOS_HIGH_CONFIDENCE, HIGH_RATE_FLOW)
            assert decision["decision"] == "MITIGATE"
            mock_block.assert_not_called()

    def test_simulated_result_marked_correctly(self, engine):
        with patch("mitigation.decision_engine.install_block_rule") as mock_block, \
             patch("mitigation.decision_engine.insert_mitigation_action"):
            mock_block.return_value = {
                "success": True,
                "simulated": True,
                "rule_id": "sim-rule",
                "message": "Simulated OVS blocking rule",
            }
            decision = engine.evaluate("10.0.0.5", DDOS_HIGH_CONFIDENCE, HIGH_RATE_FLOW)
            assert decision.get("simulated") is True
