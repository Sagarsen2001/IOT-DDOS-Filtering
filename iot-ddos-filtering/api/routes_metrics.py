"""
api/routes_metrics.py
======================
Metrics endpoint.

  GET /api/metrics  — return all system metrics
"""

import logging
from flask import Blueprint

from api.utils import success_response, error_response
from metrics.calculator import get_metrics

logger = logging.getLogger(__name__)
bp = Blueprint("metrics_bp", __name__)


@bp.route("/api/metrics", methods=["GET"])
def metrics():
    try:
        data = get_metrics()
        return success_response(data)
    except Exception as exc:
        logger.error("Error computing metrics: %s", exc)
        return error_response("METRICS_ERROR", str(exc), 500)
