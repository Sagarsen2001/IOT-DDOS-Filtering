"""
database/repository.py
======================
All database access is centralised here.
Flask routes and services must NOT write raw SQL — they call these functions.
"""

import sqlite3
import logging
from typing import Any, Dict, List, Optional

from database.db import get_connection
from database.models import (
    Alert, Device, EvaluationMetrics, MitigationAction, Prediction,
    SystemEvent, TrafficFlow,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return dict(row) if row else {}


def _rows_to_list(rows) -> List[Dict[str, Any]]:
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------

def upsert_device(device: Device) -> int:
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO devices (device_id, ip_address, mac_address, status, last_seen)
        VALUES (:device_id, :ip_address, :mac_address, :status, datetime('now'))
        ON CONFLICT(device_id) DO UPDATE SET
            ip_address  = excluded.ip_address,
            mac_address = excluded.mac_address,
            status      = excluded.status,
            last_seen   = datetime('now')
        """,
        {
            "device_id": device.device_id,
            "ip_address": device.ip_address,
            "mac_address": device.mac_address,
            "status": device.status,
        },
    )
    conn.commit()
    return cursor.lastrowid or 0


def get_all_devices() -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM devices ORDER BY created_at DESC").fetchall()
    return _rows_to_list(rows)


def get_device_by_id(device_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM devices WHERE device_id = ?", (device_id,)
    ).fetchone()
    return _row_to_dict(row) if row else None


# ---------------------------------------------------------------------------
# Traffic Flows
# ---------------------------------------------------------------------------

def insert_traffic_flow(flow: TrafficFlow) -> int:
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO traffic_flows
            (timestamp, source_ip, destination_ip, source_port, destination_port,
             protocol, duration, packet_count, byte_count,
             packet_rate, byte_rate, avg_packet_size, label)
        VALUES
            (COALESCE(:timestamp, datetime('now')),
             :source_ip, :destination_ip, :source_port, :destination_port,
             :protocol, :duration, :packet_count, :byte_count,
             :packet_rate, :byte_rate, :avg_packet_size, :label)
        """,
        {
            "timestamp": flow.timestamp,
            "source_ip": flow.source_ip,
            "destination_ip": flow.destination_ip,
            "source_port": flow.source_port,
            "destination_port": flow.destination_port,
            "protocol": flow.protocol,
            "duration": flow.duration,
            "packet_count": flow.packet_count,
            "byte_count": flow.byte_count,
            "packet_rate": flow.packet_rate,
            "byte_rate": flow.byte_rate,
            "avg_packet_size": flow.avg_packet_size,
            "label": flow.label,
        },
    )
    conn.commit()
    return cursor.lastrowid or 0


def get_traffic_flows(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    source_ip: Optional[str] = None,
    prediction: Optional[str] = None,
    label: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    conn = get_connection()
    conditions: List[str] = []
    params: List[Any] = []

    if start_time:
        conditions.append("tf.timestamp >= ?")
        params.append(start_time)
    if end_time:
        conditions.append("tf.timestamp <= ?")
        params.append(end_time)
    if source_ip:
        conditions.append("tf.source_ip = ?")
        params.append(source_ip)
    if label:
        conditions.append("tf.label = ?")
        params.append(label)
    if prediction:
        conditions.append("p.prediction = ?")
        params.append(prediction)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # Always LEFT JOIN predictions so each flow includes its ML result.
    # This is needed by the frontend traffic table which displays
    # prediction and confidence columns.
    query = f"""
        SELECT tf.*,
               p.prediction,
               p.probability,
               p.confidence
        FROM traffic_flows tf
        LEFT JOIN predictions p ON p.traffic_flow_id = tf.id
        {where}
        ORDER BY tf.id DESC
        LIMIT ?
    """
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    return _rows_to_list(rows)


# ---------------------------------------------------------------------------
# Predictions
# ---------------------------------------------------------------------------

def insert_prediction(pred: Prediction) -> int:
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO predictions
            (traffic_flow_id, prediction, probability, confidence, predicted_at)
        VALUES
            (:traffic_flow_id, :prediction, :probability, :confidence,
             COALESCE(:predicted_at, datetime('now')))
        """,
        {
            "traffic_flow_id": pred.traffic_flow_id,
            "prediction": pred.prediction,
            "probability": pred.probability,
            "confidence": pred.confidence,
            "predicted_at": pred.predicted_at,
        },
    )
    conn.commit()
    return cursor.lastrowid or 0


def get_recent_predictions(limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT p.*, tf.source_ip, tf.destination_ip, tf.protocol
        FROM predictions p
        LEFT JOIN traffic_flows tf ON tf.id = p.traffic_flow_id
        ORDER BY p.predicted_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return _rows_to_list(rows)


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

def insert_alert(alert: Alert) -> int:
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO alerts
            (device_id, source_ip, alert_type, severity, message, status)
        VALUES
            (:device_id, :source_ip, :alert_type, :severity, :message, :status)
        """,
        {
            "device_id": alert.device_id,
            "source_ip": alert.source_ip,
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "message": alert.message,
            "status": alert.status,
        },
    )
    conn.commit()
    return cursor.lastrowid or 0


def get_alerts(limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM alerts ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return _rows_to_list(rows)


# ---------------------------------------------------------------------------
# Mitigation Actions
# ---------------------------------------------------------------------------

def insert_mitigation_action(action: MitigationAction) -> int:
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO mitigation_actions
            (device_id, source_ip, action, rule_id, reason, success, simulated)
        VALUES
            (:device_id, :source_ip, :action, :rule_id, :reason, :success, :simulated)
        """,
        {
            "device_id": action.device_id,
            "source_ip": action.source_ip,
            "action": action.action,
            "rule_id": action.rule_id,
            "reason": action.reason,
            "success": int(action.success),
            "simulated": int(action.simulated),
        },
    )
    conn.commit()
    return cursor.lastrowid or 0


def get_mitigation_actions(limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM mitigation_actions ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return _rows_to_list(rows)


# ---------------------------------------------------------------------------
# Evaluation Metrics
# ---------------------------------------------------------------------------

def insert_evaluation_metrics(metrics: EvaluationMetrics) -> int:
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO evaluation_metrics
            (model_version, accuracy, precision_score, recall_score,
             f1_score, fpr, tpr)
        VALUES
            (:model_version, :accuracy, :precision_score, :recall_score,
             :f1_score, :fpr, :tpr)
        """,
        {
            "model_version": metrics.model_version,
            "accuracy": metrics.accuracy,
            "precision_score": metrics.precision_score,
            "recall_score": metrics.recall_score,
            "f1_score": metrics.f1_score,
            "fpr": metrics.fpr,
            "tpr": metrics.tpr,
        },
    )
    conn.commit()
    return cursor.lastrowid or 0


def get_latest_evaluation_metrics() -> Optional[Dict[str, Any]]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM evaluation_metrics ORDER BY recorded_at DESC LIMIT 1"
    ).fetchone()
    return _row_to_dict(row) if row else None


# ---------------------------------------------------------------------------
# System Events
# ---------------------------------------------------------------------------

def log_system_event(event: SystemEvent) -> int:
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO system_events (event_type, severity, message)
        VALUES (:event_type, :severity, :message)
        """,
        {
            "event_type": event.event_type,
            "severity": event.severity,
            "message": event.message,
        },
    )
    conn.commit()
    return cursor.lastrowid or 0


def get_system_events(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM system_events ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return _rows_to_list(rows)
