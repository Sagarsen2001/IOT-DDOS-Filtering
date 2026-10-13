"""
monitoring/feature_extractor.py
================================
Convert raw flow records (from Zeek or synthetic sources) into the normalised
feature dict that the ML preprocessing pipeline expects.

The same field names and types must be used here as in ml/preprocess.py.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def extract_features(raw_flow: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalise and validate a raw flow record.

    Parameters
    ----------
    raw_flow : dict from Zeek parser or traffic generator.

    Returns
    -------
    Feature dict ready for ml.preprocess.transform().
    """

    def _f(key: str, default: float = 0.0) -> float:
        val = raw_flow.get(key, default)
        try:
            return float(val) if val is not None else default
        except (TypeError, ValueError):
            logger.debug("Feature '%s' coerced to default (value=%r)", key, val)
            return default

    def _i(key: str, default: int = 0) -> int:
        val = raw_flow.get(key, default)
        try:
            return int(float(val)) if val is not None else default
        except (TypeError, ValueError):
            return default

    duration = _f("duration", 0.001)
    if duration <= 0:
        duration = 0.001

    packet_count = _i("packet_count", 0)
    byte_count = _i("byte_count", 0)

    # Derived rates (recompute for consistency even if already provided)
    packet_rate = _f("packet_rate") or round(packet_count / duration, 4)
    byte_rate = _f("byte_rate") or round(byte_count / duration, 4)
    avg_packet_size = _f("avg_packet_size") or (
        round(byte_count / max(packet_count, 1), 4)
    )

    protocol = str(raw_flow.get("protocol", "UNKNOWN")).upper()

    # Support both naming conventions
    src_port = _i("src_port") or _i("source_port")
    dst_port = _i("dst_port") or _i("destination_port")
    src_ip = raw_flow.get("src_ip") or raw_flow.get("source_ip", "")
    dst_ip = raw_flow.get("dst_ip") or raw_flow.get("destination_ip", "")

    return {
        # Canonical names matching preprocess.py NUMERIC_FEATURES
        "duration": round(duration, 4),
        "packet_count": packet_count,
        "byte_count": byte_count,
        "packet_rate": round(packet_rate, 4),
        "byte_rate": round(byte_rate, 4),
        "avg_packet_size": round(avg_packet_size, 4),
        "src_port": src_port,
        "dst_port": dst_port,
        "protocol": protocol,
        # Pass-through metadata (not used in ML but useful for logging/alerts)
        "source_ip": str(src_ip),
        "destination_ip": str(dst_ip),
        "timestamp": raw_flow.get("timestamp"),
        "label": raw_flow.get("label"),
    }


def validate_features(features: Dict[str, Any]) -> Optional[str]:
    """
    Basic sanity check.  Returns an error message string if invalid, else None.
    """
    required = ["duration", "packet_count", "byte_count", "packet_rate",
                "byte_rate", "avg_packet_size"]
    for field in required:
        if features.get(field) is None:
            return f"Missing required feature: {field}"
    if features.get("packet_rate", 0) < 0:
        return "packet_rate cannot be negative"
    return None
