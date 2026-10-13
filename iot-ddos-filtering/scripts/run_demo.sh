#!/usr/bin/env bash
# scripts/run_demo.sh
# ============================================================
# Complete end-to-end demo of the IoT DDoS Filtering system.
#
# What this script does
# ---------------------
#  1. (Re)generate the synthetic dataset.
#  2. Train the ML model.
#  3. Start the Flask backend in the background.
#  4. Wait for Flask to be ready.
#  5. Register simulated IoT devices.
#  6. Generate NORMAL traffic (calls the prediction API directly).
#  7. Generate DDoS-like traffic (calls the prediction API directly).
#  8. Show alert and mitigation results.
#  9. Display final metrics.
# 10. Stop Flask.
#
# Run: bash scripts/run_demo.sh
# ============================================================

set -euo pipefail

if [ -f "venv/bin/activate" ]; then source venv/bin/activate; fi

BASE_URL="http://localhost:5000"
FLASK_PID=""

cleanup() {
    if [ -n "$FLASK_PID" ]; then
        echo ""
        echo ">>> Stopping Flask (pid=$FLASK_PID)..."
        kill "$FLASK_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

echo ""
echo "========================================================"
echo "  IoT DDoS Filtering — DEMO MODE"
echo "========================================================"

# ------------------------------------------------------------------
# Step 1: Dataset & Training
# ------------------------------------------------------------------
echo ""
echo "[STEP 1] Generating synthetic dataset and training model..."
python scripts/generate_sample_dataset.py --size 2000
python -m ml.train

# ------------------------------------------------------------------
# Step 2: Start Flask
# ------------------------------------------------------------------
echo ""
echo "[STEP 2] Starting Flask backend..."
DEMO_MODE=true python app.py &
FLASK_PID=$!

echo "  Flask started (pid=$FLASK_PID) — waiting for it to be ready..."
for i in $(seq 1 15); do
    if curl -sf "$BASE_URL/api/health" > /dev/null 2>&1; then
        echo "  Flask is ready!"
        break
    fi
    sleep 1
done

# ------------------------------------------------------------------
# Step 3: Register devices
# ------------------------------------------------------------------
echo ""
echo "[STEP 3] Registering simulated IoT devices..."
for i in 1 2 3 4 5; do
    curl -sf -X POST "$BASE_URL/api/devices/register" \
        -H "Content-Type: application/json" \
        -d "{\"device_id\": \"sensor-00$i\", \"ip_address\": \"10.0.0.$i\"}" \
        > /dev/null
    echo "  Registered sensor-00$i at 10.0.0.$i"
done

# ------------------------------------------------------------------
# Step 4: Normal traffic predictions
# ------------------------------------------------------------------
echo ""
echo "[STEP 4] Sending NORMAL traffic flows to ML predictor..."
for i in 1 2 3; do
    result=$(curl -sf -X POST "$BASE_URL/api/predict" \
        -H "Content-Type: application/json" \
        -d "{
            \"source_ip\": \"10.0.0.$i\",
            \"destination_ip\": \"192.168.1.1\",
            \"src_port\": 5000$i,
            \"dst_port\": 1883,
            \"protocol\": \"TCP\",
            \"duration\": 10.0,
            \"packet_count\": 30,
            \"byte_count\": 4800,
            \"packet_rate\": 3.0,
            \"byte_rate\": 480.0,
            \"avg_packet_size\": 160.0
        }")
    echo "  10.0.0.$i → $(echo $result | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['prediction'], f\"(conf={d['data']['confidence']})\")") "
done

# ------------------------------------------------------------------
# Step 5: DDoS traffic predictions
# ------------------------------------------------------------------
echo ""
echo "[STEP 5] Sending DDoS-like traffic flows to ML predictor..."
for i in 6; do
    result=$(curl -sf -X POST "$BASE_URL/api/predict" \
        -H "Content-Type: application/json" \
        -d "{
            \"source_ip\": \"10.0.0.$i\",
            \"destination_ip\": \"192.168.1.1\",
            \"src_port\": 55555,
            \"dst_port\": 80,
            \"protocol\": \"UDP\",
            \"duration\": 0.5,
            \"packet_count\": 3000,
            \"byte_count\": 192000,
            \"packet_rate\": 6000.0,
            \"byte_rate\": 384000.0,
            \"avg_packet_size\": 64.0
        }")
    echo "  10.0.0.$i → $(echo $result | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['prediction'], f\"(conf={d['data']['confidence']})\")") "
done

# ------------------------------------------------------------------
# Step 6: Trigger manual mitigation
# ------------------------------------------------------------------
echo ""
echo "[STEP 6] Triggering manual mitigation for DDoS source..."
mit_result=$(curl -sf -X POST "$BASE_URL/api/mitigate" \
    -H "Content-Type: application/json" \
    -d '{"source_ip": "10.0.0.6"}')
echo "  Mitigation result:"
echo "$mit_result" | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(f\"  action={d['action']} simulated={d['simulated']} success={d['success']}\")"

# ------------------------------------------------------------------
# Step 7: Show alerts
# ------------------------------------------------------------------
echo ""
echo "[STEP 7] Security alerts:"
curl -sf "$BASE_URL/api/alerts" | python3 -c "
import sys, json
data = json.load(sys.stdin)['data']
print(f\"  Total alerts: {data['count']}\")
for a in data['alerts'][:3]:
    print(f\"  [{a['severity']}] {a['alert_type']} from {a['source_ip']} — {a['message'][:60]}\")
"

# ------------------------------------------------------------------
# Step 8: Final metrics
# ------------------------------------------------------------------
echo ""
echo "[STEP 8] System metrics:"
curl -sf "$BASE_URL/api/metrics" | python3 -c "
import sys, json
data = json.load(sys.stdin)['data']
ml = data['ml']
sec = data['security']
print(f\"  ML  — accuracy={ml.get('accuracy')} f1={ml.get('f1_score')} fpr={ml.get('false_positive_rate')}\")
print(f\"  Sec — alerts={sec['total_alerts']} ddos_detected={sec['total_ddos_detected']} blocked={sec['unique_blocked_devices']}\")
"

echo ""
echo "========================================================"
echo "  Demo complete!  Flask will shut down now."
echo "========================================================"
