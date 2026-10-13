"""
monitoring/traffic_monitor.py
==============================
Background monitoring service.

Runs a daemon thread that periodically:
  1. Reads flows (Zeek or synthetic).
  2. Extracts features.
  3. Sends each flow to the ML predictor.
  4. Stores flows and predictions in the database.
  5. Creates alerts for DDOS predictions.
  6. Passes suspicious sources to the decision engine.

The monitor is designed to be started once at Flask startup and run
continuously in the background without blocking request handlers.
"""

import logging
import threading
import time
from typing import Any, Dict, Optional

import config
from database.models import Alert, Prediction, SystemEvent, TrafficFlow
from database.repository import (
    insert_alert, insert_prediction, insert_traffic_flow, log_system_event,
)
from mitigation.decision_engine import DecisionEngine
from ml.predict import predict_single, is_model_loaded
from monitoring.feature_extractor import extract_features, validate_features
from monitoring.zeek_parser import get_flows

logger = logging.getLogger(__name__)

# Security event logger for DDoS events
security_logger = logging.getLogger("SECURITY")


class TrafficMonitor:
    """
    Daemon thread that monitors traffic flows and triggers alerts/mitigation.

    Usage
    -----
        monitor = TrafficMonitor()
        monitor.start()
        …
        monitor.stop()
    """

    def __init__(
        self,
        interval: float = config.MONITOR_INTERVAL_SECONDS,
        demo_mode: bool = config.DEMO_MODE,
    ) -> None:
        self.interval = interval
        self.demo_mode = demo_mode
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._decision_engine = DecisionEngine()
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Start the background monitoring thread."""
        if self._running:
            logger.warning("TrafficMonitor is already running")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="TrafficMonitor",
            daemon=True,
        )
        self._thread.start()
        self._running = True
        logger.info(
            "TrafficMonitor started (interval=%.1fs, demo=%s)",
            self.interval, self.demo_mode,
        )
        log_system_event(SystemEvent(
            event_type="MONITOR_STARTED",
            message=f"TrafficMonitor started (demo_mode={self.demo_mode})",
        ))

    def stop(self) -> None:
        """Signal the background thread to stop cleanly."""
        self._stop_event.set()
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        logger.info("TrafficMonitor stopped")

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._process_batch()
            except Exception as exc:
                logger.error("Unexpected error in monitoring loop: %s", exc, exc_info=True)
            self._stop_event.wait(timeout=self.interval)

    def _process_batch(self) -> None:
        """Fetch flows, run inference, store results, trigger mitigation."""
        if not is_model_loaded():
            logger.warning("ML model not loaded — skipping monitoring cycle")
            return

        raw_flows = get_flows(demo_mode=self.demo_mode)
        if not raw_flows:
            logger.debug("No flows returned in this monitoring cycle")
            return

        for raw_flow in raw_flows:
            self._process_flow(raw_flow)

    def _process_flow(self, raw_flow: Dict[str, Any]) -> None:
        """Process a single flow through the full pipeline."""
        try:
            features = extract_features(raw_flow)
        except Exception as exc:
            logger.warning("Feature extraction failed: %s", exc)
            return

        error = validate_features(features)
        if error:
            logger.warning("Feature validation failed: %s", error)
            return

        # --- Persist the flow ---
        flow_record = TrafficFlow(
            source_ip=features["source_ip"],
            destination_ip=features["destination_ip"],
            source_port=features.get("src_port"),
            destination_port=features.get("dst_port"),
            protocol=features.get("protocol"),
            duration=features.get("duration"),
            packet_count=features.get("packet_count"),
            byte_count=features.get("byte_count"),
            packet_rate=features.get("packet_rate"),
            byte_rate=features.get("byte_rate"),
            avg_packet_size=features.get("avg_packet_size"),
            timestamp=features.get("timestamp"),
        )
        flow_id = insert_traffic_flow(flow_record)

        # --- ML Prediction ---
        result = predict_single(features)
        if "error" in result:
            logger.error("Prediction failed for flow %d: %s", flow_id, result["error"])
            return

        pred = Prediction(
            traffic_flow_id=flow_id,
            prediction=result["prediction"],
            probability=result["probability"],
            confidence=result["confidence"],
        )
        insert_prediction(pred)

        # --- Alert & mitigation for DDOS ---
        if result["prediction"] == "DDOS":
            src_ip = features["source_ip"]
            security_logger.warning(
                "DDoS detected — src=%s confidence=%.2f probability=%.2f",
                src_ip, result["confidence"], result["probability"],
            )

            alert = Alert(
                source_ip=src_ip,
                alert_type="DDOS_DETECTED",
                severity="HIGH",
                message=(
                    f"DDoS-like traffic from {src_ip} "
                    f"(confidence={result['confidence']:.2f}, "
                    f"packet_rate={features.get('packet_rate', 'N/A')})"
                ),
            )
            insert_alert(alert)

            # Update device status in database if known
            try:
                from database.db import get_connection
                conn = get_connection()
                conn.execute(
                    "UPDATE devices SET status = 'suspicious', last_seen = datetime('now') WHERE ip_address = ? AND status != 'blocked'",
                    (src_ip,)
                )
                conn.commit()
            except Exception as e:
                logger.debug("Device status update skipped: %s", e)
        elif float(features.get("packet_rate", 0)) > 70 and features.get("source_ip"):
            try:
                from database.db import get_connection
                conn = get_connection()
                conn.execute(
                    "UPDATE devices SET status = 'suspicious', last_seen = datetime('now') WHERE ip_address = ? AND status = 'active'",
                    (features["source_ip"],)
                )
                conn.commit()
            except Exception as e:
                logger.debug("Device anomalous update skipped: %s", e)

            # Decision engine decides whether to mitigate
            self._decision_engine.evaluate(
                source_ip=src_ip,
                prediction_result=result,
                flow_features=features,
            )
