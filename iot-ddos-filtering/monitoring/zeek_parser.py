"""
monitoring/zeek_parser.py
=========================
Parse Zeek TSV connection log files (conn.log) into the internal flow schema.

Zeek conn.log columns (standard subset):
    ts, uid, id.orig_h, id.orig_p, id.resp_h, id.resp_p,
    proto, service, duration, orig_bytes, resp_bytes,
    orig_pkts, resp_pkts, conn_state, …

The parser:
  - Handles missing/malformed rows gracefully.
  - Returns a list of normalised flow dicts.
  - Works with both REAL logs and sample/synthetic logs.
  - Skips comment lines starting with '#'.

DEMO MODE
---------
If DEMO_MODE is True or the log file is unavailable, the parser returns
synthetic flow records so the pipeline can continue uninterrupted.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import config

logger = logging.getLogger(__name__)

# Column positions in a standard Zeek conn.log TSV (0-indexed after stripping header)
_ZEEK_COLUMNS = [
    "ts", "uid", "id_orig_h", "id_orig_p", "id_resp_h", "id_resp_p",
    "proto", "service", "duration", "orig_bytes", "resp_bytes", "conn_state",
    "local_orig", "local_resp", "missed_bytes", "history",
    "orig_pkts", "orig_ip_bytes", "resp_pkts", "resp_ip_bytes",
]

_MISSING = {"-", "(empty)", "", None}


def _safe_float(val: Any) -> Optional[float]:
    if val in _MISSING:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _safe_int(val: Any) -> Optional[int]:
    if val in _MISSING:
        return None
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


def _parse_line(fields: List[str], col_map: Dict[str, int]) -> Optional[Dict[str, Any]]:
    """Convert one TSV row into a normalised flow dict."""

    def get(name: str) -> Optional[str]:
        idx = col_map.get(name)
        if idx is None or idx >= len(fields):
            return None
        v = fields[idx].strip()
        return None if v in _MISSING else v

    src_ip = get("id_orig_h")
    dst_ip = get("id_resp_h")
    if not src_ip or not dst_ip:
        return None  # Essential fields missing

    duration = _safe_float(get("duration")) or 0.001
    orig_pkts = _safe_int(get("orig_pkts")) or 0
    resp_pkts = _safe_int(get("resp_pkts")) or 0
    orig_bytes = _safe_int(get("orig_bytes")) or 0
    resp_bytes = _safe_int(get("resp_bytes")) or 0

    packet_count = orig_pkts + resp_pkts
    byte_count = orig_bytes + resp_bytes
    packet_rate = packet_count / max(duration, 0.001)
    byte_rate = byte_count / max(duration, 0.001)
    avg_packet_size = byte_count / max(packet_count, 1)

    return {
        "source_ip": src_ip,
        "destination_ip": dst_ip,
        "source_port": _safe_int(get("id_orig_p")),
        "destination_port": _safe_int(get("id_resp_p")),
        "protocol": (get("proto") or "unknown").upper(),
        "duration": round(duration, 4),
        "packet_count": packet_count,
        "byte_count": byte_count,
        "packet_rate": round(packet_rate, 4),
        "byte_rate": round(byte_rate, 4),
        "avg_packet_size": round(avg_packet_size, 4),
        "timestamp": get("ts"),
        "label": None,   # Ground truth unknown from live logs
        # Feature aliases expected by preprocess.py
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "src_port": _safe_int(get("id_orig_p")),
        "dst_port": _safe_int(get("id_resp_p")),
    }


def parse_zeek_log(filepath: str) -> List[Dict[str, Any]]:
    """
    Parse a Zeek conn.log file.

    Parameters
    ----------
    filepath : Absolute path to the Zeek conn.log file.

    Returns
    -------
    List of normalised flow dicts (may be empty).
    """
    path = Path(filepath)
    if not path.exists():
        logger.warning("Zeek log not found: %s", filepath)
        return []

    flows: List[Dict[str, Any]] = []
    col_map: Dict[str, int] = {}

    try:
        with open(path, "r", errors="replace") as fh:
            for raw_line in fh:
                line = raw_line.rstrip("\n")

                # Parse header comment that defines column order
                if line.startswith("#fields"):
                    cols = line.split("\t")[1:]
                    # Normalise column names: id.orig_h → id_orig_h
                    col_map = {
                        c.replace(".", "_"): i for i, c in enumerate(cols)
                    }
                    continue

                # Skip other comment lines
                if line.startswith("#") or not line.strip():
                    continue

                # If no column map found, fall back to positional defaults
                if not col_map:
                    col_map = {c: i for i, c in enumerate(_ZEEK_COLUMNS)}

                fields = line.split("\t")
                try:
                    flow = _parse_line(fields, col_map)
                    if flow:
                        flows.append(flow)
                except Exception as exc:
                    logger.debug("Skipping malformed Zeek line: %s — %s", line[:80], exc)

    except OSError as exc:
        logger.error("Cannot read Zeek log '%s': %s", filepath, exc)

    logger.info("Parsed %d flows from Zeek log: %s", len(flows), filepath)
    return flows


def get_flows(demo_mode: bool = config.DEMO_MODE) -> List[Dict[str, Any]]:
    """
    High-level entry-point for the monitoring pipeline.

    In REAL MODE  → parse ZEEK_LOG_PATH.
    In DEMO MODE  → return synthetic flow records.
    """
    if not demo_mode and os.path.exists(config.ZEEK_LOG_PATH):
        return parse_zeek_log(config.ZEEK_LOG_PATH)

    if not demo_mode:
        logger.warning(
            "REAL MODE requested but Zeek log not found at %s — "
            "falling back to synthetic data.",
            config.ZEEK_LOG_PATH,
        )

    logger.info("[DEMO MODE] Generating synthetic Zeek-like flows")
    return _synthetic_demo_flows()


def _synthetic_demo_flows() -> List[Dict[str, Any]]:
    """
    Generate dynamic, realistic simulated IoT network flows for demo mode.
    Includes active IoT device telemetry with realistic jitter, and an attack
    burst from a compromised device. If a device is blocked by mitigation,
    its traffic is suppressed so the user sees the attack stop on charts.
    """
    import random
    import time

    # Check for actively blocked IPs in the database
    blocked_ips = set()
    try:
        from database.repository import get_mitigation_actions
        actions = get_mitigation_actions(limit=50)
        blocked_ips = {a["source_ip"] for a in actions if a.get("action") == "BLOCK" and a.get("success")}
    except Exception:
        pass

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    flows: List[Dict[str, Any]] = []

    # Normal IoT devices generating telemetry
    normal_profiles = [
        {"ip": "10.0.0.1", "port": 1883, "proto": "TCP"},
        {"ip": "10.0.0.3", "port": 8883, "proto": "TCP"},
        {"ip": "10.0.0.4", "port": 5683, "proto": "UDP"},
        {"ip": "10.0.0.5", "port": 1883, "proto": "TCP"},
    ]

    for p in normal_profiles:
        # Subtle variations in telemetry duration and packet rates
        duration = round(random.uniform(2.5, 7.0), 3)
        pkts = random.randint(12, 45)
        bytes_count = pkts * random.randint(90, 240)
        packet_rate = round(pkts / max(duration, 0.001), 2)
        byte_rate = round(bytes_count / max(duration, 0.001), 2)
        avg_pkt_size = round(bytes_count / max(pkts, 1), 1)
        src_port = random.randint(49152, 65535)

        flows.append({
            "source_ip": p["ip"], "src_ip": p["ip"],
            "destination_ip": "192.168.1.1", "dst_ip": "192.168.1.1",
            "source_port": src_port, "src_port": src_port,
            "destination_port": p["port"], "dst_port": p["port"],
            "protocol": p["proto"],
            "duration": duration,
            "packet_count": pkts,
            "byte_count": bytes_count,
            "packet_rate": packet_rate,
            "byte_rate": byte_rate,
            "avg_packet_size": avg_pkt_size,
            "timestamp": now,
            "label": 0,
        })

    # Suspicious device (10.0.0.6 - port scanning / anomalous traffic)
    bot_ip = "10.0.0.6"
    if bot_ip not in blocked_ips:
        duration = round(random.uniform(1.0, 2.5), 3)
        pkts = random.randint(120, 280)
        bytes_count = pkts * random.randint(64, 120)
        packet_rate = round(pkts / max(duration, 0.001), 2)
        byte_rate = round(bytes_count / max(duration, 0.001), 2)
        flows.append({
            "source_ip": bot_ip, "src_ip": bot_ip,
            "destination_ip": "192.168.1.1", "dst_ip": "192.168.1.1",
            "source_port": random.randint(40000, 50000), "src_port": 45000,
            "destination_port": random.choice([22, 23, 80, 8080]), "dst_port": 80,
            "protocol": "TCP",
            "duration": duration,
            "packet_count": pkts,
            "byte_count": bytes_count,
            "packet_rate": packet_rate,
            "byte_rate": byte_rate,
            "avg_packet_size": round(bytes_count / max(pkts, 1), 1),
            "timestamp": now,
            "label": 1,
        })

    # Compromised / High-Rate Attack device (10.0.0.2)
    attack_ip = "10.0.0.2"
    if attack_ip not in blocked_ips:
        # High-rate burst: 3000-8500 packets/sec
        duration = round(random.uniform(0.15, 0.45), 3)
        pkts = random.randint(2000, 6000)
        bytes_count = pkts * random.randint(64, 128)
        packet_rate = round(pkts / max(duration, 0.001), 2)
        byte_rate = round(bytes_count / max(duration, 0.001), 2)
        avg_pkt_size = round(bytes_count / max(pkts, 1), 1)
        src_port = random.randint(1024, 65535)

        flows.append({
            "source_ip": attack_ip, "src_ip": attack_ip,
            "destination_ip": "192.168.1.1", "dst_ip": "192.168.1.1",
            "source_port": src_port, "src_port": src_port,
            "destination_port": random.choice([80, 443, 1883]), "dst_port": 80,
            "protocol": random.choice(["TCP", "UDP"]),
            "duration": duration,
            "packet_count": pkts,
            "byte_count": bytes_count,
            "packet_rate": packet_rate,
            "byte_rate": byte_rate,
            "avg_packet_size": avg_pkt_size,
            "timestamp": now,
            "label": 1,
        })
    else:
        logger.debug("[DEMO] Traffic from blocked source %s dropped by rule", attack_ip)

    return flows
