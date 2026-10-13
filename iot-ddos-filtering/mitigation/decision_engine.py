"""
mitigation/decision_engine.py
==============================
Decision engine for the IoT DDoS filtering system.

Logic
-----
  NORMAL  → ALLOW  (no action)
  DDOS    → evaluate conditions:
            if confidence >= DETECTION_THRESHOLD
               [and optionally packet_rate >= MIN_PACKET_RATE_THRESHOLD]
            then → MITIGATE (create alert, install block rule, record action)
            else → WARN (log low-confidence detection, skip blocking)

The engine does NOT pretend to be "adaptive AI".
It applies a clear, configurable threshold-based policy.
"""

import logging
from typing import Any, Dict

import config
from database.models import MitigationAction, SystemEvent
from database.repository import insert_mitigation_action, log_system_event
from mitigation.rule_manager import install_block_rule

logger = logging.getLogger(__name__)
security_logger = logging.getLogger("SECURITY")


class DecisionEngine:
    """
    Evaluates ML predictions and decides whether to mitigate.

    Parameters
    ----------
    threshold       : Minimum confidence for automatic mitigation.
    min_packet_rate : Optional secondary check on packet rate.
    mitigation_enabled : Whether actual/simulated blocking occurs.
    """

    def __init__(
        self,
        threshold: float = config.DETECTION_THRESHOLD,
        min_packet_rate: float = config.MIN_PACKET_RATE_THRESHOLD,
        mitigation_enabled: bool = config.MITIGATION_ENABLED,
    ) -> None:
        self.threshold = threshold
        self.min_packet_rate = 1000.0  # Automatic mitigation applies to high-rate floods >= 1000 pkts/s
        self.mitigation_enabled = mitigation_enabled

    def evaluate(
        self,
        source_ip: str,
        prediction_result: Dict[str, Any],
        flow_features: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Decide and act on a prediction result.

        Parameters
        ----------
        source_ip         : Source IP of the suspicious flow.
        prediction_result : Output dict from ml.predict.predict_single().
        flow_features     : Extracted feature dict for additional checks.

        Returns
        -------
        Decision dict with keys: decision, action_taken, reason, result.
        """
        prediction = prediction_result.get("prediction", "NORMAL")
        confidence = float(prediction_result.get("confidence", 0.0))
        packet_rate = float(flow_features.get("packet_rate", 0.0))

        if prediction != "DDOS":
            return {"decision": "ALLOW", "action_taken": None, "reason": "Normal traffic"}

        # Check confidence threshold
        if confidence < self.threshold:
            logger.warning(
                "Low-confidence DDoS prediction for src=%s "
                "(confidence=%.2f < threshold=%.2f) — not mitigating",
                source_ip, confidence, self.threshold,
            )
            log_system_event(SystemEvent(
                event_type="LOW_CONFIDENCE_DETECTION",
                severity="WARNING",
                message=f"DDoS prediction confidence {confidence:.2f} below threshold {self.threshold} for {source_ip}",
            ))
            return {
                "decision": "WARN",
                "action_taken": None,
                "reason": f"Confidence {confidence:.2f} below threshold {self.threshold}",
            }

        # Optional packet-rate sanity check
        if self.min_packet_rate > 0 and packet_rate < self.min_packet_rate:
            logger.warning(
                "DDoS predicted but packet_rate=%.1f < min_threshold=%.1f for src=%s — skipping",
                packet_rate, self.min_packet_rate, source_ip,
            )
            return {
                "decision": "WARN",
                "action_taken": None,
                "reason": f"packet_rate {packet_rate:.1f} below minimum threshold {self.min_packet_rate}",
            }

        # --- Mitigate ---
        security_logger.warning(
            "SECURITY: DDoS MITIGATING — src=%s confidence=%.2f packet_rate=%.1f",
            source_ip, confidence, packet_rate,
        )

        action_result = None
        success = False
        simulated = True

        if self.mitigation_enabled:
            action_result = install_block_rule(source_ip)
            success = bool(action_result.get("success", False))
            simulated = bool(action_result.get("simulated", True))

            # Persist mitigation record
            ma = MitigationAction(
                source_ip=source_ip,
                action="BLOCK",
                rule_id=action_result.get("rule_id"),
                reason=f"DDoS detected (confidence={confidence:.2f})",
                success=success,
                simulated=simulated,
            )
            insert_mitigation_action(ma)

            # Update device status in database to blocked
            try:
                from database.db import get_connection
                conn = get_connection()
                conn.execute(
                    "UPDATE devices SET status = 'blocked', last_seen = datetime('now') WHERE ip_address = ?",
                    (source_ip,)
                )
                conn.commit()
            except Exception as e:
                logger.debug("Device status block update skipped: %s", e)

            security_logger.warning(
                "SECURITY: Block rule installed for src=%s (simulated=%s, success=%s)",
                source_ip, simulated, success,
            )
        else:
            logger.info(
                "Mitigation DISABLED — DDoS detected from %s but no action taken", source_ip
            )

        return {
            "decision": "MITIGATE",
            "action_taken": "BLOCK",
            "reason": f"DDoS detected (confidence={confidence:.2f}, packet_rate={packet_rate:.1f})",
            "mitigation_result": action_result,
            "simulated": simulated,
        }
