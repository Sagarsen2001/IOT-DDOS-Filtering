"""
app.py
======
Flask application factory and entry-point.

Startup sequence
----------------
1. Configure logging.
2. Initialise SQLite database.
3. Attempt to load the ML model.
4. Attempt to connect to MQTT broker.
5. Start the background TrafficMonitor daemon (if model is loaded).
6. Register all API blueprints.
7. Start the Flask development server.
"""

import logging

from flask import Flask
from flask_cors import CORS

import config
from api.routes_control import bp as control_bp
from api.routes_detection import bp as detection_bp
from api.routes_devices import bp as devices_bp
from api.routes_metrics import bp as metrics_bp
from api.routes_traffic import bp as traffic_bp
from database.db import init_db
from ml.predict import is_model_loaded, reload_model
from monitoring.traffic_monitor import TrafficMonitor
from network.mqtt_client import MQTTClient

config.configure_logging()
logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """
    Application factory.
    Returns a configured Flask application ready to run.
    """
    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY

    # ------------------------------------------------------------------
    # CORS — allow any origin so a separate frontend can connect
    # ------------------------------------------------------------------
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    try:
        init_db()
    except Exception as exc:
        logger.error("CRITICAL: Database initialisation failed: %s", exc)
        # Continue — routes will return 500 on DB calls

    # ------------------------------------------------------------------
    # ML Model
    # ------------------------------------------------------------------
    if not is_model_loaded():
        logger.warning(
            "ML model not loaded. "
            "Train it first: python -m ml.train   or   bash scripts/train_model.sh"
        )

    # ------------------------------------------------------------------
    # MQTT
    # ------------------------------------------------------------------
    mqtt_client = MQTTClient()
    connected = mqtt_client.connect()
    if not connected:
        logger.warning("MQTT broker unavailable — continuing without MQTT")
    app.mqtt_client = mqtt_client  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Background Traffic Monitor
    # ------------------------------------------------------------------
    monitor = TrafficMonitor(demo_mode=config.DEMO_MODE)
    if is_model_loaded():
        monitor.start()
    else:
        logger.warning(
            "TrafficMonitor not started — ML model must be loaded first. "
            "Call POST /api/demo/start after training."
        )
    app.traffic_monitor = monitor  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # API Blueprints
    # ------------------------------------------------------------------
    for bp in (control_bp, detection_bp, devices_bp, metrics_bp, traffic_bp):
        app.register_blueprint(bp)

    # ------------------------------------------------------------------
    # Teardown
    # ------------------------------------------------------------------
    @app.teardown_appcontext
    def shutdown_resources(exc):
        """Called when the app context tears down (e.g., on shutdown)."""
        pass  # Connections are thread-local; no explicit close needed

    logger.info(
        "Flask app created — host=%s port=%d demo_mode=%s",
        config.FLASK_HOST, config.FLASK_PORT, config.DEMO_MODE,
    )
    return app


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------
if __name__ == "__main__":
    application = create_app()
    application.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG,
        use_reloader=False,   # Reloader would double-start the background thread
    )
