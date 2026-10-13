"""
api/routes_control.py
======================
Control and system-status endpoints.

  GET  /api/health          — quick health check
  GET  /api/system/status   — detailed component status
  GET  /api/mitigations     — mitigation history
  POST /api/mitigate        — manually block a source IP
  POST /api/demo/start      — start the demo workflow
  POST /api/demo/stop       — stop the demo workflow
"""

import logging
import threading
from flask import Blueprint, current_app, request

from api.utils import success_response, error_response, validate_ip
from database.models import MitigationAction
from database.repository import get_mitigation_actions, insert_mitigation_action
from mitigation.rule_manager import install_block_rule
from ml.predict import is_model_loaded
from network.mqtt_client import MQTTClient
from network.ovs_manager import check_ovs_available
from ryu.ddos_controller import RyuClient
import config

logger = logging.getLogger(__name__)
bp = Blueprint("control", __name__)

# Module-level demo state
_demo_thread: threading.Thread = None
_demo_running = False


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@bp.route("/api/health", methods=["GET"])
def health():
    return success_response({
        "status": "ok",
        "service": "IoT DDoS Filtering Backend",
        "demo_mode": config.DEMO_MODE,
    })


# ---------------------------------------------------------------------------
# System Status
# ---------------------------------------------------------------------------

@bp.route("/api/system/status", methods=["GET"])
def system_status():
    # Database
    db_ok = _check_db()

    # ML model
    model_ok = is_model_loaded()

    # MQTT (check from app context)
    mqtt_client: MQTTClient = getattr(current_app, "mqtt_client", None)
    mqtt_ok = mqtt_client.is_connected if mqtt_client else False

    # OVS
    ovs_ok = check_ovs_available()

    # Ryu
    ryu_client = RyuClient()
    ryu_ok = ryu_client.is_reachable()

    # Zeek: check if log file exists
    import os
    zeek_ok = os.path.exists(config.ZEEK_LOG_PATH)

    return success_response({
        "flask": "running",
        "database": "ok" if db_ok else "error",
        "ml_model": "loaded" if model_ok else "not_loaded",
        "mqtt": "connected" if mqtt_ok else "disconnected",
        "ovs": "simulated" if config.DEMO_MODE else ("available" if ovs_ok else "unavailable"),
        "ryu": "simulated" if config.DEMO_MODE else ("reachable" if ryu_ok else "unreachable"),
        "zeek": "simulated" if config.DEMO_MODE else ("log_found" if zeek_ok else "log_not_found"),
        "demo_mode": config.DEMO_MODE,
        "demo_running": _demo_running,
    })


# ---------------------------------------------------------------------------
# Mitigations
# ---------------------------------------------------------------------------

@bp.route("/api/mitigations", methods=["GET"])
def list_mitigations():
    try:
        limit = min(int(request.args.get("limit", 100)), 500)
    except ValueError:
        limit = 100
    try:
        actions = get_mitigation_actions(limit=limit)
        return success_response({"mitigations": actions, "count": len(actions)})
    except Exception as exc:
        logger.error("Error fetching mitigations: %s", exc)
        return error_response("DATABASE_ERROR", str(exc), 500)


@bp.route("/api/mitigate", methods=["POST"])
def mitigate():
    """
    Manually trigger mitigation for a source IP.

    Request body
    ------------
    { "source_ip": "10.0.0.4" }
    """
    body = request.get_json(silent=True) or {}
    source_ip = body.get("source_ip", "").strip()

    if not source_ip:
        return error_response("INVALID_INPUT", "source_ip is required", 400)
    if not validate_ip(source_ip):
        return error_response("INVALID_INPUT", f"'{source_ip}' is not a valid IP address", 400)

    result = install_block_rule(source_ip)

    # Record in DB
    try:
        ma = MitigationAction(
            source_ip=source_ip,
            action="BLOCK",
            rule_id=result.get("rule_id"),
            reason="Manual API request",
            success=result.get("success", False),
            simulated=result.get("simulated", True),
        )
        insert_mitigation_action(ma)

        from database.db import get_connection
        conn = get_connection()
        conn.execute(
            "UPDATE devices SET status = 'blocked', last_seen = datetime('now') WHERE ip_address = ?",
            (source_ip,)
        )
        conn.commit()
    except Exception as exc:
        logger.warning("Could not persist mitigation action: %s", exc)

    status_code = 200 if result.get("success") else 500
    return success_response(result, status=status_code)


# ---------------------------------------------------------------------------
# Demo Control
# ---------------------------------------------------------------------------

@bp.route("/api/demo/start", methods=["POST"])
def demo_start():
    global _demo_thread, _demo_running

    # 1. Ensure devices are seeded in database and demo state is clean
    try:
        from database.db import seed_default_devices, get_connection
        seed_default_devices()
        conn = get_connection()
        # Reset all devices to active state
        conn.execute("UPDATE devices SET status = 'active'")
        # Clear previous demo mitigations so attack can be observed again
        conn.execute("DELETE FROM mitigation_actions WHERE source_ip IN ('10.0.0.2', '10.0.0.6')")
        conn.commit()
    except Exception as exc:
        logger.warning("Device seed/reset during demo_start: %s", exc)

    monitor = getattr(current_app, "traffic_monitor", None)
    if monitor and not monitor.is_running:
        monitor.start()

    _demo_running = True
    logger.info("Demo workflow started via API")
    return success_response({
        "message": "Demo workflow started — live IoT traffic and threat detection active",
        "demo_mode": config.DEMO_MODE,
        "demo_running": True,
    })


@bp.route("/api/demo/stop", methods=["POST"])
def demo_stop():
    global _demo_running

    monitor = getattr(current_app, "traffic_monitor", None)
    if monitor and monitor.is_running:
        monitor.stop()

    _demo_running = False
    logger.info("Demo workflow stopped via API")
    return success_response({"message": "Demo workflow stopped", "demo_running": False})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_db() -> bool:
    try:
        from database.db import get_connection
        conn = get_connection()
        conn.execute("SELECT 1").fetchone()
        return True
    except Exception:
        return False
