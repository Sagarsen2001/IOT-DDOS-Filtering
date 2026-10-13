# IoT DDoS Filtering — Intelligent ML-Based Traffic Filtering System

> **Academic Mid-Semester Lab Project**  
> An end-to-end backend system for detecting and mitigating DDoS attacks in
> simulated IoT networks using Machine Learning, Ryu SDN, and Open vSwitch.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Technologies Used](#3-technologies-used)
4. [Directory Structure](#4-directory-structure)
5. [Ubuntu Prerequisites](#5-ubuntu-prerequisites)
6. [Installation](#6-installation)
7. [Database Setup](#7-database-setup)
8. [Dataset Generation](#8-dataset-generation)
9. [Model Training](#9-model-training)
10. [Running Flask](#10-running-flask)
11. [Starting Mosquitto](#11-starting-mosquitto)
12. [Starting Ryu](#12-starting-ryu)
13. [Starting Mininet](#13-starting-mininet)
14. [Generating Traffic](#14-generating-traffic)
15. [Running DEMO MODE](#15-running-demo-mode)
16. [API Documentation](#16-api-documentation)
17. [Metrics](#17-metrics)
18. [Testing](#18-testing)
19. [Docker](#19-docker)
20. [Troubleshooting](#20-troubleshooting)
21. [Limitations](#21-limitations)
22. [Future Improvements](#22-future-improvements)

---

## 1. Project Overview

This system demonstrates an end-to-end pipeline for detecting DDoS attacks
originating from compromised IoT devices and automatically blocking them
at the SDN layer.

**The complete pipeline:**

```
IoT devices (Mininet hosts)
        ↓
Open vSwitch (OVS)
        ↓
MQTT / network traffic
        ↓
Zeek (flow monitoring)
        ↓
Feature extraction
        ↓
RandomForest ML model
        ↓
NORMAL / DDOS classification
        ↓
Decision Engine (confidence threshold)
        ↓
Ryu SDN Controller
        ↓
OVS blocking rule → traffic dropped
        ↓
Metrics + SQLite database
        ↓
Flask REST API (ready for frontend)
```

**DEMO MODE** — The system fully supports running without Mininet, Ryu, OVS,
or Zeek installed. Synthetic data is used, all mitigation is simulated, and
every simulated action is clearly logged as such.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Flask REST API                        │
│  /api/health  /api/predict  /api/mitigate  /api/metrics │
└───────────────────────┬─────────────────────────────────┘
                        │
          ┌─────────────▼──────────────┐
          │     Background Monitor      │
          │  (TrafficMonitor daemon)    │
          └────────┬───────────────────┘
                   │
       ┌───────────▼──────────┐
       │   Feature Extractor  │
       └───────────┬──────────┘
                   │
       ┌───────────▼──────────┐
       │  RandomForest ML      │  ← trained on synthetic/real flows
       └───────────┬──────────┘
                   │
       ┌───────────▼──────────┐
       │   Decision Engine     │  ← confidence + rate thresholds
       └───────────┬──────────┘
                   │
       ┌───────────▼──────────┐
       │   Rule Manager        │
       │  Ryu REST ──► OVS    │  ← installs DROP rules
       └───────────────────────┘
```

---

## 3. Technologies Used

| Component       | Technology                        |
|-----------------|-----------------------------------|
| Backend API     | Python 3.11 + Flask 3.x           |
| ML              | scikit-learn RandomForestClassifier|
| Database        | SQLite (via stdlib sqlite3)        |
| MQTT            | Mosquitto + paho-mqtt             |
| Network emulation | Mininet + Open vSwitch           |
| SDN Controller  | Ryu (OpenFlow 1.3)               |
| Flow monitoring | Zeek (conn.log parser)            |
| Serialisation   | joblib (model artifacts)          |
| Testing         | pytest                            |
| Containerisation| Docker + docker-compose           |

---

## 4. Directory Structure

```
iot-ddos-filtering/
├── app.py                    ← Flask application factory
├── config.py                 ← All configuration (env-based)
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── README.md
│
├── api/                      ← Flask blueprints
│   ├── routes_devices.py
│   ├── routes_traffic.py
│   ├── routes_detection.py
│   ├── routes_metrics.py
│   ├── routes_control.py
│   └── utils.py
│
├── database/
│   ├── db.py                 ← Connection management + schema
│   ├── models.py             ← Dataclasses
│   └── repository.py        ← All SQL operations
│
├── ml/
│   ├── dataset.py            ← Synthetic dataset generator
│   ├── preprocess.py        ← Feature engineering pipeline
│   ├── train.py             ← Training entry-point
│   ├── predict.py           ← Inference module
│   ├── evaluate.py          ← Metrics calculation
│   ├── model.py             ← Save/load utilities
│   └── artifacts/           ← Trained model + scaler + encoder
│
├── monitoring/
│   ├── zeek_parser.py       ← Zeek conn.log parser
│   ├── feature_extractor.py ← Feature normalisation
│   └── traffic_monitor.py   ← Background daemon thread
│
├── network/
│   ├── mqtt_client.py       ← MQTT client wrapper
│   ├── traffic_generator.py ← Controlled traffic generator
│   ├── mininet_topology.py  ← Mininet IoT topology
│   └── ovs_manager.py       ← OVS command abstraction
│
├── ryu/
│   └── ddos_controller.py   ← Ryu app + REST client
│
├── mitigation/
│   ├── decision_engine.py   ← ALLOW / WARN / MITIGATE logic
│   └── rule_manager.py      ← Coordinates Ryu + OVS
│
├── metrics/
│   └── calculator.py        ← ML + network + security metrics
│
├── data/
│   ├── raw/
│   ├── processed/           ← dataset.csv saved here
│   └── samples/             ← sample_zeek_conn.log
│
├── tests/
│   ├── conftest.py
│   ├── test_features.py
│   ├── test_ml.py
│   ├── test_decision_engine.py
│   └── test_api.py
│
└── scripts/
    ├── setup_environment.sh
    ├── generate_sample_dataset.py
    ├── train_model.sh
    └── run_demo.sh
```

---

## 5. Ubuntu Prerequisites

```bash
# System packages
sudo apt-get update
sudo apt-get install -y \
    python3.11 python3.11-venv python3-pip \
    mosquitto mosquitto-clients \
    zeek \
    openvswitch-switch \
    mininet \
    net-tools curl git
```

> **Note:** Ryu is installed as a Python package (see Installation).
> Mininet, OVS, and Zeek require Ubuntu 20.04 or 22.04.

---

## 6. Installation

```bash
# Clone or copy the project
cd iot-ddos-filtering

# Create and activate virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# (Optional) Install Ryu for real SDN control
pip install ryu

# Copy and edit configuration
cp .env.example .env
# Edit .env as needed (defaults work for DEMO MODE)
```

Or use the setup script:

```bash
bash scripts/setup_environment.sh
```

---

## 7. Database Setup

The database is initialised automatically on `python app.py`. To initialise manually:

```bash
python -c "from database.db import init_db; init_db()"
```

The SQLite file is created at the path in `DATABASE_PATH` (default: `data/iot_ddos.db`).

---

## 8. Dataset Generation

```bash
# Generate default 5000-sample dataset
python scripts/generate_sample_dataset.py

# Custom size and seed
python scripts/generate_sample_dataset.py --size 10000 --seed 42

# Output: data/processed/dataset.csv
```

The generated dataset contains:
- **65% NORMAL** flows: low packet rate, normal MQTT telemetry patterns
- **35% DDOS** flows: high packet rate (>500 pkt/s), high byte rate, short duration

> ⚠️ **Important:** This is a **synthetic dataset for prototyping only**.
> For real deployment, replace it with actual Zeek-captured flow data.

---

## 9. Model Training

```bash
# Quick method
bash scripts/train_model.sh

# Or manually
python -m ml.train

# Output:
#   ml/artifacts/rf_model.joblib   ← trained RandomForest
#   ml/artifacts/scaler.joblib     ← fitted StandardScaler
#   ml/artifacts/encoder.joblib    ← fitted LabelEncoder
#   ml/artifacts/metrics.json      ← evaluation results
```

Expected metrics on the synthetic dataset:

| Metric    | Expected   |
|-----------|------------|
| Accuracy  | ≥ 0.95     |
| F1-score  | ≥ 0.94     |
| FPR       | ≤ 0.05     |

---

## 10. Running Flask

```bash
# Activate venv first
source venv/bin/activate

# DEMO MODE (no Ryu/OVS/Zeek required)
DEMO_MODE=true python app.py

# Production-like (requires all components running)
DEMO_MODE=false python app.py

# With custom port
FLASK_PORT=8080 python app.py
```

Flask starts at: **http://localhost:5000**

---

## 11. Starting Mosquitto

```bash
# System service (Ubuntu)
sudo systemctl start mosquitto
sudo systemctl status mosquitto

# Or run manually for testing
mosquitto -v

# Test publish/subscribe
mosquitto_pub -t "iot/sensor-001/telemetry" -m '{"temp": 25.3}'
mosquitto_sub -t "iot/+/telemetry"
```

---

## 12. Starting Ryu

```bash
# Install Ryu (requires Python 3.8 for full compatibility)
pip install ryu

# Start the DDoS controller
ryu-manager ryu/ddos_controller.py --observe-links --verbose

# Ryu REST API will be available at http://localhost:8080
```

> **Note:** Ryu officially supports Python 3.8. If using Python 3.11,
> some Ryu internals may emit deprecation warnings. The core functionality
> (OpenFlow event handling, REST API) still works.

---

## 13. Starting Mininet

```bash
# Must be run as root
sudo mn --topo single,7 \
        --controller remote,ip=127.0.0.1,port=6653 \
        --switch ovsk,protocols=OpenFlow13

# Or use the project topology (requires root)
sudo python network/mininet_topology.py
```

Once Mininet is running, you can open xterm windows:
```
mininet> xterm h1 h6
# h1: normal IoT device
# h6: simulated attacker (DDoS source)
```

---

## 14. Generating Traffic

**Normal traffic (MQTT telemetry):**
```bash
python -m network.traffic_generator --mode normal --rate 2 --duration 60
```

**DDoS simulation (high-rate bursts — lab only):**
```bash
python -m network.traffic_generator --mode attack --rate 500 --duration 10
```

**Without MQTT broker:**
```bash
python -m network.traffic_generator --mode attack --rate 200 --duration 5 --no-mqtt
```

---

## 15. Running DEMO MODE

The complete end-to-end demo in one command:

```bash
bash scripts/run_demo.sh
```

This will:
1. Generate dataset and train the model.
2. Start Flask in the background.
3. Register 5 simulated IoT devices.
4. Send NORMAL traffic flows → classified as NORMAL.
5. Send DDoS-like traffic flows → classified as DDOS.
6. Trigger manual mitigation → simulated OVS block rule.
7. Display alerts, mitigations, and final metrics.

---

## 16. API Documentation

All responses follow the format:

**Success:**
```json
{
  "success": true,
  "data": { ... },
  "timestamp": "2024-01-15T10:00:00+00:00"
}
```

**Error:**
```json
{
  "success": false,
  "error": {
    "code": "INVALID_INPUT",
    "message": "source_ip is required"
  },
  "timestamp": "2024-01-15T10:00:00+00:00"
}
```

---

### GET /api/health
Quick health check.

```bash
curl http://localhost:5000/api/health
```

---

### GET /api/system/status
Detailed component status.

```bash
curl http://localhost:5000/api/system/status
```

Response `data` includes: `flask`, `database`, `ml_model`, `mqtt`, `ovs`, `ryu`, `zeek`, `demo_mode`.

---

### GET /api/devices
List all registered IoT devices.

```bash
curl http://localhost:5000/api/devices
```

---

### GET /api/devices/{device_id}
Get a specific device.

```bash
curl http://localhost:5000/api/devices/sensor-001
```

---

### POST /api/devices/register
Register a new IoT device.

```bash
curl -X POST http://localhost:5000/api/devices/register \
  -H "Content-Type: application/json" \
  -d '{"device_id": "sensor-001", "ip_address": "10.0.0.1", "mac_address": "aa:bb:cc:dd:ee:01"}'
```

---

### GET /api/traffic
Query traffic flows with optional filters.

```bash
# All flows
curl http://localhost:5000/api/traffic

# Filter by source IP
curl "http://localhost:5000/api/traffic?source_ip=10.0.0.6"

# Filter by prediction
curl "http://localhost:5000/api/traffic?prediction=DDOS"

# Time range
curl "http://localhost:5000/api/traffic?start_time=2024-01-01&end_time=2024-12-31"
```

---

### POST /api/predict
Classify a single network flow.

```bash
curl -X POST http://localhost:5000/api/predict \
  -H "Content-Type: application/json" \
  -d '{
    "source_ip": "10.0.0.6",
    "destination_ip": "192.168.1.1",
    "src_port": 55555,
    "dst_port": 80,
    "protocol": "UDP",
    "duration": 0.5,
    "packet_count": 3000,
    "byte_count": 192000,
    "packet_rate": 6000.0,
    "byte_rate": 384000.0,
    "avg_packet_size": 64.0
  }'
```

Response:
```json
{
  "success": true,
  "data": {
    "prediction": "DDOS",
    "label": 1,
    "probability": 0.97,
    "confidence": 0.97,
    "model_version": "rf-v1",
    "timestamp": "2024-01-15T10:00:00+00:00"
  }
}
```

---

### GET /api/detections
Recent ML predictions.

```bash
curl "http://localhost:5000/api/detections?limit=50"
```

---

### GET /api/alerts
Recent security alerts.

```bash
curl "http://localhost:5000/api/alerts?limit=20"
```

---

### POST /api/mitigate
Manually block a source IP.

```bash
curl -X POST http://localhost:5000/api/mitigate \
  -H "Content-Type: application/json" \
  -d '{"source_ip": "10.0.0.6"}'
```

Response in DEMO MODE:
```json
{
  "success": true,
  "data": {
    "success": true,
    "simulated": true,
    "action": "BLOCK",
    "source_ip": "10.0.0.6",
    "message": "Simulated OVS blocking rule for 10.0.0.6"
  }
}
```

---

### GET /api/mitigations
Mitigation action history.

```bash
curl http://localhost:5000/api/mitigations
```

---

### GET /api/metrics
All system metrics.

```bash
curl http://localhost:5000/api/metrics
```

---

### POST /api/demo/start / POST /api/demo/stop
Start or stop the background monitoring demo.

```bash
curl -X POST http://localhost:5000/api/demo/start
curl -X POST http://localhost:5000/api/demo/stop
```

---

## 17. Metrics

| Category | Metric                  | Source                              |
|----------|-------------------------|-------------------------------------|
| ML       | Accuracy                | Saved from last training run        |
| ML       | Precision / Recall / F1 | Saved from last training run        |
| ML       | False Positive Rate     | FP / (FP + TN) from evaluation      |
| Network  | Average throughput (bps)| Computed from stored flow byte_rate |
| Network  | Average flow duration   | Computed from stored flows          |
| Security | Total alerts            | Counted from alerts table           |
| Security | DDoS detections         | Counted from predictions table      |
| Security | Unique blocked devices  | Counted from mitigation_actions     |
| Security | Average detection time  | Flow timestamp → prediction time    |

> **Honesty policy:** Metrics that cannot be computed from available data
> return `null` (JSON `null`) rather than fabricated values.

---

## 18. Testing

```bash
# Run all tests
pytest -q

# With coverage
pytest --cov=. --cov-report=term-missing -q

# Run specific test file
pytest tests/test_ml.py -v
pytest tests/test_api.py -v
pytest tests/test_decision_engine.py -v
pytest tests/test_features.py -v
```

**Tests do NOT require:**
- A running Flask server
- Mosquitto MQTT broker
- Ryu controller
- OVS switch
- Zeek

All external dependencies are mocked.

---

## 19. Docker

**Flask backend + MQTT broker only:**

```bash
# Build and start
docker compose up --build

# Stop
docker compose down
```

> ⚠️ **Mininet, OVS, and Ryu cannot be containerised** reliably because
> they require Linux kernel modules (netns, OVS kernel module) that are
> not available in standard Docker containers. Run them on the native
> Ubuntu host.

The Flask backend will be available at **http://localhost:5000** with
MQTT on **localhost:1883**.

---

## 20. Troubleshooting

| Problem | Solution |
|---------|----------|
| `Model not found` error | Run `python -m ml.train` first |
| MQTT disconnected | Start Mosquitto: `sudo systemctl start mosquitto` |
| `OVS unavailable` | Install: `sudo apt install openvswitch-switch` |
| Ryu unreachable | Start: `ryu-manager ryu/ddos_controller.py` |
| `ModuleNotFoundError` | Activate venv: `source venv/bin/activate` |
| Database error | Check permissions on `data/` directory |
| Port 5000 in use | Set `FLASK_PORT=8080` in `.env` |
| Zeek log not found | Set `DEMO_MODE=true` or configure `ZEEK_LOG_PATH` |
| Mininet permission denied | Run with: `sudo python network/mininet_topology.py` |

---

## 21. Limitations

1. **Synthetic dataset**: The default dataset is generated algorithmically.
   Results will improve significantly with real Zeek-captured traffic.

2. **Ryu Python version**: Ryu is tested on Python 3.8. Python 3.11 may
   produce deprecation warnings. The Ryu REST client in `RyuClient` works
   with any Python version.

3. **No Mininet containerisation**: Mininet and OVS require kernel modules
   and root access — they cannot run inside Docker containers.

4. **Packet loss and latency metrics**: These require active network probes
   (e.g., ping, iperf). The current implementation returns `null` for these
   until probing is added.

5. **Single-switch topology**: The Mininet topology uses one OVS switch.
   Multi-switch topologies would require spanning tree or additional routing.

6. **No user authentication**: This is an academic lab project. The API
   has no authentication. Do not expose it on a public network.

---

## 22. Future Improvements

- Replace synthetic dataset with real Zeek-captured PCAP flows.
- Add active network probing for latency/packet-loss metrics.
- Implement per-device traffic baseline tracking.
- Add multi-switch Mininet topology with multiple controllers.
- Integrate Suricata as a secondary validation source.
- Add JWT authentication to the REST API.
- Build the HTML/CSS/JavaScript frontend dashboard.
- Implement automatic model retraining when new labelled data arrives.
- Add IPv6 support for both detection and OVS rules.
- Export metrics to Prometheus/Grafana for real-time visualisation.
