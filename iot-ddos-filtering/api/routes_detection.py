"""
api/routes_detection.py
========================
ML detection and alert endpoints.

  GET  /api/detections  — recent ML predictions
  GET  /api/alerts      — recent security alerts
  POST /api/predict     — predict a single flow
"""

import logging
from flask import Blueprint, request

from api.utils import success_response, error_response
from database.models import Alert, Prediction, TrafficFlow
from database.repository import get_alerts, get_recent_predictions, insert_alert, insert_prediction, insert_traffic_flow
from ml.predict import predict_single, is_model_loaded
from monitoring.feature_extractor import extract_features

logger = logging.getLogger(__name__)
bp = Blueprint("detection", __name__)


@bp.route("/api/detections", methods=["GET"])
def list_detections():
    try:
        limit = min(int(request.args.get("limit", 100)), 500)
    except ValueError:
        limit = 100
    try:
        preds = get_recent_predictions(limit=limit)
        return success_response({"detections": preds, "count": len(preds)})
    except Exception as exc:
        logger.error("Error fetching detections: %s", exc)
        return error_response("DATABASE_ERROR", str(exc), 500)


@bp.route("/api/alerts", methods=["GET"])
def list_alerts():
    try:
        limit = min(int(request.args.get("limit", 100)), 500)
    except ValueError:
        limit = 100
    try:
        alerts = get_alerts(limit=limit)
        return success_response({"alerts": alerts, "count": len(alerts)})
    except Exception as exc:
        logger.error("Error fetching alerts: %s", exc)
        return error_response("DATABASE_ERROR", str(exc), 500)


@bp.route("/api/predict", methods=["POST"])
def predict():
    """
    Classify a single network flow.

    Request body (JSON)
    -------------------
    {
        "source_ip": "10.0.0.1",
        "destination_ip": "192.168.1.1",
        "src_port": 50001,
        "dst_port": 1883,
        "protocol": "TCP",
        "duration": 5.0,
        "packet_count": 20,
        "byte_count": 3200,
        "packet_rate": 4.0,
        "byte_rate": 640.0,
        "avg_packet_size": 160.0
    }

    Response
    --------
    {
        "prediction": "NORMAL",
        "label": 0,
        "probability": 0.03,
        "confidence": 0.97,
        "model_version": "rf-v1",
        "timestamp": "..."
    }
    """
    if not is_model_loaded():
        return error_response(
            "MODEL_NOT_LOADED",
            "ML model is not loaded. Run ml/train.py first.",
            503,
        )

    body = request.get_json(silent=True)
    if not body:
        return error_response("INVALID_INPUT", "JSON body is required", 400)

    # Extract and normalise features
    try:
        features = extract_features(body)
    except Exception as exc:
        return error_response("FEATURE_EXTRACTION_ERROR", str(exc), 400)

    # Run ML inference
    result = predict_single(features)
    if "error" in result:
        return error_response("PREDICTION_ERROR", result.get("message", "Unknown error"), 500)

    # Persist flow and prediction
    try:
        flow = TrafficFlow(
            source_ip=features.get("source_ip", ""),
            destination_ip=features.get("destination_ip", ""),
            source_port=features.get("src_port"),
            destination_port=features.get("dst_port"),
            protocol=features.get("protocol"),
            duration=features.get("duration"),
            packet_count=features.get("packet_count"),
            byte_count=features.get("byte_count"),
            packet_rate=features.get("packet_rate"),
            byte_rate=features.get("byte_rate"),
            avg_packet_size=features.get("avg_packet_size"),
        )
        flow_id = insert_traffic_flow(flow)

        pred = Prediction(
            traffic_flow_id=flow_id,
            prediction=result["prediction"],
            probability=result["probability"],
            confidence=result["confidence"],
        )
        insert_prediction(pred)

        # Create alert if DDoS
        if result["prediction"] == "DDOS":
            alert = Alert(
                source_ip=features.get("source_ip", ""),
                alert_type="DDOS_DETECTED",
                severity="HIGH",
                message=f"DDoS prediction via /api/predict (confidence={result['confidence']:.2f})",
            )
            insert_alert(alert)
            logger.warning(
                "SECURITY: DDoS detected via API for src=%s", features.get("source_ip")
            )

    except Exception as exc:
        logger.warning("Could not persist prediction result: %s", exc)

    return success_response(result)
