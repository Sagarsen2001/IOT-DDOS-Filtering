#!/usr/bin/env bash
# scripts/train_model.sh
# ============================================================
# Generate dataset (if missing) and train the RandomForest model.
# Run from project root: bash scripts/train_model.sh
# ============================================================

set -euo pipefail

# Activate virtual environment if present
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

echo ""
echo "========================================================"
echo "  IoT DDoS Filtering — Model Training"
echo "========================================================"
echo ""

echo "[1/3] Generating synthetic dataset (if not present)..."
python scripts/generate_sample_dataset.py

echo ""
echo "[2/3] Initialising database..."
python -c "from database.db import init_db; init_db(); print('  Database ready')"

echo ""
echo "[3/3] Training RandomForest classifier..."
python -m ml.train

echo ""
echo "========================================================"
echo "  Training complete!"
echo "  Model saved to: ml/artifacts/rf_model.joblib"
echo "  Metrics saved to: ml/artifacts/metrics.json"
echo "========================================================"
