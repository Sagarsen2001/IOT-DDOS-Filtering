"""
api/utils.py
============
Shared helpers for consistent JSON responses and input validation.
"""

import ipaddress
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from flask import jsonify, Response


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def success_response(data: Any = None, status: int = 200) -> Tuple[Response, int]:
    body = {
        "success": True,
        "data": data,
        "timestamp": _now_iso(),
    }
    return jsonify(body), status


def error_response(
    code: str,
    message: str,
    status: int = 400,
) -> Tuple[Response, int]:
    body = {
        "success": False,
        "error": {"code": code, "message": message},
        "timestamp": _now_iso(),
    }
    return jsonify(body), status


def validate_ip(ip: str) -> bool:
    """Return True if ip is a valid IPv4 or IPv6 address."""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False
