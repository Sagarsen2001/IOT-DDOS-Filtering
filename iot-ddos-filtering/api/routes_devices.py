"""
api/routes_devices.py
=====================
IoT device management endpoints.

  GET  /api/devices              — list all devices
  GET  /api/devices/<device_id>  — get single device
  POST /api/devices/register     — register a new device
"""

import logging
from flask import Blueprint, request

from api.utils import success_response, error_response, validate_ip
from database.models import Device
from database.repository import get_all_devices, get_device_by_id, upsert_device

logger = logging.getLogger(__name__)
bp = Blueprint("devices", __name__)


@bp.route("/api/devices", methods=["GET"])
def list_devices():
    try:
        devices = get_all_devices()
        return success_response({"devices": devices, "count": len(devices)})
    except Exception as exc:
        logger.error("Error listing devices: %s", exc)
        return error_response("DATABASE_ERROR", str(exc), 500)


@bp.route("/api/devices/<device_id>", methods=["GET"])
def get_device(device_id: str):
    try:
        device = get_device_by_id(device_id)
        if device is None:
            return error_response("NOT_FOUND", f"Device '{device_id}' not found", 404)
        return success_response({"device": device})
    except Exception as exc:
        logger.error("Error fetching device %s: %s", device_id, exc)
        return error_response("DATABASE_ERROR", str(exc), 500)


@bp.route("/api/devices/register", methods=["POST"])
def register_device():
    body = request.get_json(silent=True) or {}

    device_id = body.get("device_id", "").strip()
    ip_address = body.get("ip_address", "").strip()

    if not device_id:
        return error_response("INVALID_INPUT", "device_id is required", 400)
    if not ip_address:
        return error_response("INVALID_INPUT", "ip_address is required", 400)
    if not validate_ip(ip_address):
        return error_response("INVALID_INPUT", f"'{ip_address}' is not a valid IP address", 400)

    device = Device(
        device_id=device_id,
        ip_address=ip_address,
        mac_address=body.get("mac_address"),
        status=body.get("status", "active"),
    )
    try:
        upsert_device(device)
        logger.info("Device registered: %s (%s)", device_id, ip_address)
        return success_response({"device_id": device_id, "ip_address": ip_address}, status=201)
    except Exception as exc:
        logger.error("Error registering device: %s", exc)
        return error_response("DATABASE_ERROR", str(exc), 500)
