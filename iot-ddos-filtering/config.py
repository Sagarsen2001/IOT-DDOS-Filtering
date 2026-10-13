"""
config.py
=========
Central configuration for the IoT DDoS Filtering system.
All settings can be overridden by environment variables or a .env file.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if present (does not override existing env vars)
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


def _get_bool(key: str, default: bool) -> bool:
    """Parse an environment variable as a boolean."""
    val = os.getenv(key, str(default)).lower()
    return val in ("1", "true", "yes", "on")


# ---------------------------------------------------------------------------
# Flask
# ---------------------------------------------------------------------------
FLASK_HOST: str = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT: int = int(os.getenv("FLASK_PORT", "5000"))
FLASK_DEBUG: bool = _get_bool("FLASK_DEBUG", False)
SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASE_PATH: str = os.getenv(
    "DATABASE_PATH",
    str(BASE_DIR / "data" / "iot_ddos.db"),
)

# ---------------------------------------------------------------------------
# MQTT
# ---------------------------------------------------------------------------
MQTT_BROKER_HOST: str = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT: int = int(os.getenv("MQTT_BROKER_PORT", "1883"))
MQTT_TOPIC: str = os.getenv("MQTT_TOPIC", "iot/+/telemetry")
MQTT_CLIENT_ID: str = os.getenv("MQTT_CLIENT_ID", "iot-ddos-backend")
MQTT_KEEPALIVE: int = int(os.getenv("MQTT_KEEPALIVE", "60"))

# ---------------------------------------------------------------------------
# Ryu SDN Controller
# ---------------------------------------------------------------------------
RYU_HOST: str = os.getenv("RYU_HOST", "localhost")
RYU_PORT: int = int(os.getenv("RYU_PORT", "8080"))
RYU_OFCTL_URL: str = f"http://{RYU_HOST}:{RYU_PORT}"

# ---------------------------------------------------------------------------
# Open vSwitch
# ---------------------------------------------------------------------------
OVS_SWITCH_NAME: str = os.getenv("OVS_SWITCH_NAME", "s1")

# ---------------------------------------------------------------------------
# ML / Detection
# ---------------------------------------------------------------------------
MODEL_PATH: str = os.getenv(
    "MODEL_PATH",
    str(BASE_DIR / "ml" / "artifacts" / "rf_model.joblib"),
)
SCALER_PATH: str = os.getenv(
    "SCALER_PATH",
    str(BASE_DIR / "ml" / "artifacts" / "scaler.joblib"),
)
ENCODER_PATH: str = os.getenv(
    "ENCODER_PATH",
    str(BASE_DIR / "ml" / "artifacts" / "encoder.joblib"),
)
METRICS_PATH: str = os.getenv(
    "METRICS_PATH",
    str(BASE_DIR / "ml" / "artifacts" / "metrics.json"),
)
MODEL_VERSION: str = os.getenv("MODEL_VERSION", "rf-v1")

DETECTION_THRESHOLD: float = float(os.getenv("DETECTION_THRESHOLD", "0.7"))
MIN_PACKET_RATE_THRESHOLD: float = float(
    os.getenv("MIN_PACKET_RATE_THRESHOLD", "100.0")
)
MITIGATION_ENABLED: bool = _get_bool("MITIGATION_ENABLED", True)

# ---------------------------------------------------------------------------
# Zeek
# ---------------------------------------------------------------------------
ZEEK_LOG_PATH: str = os.getenv("ZEEK_LOG_PATH", "/opt/zeek/logs/current/conn.log")

# ---------------------------------------------------------------------------
# Data / Dataset
# ---------------------------------------------------------------------------
DATASET_PATH: str = os.getenv(
    "DATASET_PATH",
    str(BASE_DIR / "data" / "processed" / "dataset.csv"),
)
RANDOM_SEED: int = int(os.getenv("RANDOM_SEED", "42"))
DATASET_SIZE: int = int(os.getenv("DATASET_SIZE", "5000"))

# ---------------------------------------------------------------------------
# Demo Mode
# ---------------------------------------------------------------------------
DEMO_MODE: bool = _get_bool("DEMO_MODE", True)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

# ---------------------------------------------------------------------------
# Monitoring
# ---------------------------------------------------------------------------
MONITOR_INTERVAL_SECONDS: float = float(os.getenv("MONITOR_INTERVAL_SECONDS", "5.0"))


def configure_logging() -> None:
    """Apply the global logging configuration."""
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format=LOG_FORMAT,
    )
