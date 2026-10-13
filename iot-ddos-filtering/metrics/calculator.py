"""
metrics/calculator.py
======================
Security and network metrics calculator.

Returns a single dict suitable for the /api/metrics endpoint.

HONESTY POLICY
--------------
If a metric cannot be computed from available data, it returns None
(serialised as null in JSON). We NEVER fabricate measurements.

ML Metrics       — loaded from the last saved evaluation run.
Network Metrics  — derived from the traffic_flows table.
Security Metrics — derived from alerts, mitigation_actions, predictions tables.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from database.db import get_connection
from ml.evaluate import load_metrics

logger = logging.getLogger(__name__)


def _query_scalar(sql: str, params: tuple = ()) -> Optional[float]:
    """Run a scalar SQL query and return the first column of the first row."""
    try:
        conn = get_connection()
        row = conn.execute(sql, params).fetchone()
        if row is None:
            return None
        val = row[0]
        return float(val) if val is not None else None
    except Exception as exc:
        logger.error("Metric query failed: %s | SQL: %s", exc, sql)
        return None


def get_metrics() -> Dict[str, Any]:
    """
    Compute and return all system metrics.

    Returns
    -------
    dict with sections: ml, network, security, timestamp.
    """
    ml_section = _ml_metrics()
    network_section = _network_metrics()
    security_section = _security_metrics()

    return {
        "ml": ml_section,
        "network": network_section,
        "security": security_section,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# ML Metrics
# ---------------------------------------------------------------------------

def _ml_metrics() -> Dict[str, Any]:
    """Load saved evaluation metrics from the last training run."""
    saved = load_metrics()
    if not saved:
        logger.debug("No saved ML metrics found")
        return {
            "accuracy": None,
            "precision": None,
            "recall": None,
            "f1_score": None,
            "false_positive_rate": None,
            "true_positive_rate": None,
            "model_version": None,
            "note": "No evaluation results yet — train the model first",
        }
    return {
        "accuracy": saved.get("accuracy"),
        "precision": saved.get("precision"),
        "recall": saved.get("recall"),
        "f1_score": saved.get("f1_score"),
        "false_positive_rate": saved.get("false_positive_rate"),
        "true_positive_rate": saved.get("true_positive_rate"),
        "model_version": saved.get("model_version"),
        "confusion_matrix": saved.get("confusion_matrix"),
    }


# ---------------------------------------------------------------------------
# Network Metrics
# ---------------------------------------------------------------------------

def _network_metrics() -> Dict[str, Any]:
    """Compute network-level metrics from stored flow records."""
    # Throughput: average byte_rate across all stored flows
    avg_byte_rate = _query_scalar(
        "SELECT AVG(byte_rate) FROM traffic_flows WHERE byte_rate IS NOT NULL"
    )
    # Average latency proxy: average flow duration
    avg_duration = _query_scalar(
        "SELECT AVG(duration) FROM traffic_flows WHERE duration IS NOT NULL"
    )
    # Total flows stored
    total_flows = _query_scalar("SELECT COUNT(*) FROM traffic_flows")

    return {
        "average_throughput_bps": round(avg_byte_rate, 2) if avg_byte_rate is not None else None,
        "average_flow_duration_s": round(avg_duration, 4) if avg_duration is not None else None,
        "total_flows_recorded": int(total_flows) if total_flows is not None else 0,
        # Packet loss and real latency require active measurement probes —
        # not available from stored flows.
        "packet_loss_pct": None,
        "latency_ms": None,
        "note_packet_loss": "Requires active probe — not available from stored flows",
    }


# ---------------------------------------------------------------------------
# Security Metrics
# ---------------------------------------------------------------------------

def _security_metrics() -> Dict[str, Any]:
    """Compute security-level metrics from alerts and mitigation actions."""
    total_alerts = _query_scalar("SELECT COUNT(*) FROM alerts") or 0
    total_ddos_detected = _query_scalar(
        "SELECT COUNT(*) FROM predictions WHERE prediction = 'DDOS'"
    ) or 0
    total_normal = _query_scalar(
        "SELECT COUNT(*) FROM predictions WHERE prediction = 'NORMAL'"
    ) or 0
    total_mitigations = _query_scalar("SELECT COUNT(*) FROM mitigation_actions") or 0
    successful_blocks = _query_scalar(
        "SELECT COUNT(*) FROM mitigation_actions WHERE success = 1"
    ) or 0
    unique_malicious_sources = _query_scalar(
        "SELECT COUNT(DISTINCT source_ip) FROM alerts"
    ) or 0
    unique_blocked = _query_scalar(
        "SELECT COUNT(DISTINCT source_ip) FROM mitigation_actions WHERE action = 'BLOCK'"
    ) or 0

    # False positives: predictions labelled DDOS but flow label was 0 (NORMAL)
    # Only available if ground-truth labels are stored in traffic_flows
    fp_count = _query_scalar(
        """
        SELECT COUNT(*) FROM predictions p
        JOIN traffic_flows tf ON tf.id = p.traffic_flow_id
        WHERE p.prediction = 'DDOS' AND tf.label = '0'
        """
    ) or 0

    # Average detection time: time from flow timestamp to predicted_at
    avg_detection_time = _query_scalar(
        """
        SELECT AVG(
            (julianday(p.predicted_at) - julianday(tf.timestamp)) * 86400.0
        )
        FROM predictions p
        JOIN traffic_flows tf ON tf.id = p.traffic_flow_id
        WHERE tf.timestamp IS NOT NULL
        """
    )

    return {
        "total_alerts": int(total_alerts),
        "total_ddos_detected": int(total_ddos_detected),
        "total_normal_detected": int(total_normal),
        "total_mitigations": int(total_mitigations),
        "successful_blocks": int(successful_blocks),
        "unique_malicious_sources": int(unique_malicious_sources),
        "unique_blocked_devices": int(unique_blocked),
        "false_positives_from_labelled_flows": int(fp_count),
        "average_detection_time_s": (
            round(avg_detection_time, 3) if avg_detection_time is not None else None
        ),
        "average_mitigation_time_s": None,   # Requires timing instrumentation
        "note_mitigation_time": "Mitigation timing not yet instrumented",
    }
