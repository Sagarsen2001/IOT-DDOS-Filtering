"""
api/routes_traffic.py
=====================
Traffic flow query endpoints.

  GET /api/traffic   — filtered flow list
"""

import logging
from flask import Blueprint, request

from api.utils import success_response, error_response
from database.repository import get_traffic_flows

logger = logging.getLogger(__name__)
bp = Blueprint("traffic", __name__)


@bp.route("/api/traffic", methods=["GET"])
def list_traffic():
    """
    Query stored traffic flows.

    Query Parameters
    ----------------
    start_time  : ISO datetime string lower bound.
    end_time    : ISO datetime string upper bound.
    source_ip   : Filter by source IP.
    prediction  : Filter by prediction ('NORMAL' or 'DDOS').
    label       : Filter by ground-truth label ('0' or '1').
    limit       : Max rows to return (default 200, max 1000).
    """
    start_time = request.args.get("start_time")
    end_time = request.args.get("end_time")
    source_ip = request.args.get("source_ip")
    prediction = request.args.get("prediction")
    label = request.args.get("label")

    try:
        limit = min(int(request.args.get("limit", 200)), 1000)
    except ValueError:
        return error_response("INVALID_INPUT", "limit must be an integer", 400)

    if prediction and prediction not in ("NORMAL", "DDOS"):
        return error_response(
            "INVALID_INPUT",
            "prediction must be 'NORMAL' or 'DDOS'",
            400,
        )

    try:
        flows = get_traffic_flows(
            start_time=start_time,
            end_time=end_time,
            source_ip=source_ip,
            prediction=prediction,
            label=label,
            limit=limit,
        )
        return success_response({"flows": flows, "count": len(flows)})
    except Exception as exc:
        logger.error("Error fetching traffic flows: %s", exc)
        return error_response("DATABASE_ERROR", str(exc), 500)
