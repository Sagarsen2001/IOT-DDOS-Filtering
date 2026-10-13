#!/usr/bin/env bash
# scripts/setup_environment.sh
# ============================================================
# One-time setup for the IoT DDoS Filtering project on Ubuntu.
# Run with: bash scripts/setup_environment.sh
# ============================================================

set -euo pipefail

echo ""
echo "========================================================"
echo "  IoT DDoS Filtering — Environment Setup"
echo "========================================================"
echo ""

# --- System packages ---
echo "[1/6] Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    mosquitto \
    mosquitto-clients \
    zeek \
    openvswitch-switch \
    mininet \
    net-tools \
    curl \
    git

echo "[2/6] Creating Python virtual environment..."
if [ ! -d "venv" ]; then
    python3.11 -m venv venv
    echo "  Virtual environment created at ./venv"
else
    echo "  Virtual environment already exists — skipping"
fi

echo "[3/6] Installing Python dependencies..."
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "  Python packages installed"

echo "[4/6] Setting up .env file..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "  .env created from .env.example — edit it if needed"
else
    echo "  .env already exists — skipping"
fi

echo "[5/6] Creating data directories..."
mkdir -p data/raw data/processed data/samples ml/artifacts

echo "[6/6] Starting Mosquitto MQTT broker..."
if systemctl is-active --quiet mosquitto; then
    echo "  Mosquitto already running"
else
    sudo systemctl enable mosquitto
    sudo systemctl start mosquitto
    echo "  Mosquitto started"
fi

echo ""
echo "========================================================"
echo "  Setup complete!"
echo ""
echo "  Next steps:"
echo "  1. source venv/bin/activate"
echo "  2. python scripts/generate_sample_dataset.py"
echo "  3. python -m ml.train"
echo "  4. python app.py"
echo "  5. Visit http://localhost:5000/api/health"
echo "  6. For full demo: bash scripts/run_demo.sh"
echo "========================================================"
