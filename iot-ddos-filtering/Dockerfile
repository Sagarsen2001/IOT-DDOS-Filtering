# ============================================================
# Dockerfile — Flask backend
# ============================================================
# Containerises the Flask + SQLite + ML inference backend.
# Mininet, OVS, and Ryu are NOT included (they require
# Linux kernel features unavailable in standard Docker).
# ============================================================

FROM python:3.11-slim

LABEL maintainer="IoT DDoS Filtering Project"
LABEL description="Flask backend for IoT DDoS detection and mitigation"

# ── System dependencies ───────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python dependencies (cached layer) ────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application source ────────────────────────────────────────
COPY . .

# ── Ensure runtime directories exist ──────────────────────────
RUN mkdir -p data/raw data/processed data/samples ml/artifacts

# ── Non-root user for security ────────────────────────────────
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser && \
    chown -R appuser:appgroup /app
USER appuser

# ── Environment defaults ─────────────────────────────────────
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEMO_MODE=true \
    FLASK_HOST=0.0.0.0 \
    FLASK_PORT=5000 \
    FLASK_DEBUG=false \
    MQTT_BROKER_HOST=mosquitto \
    MQTT_BROKER_PORT=1883 \
    DATABASE_PATH=/app/data/iot_ddos.db \
    LOG_LEVEL=INFO

EXPOSE 5000

# ── Health check ──────────────────────────────────────────────
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

CMD ["python", "app.py"]
