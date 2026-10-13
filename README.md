# IoT DDoS Detection & Automated SDN Mitigation System

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=flat&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Scikit-Learn](https://img.shields.io/badge/scikit--learn-1.4-F7931E?style=flat&logo=scikit-learn&logoColor=white)](https://scikit-learn.org/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)
[![SDN](https://img.shields.io/badge/SDN-Ryu%20%7C%20OpenFlow%201.3-blue)](https://ryu-sdn.org/)
[![License](https://img.shields.io/badge/License-Academic%20MidSem-green.svg)](#)

An intelligent, end-to-end cybersecurity system designed to protect resource-constrained Internet of Things (IoT) networks against Distributed Denial of Service (DDoS) attacks.

The system combines **real-time network flow monitoring**, **Machine Learning threat classification (Random Forest)**, and **Software-Defined Networking (SDN OpenFlow 1.3)** to automatically detect volumetric flood attacks and install dynamic drop rules at the network ingress, accompanied by a **modern Cyber-Defense Web Dashboard**.

---

## 📑 Table of Contents

- [System Architecture](#-system-architecture)
- [Key Features](#-key-features)
- [Dashboard & Web Interface](#-dashboard--web-interface)
- [Quick Start Guide](#-quick-start-guide)
  - [Option A: Docker (Recommended)](#option-a-docker-recommended)
  - [Option B: Local Python Development](#option-b-local-python-development)
- [Testing the System (Demo Mode)](#-testing-the-system-demo-mode)
- [How Mitigation Works (Suspicious vs. Blocked)](#-how-mitigation-works-suspicious-vs-blocked)
- [REST API Reference](#-rest-api-reference)
- [Project Directory Structure](#-project-directory-structure)
- [Machine Learning Details](#-machine-learning-details)
- [Technology Stack](#-technology-stack)
- [Academic Notice & License](#-academic-notice--license)

---

## 🏛 System Architecture

The project employs a multi-tiered architecture separating the **Data Plane** (IoT network traffic and Open vSwitch), the **Detection & ML Engine**, the **SDN Control Plane** (Ryu Controller), and the **Presentation Layer** (Flask REST API + Nginx + Web UI).

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       Edge & IoT Data Plane                              │
│  [IoT Sensors]  [Security Cameras]  [Smart Gateways]  [Compromised Bots]│
│                           │ (MQTT / TCP / UDP)                          │
│                           ▼                                             │
│               [Open vSwitch (OVS) Switch br0]                           │
└───────────────────────────┬─────────────────────────────────────────────┘
                            │
               Flow Telemetry (Zeek / Synthetic)
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     Ingestion & ML Threat Detection                     │
│  1. Feature Extractor (10 Flow Features: packet_rate, byte_rate, etc.)  │
│  2. StandardScaler & One-Hot Encoding                                    │
│  3. Random Forest Classifier (Normal vs. DDoS Classification)           │
│  4. Confidence & Threshold Evaluator                                    │
└───────────────────────────┬─────────────────────────────────────────────┘
                            │
              DDoS Detected (Conf >= 0.80)
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Mitigation Decision Engine & SDN                     │
│  • Two-Tier State Evaluation:                                           │
│    - Anomalous / Scan (>70 pkts/s)    ──► Set Status: 'suspicious'      │
│    - Volumetric Flood (>=1000 pkts/s) ──► Set Status: 'blocked'         │
│  • Primary: Ryu SDN Controller (REST OpenFlow 1.3 FlowMod Drop Entry)   │
│  • Fallback: Direct OVS command (`ovs-ofctl add-flow br0 ... drop`)     │
└───────────────────────────┬─────────────────────────────────────────────┘
                            │
            State Sync & Persistent Auditing
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                  Persistence & Presentation Layers                      │
│  • SQLite Database (WAL Mode, Thread-Local Storage)                     │
│  • Flask REST API (Port 5000)                                           │
│  • Nginx Reverse Proxy & Static Host (Port 8080)                        │
│  • Cyber-Defense Web Dashboard (Light & Dark Theme)                     │
└─────────────────────────────────────────────────────────────────────────┘
```

> 📖 For an in-depth architectural breakdown, including UML sequence diagrams, OpenFlow flow structures, and database ER models, see [**ARCHITECTURE.md**](file:///e:/MidSemProject/ARCHITECTURE.md).

---

## ✨ Key Features

- **Real-Time Flow Classification:** Detects anomalous and malicious flows within milliseconds using a trained Random Forest model.
- **Automated OpenFlow 1.3 Mitigation:** Drops malicious packets directly at switch ports before they reach the core network or target servers.
- **Two-Tier Threat Management:** Differentiates between light anomalies (`suspicious`) and volumetric floods (`blocked`), avoiding false-positive device cutoffs.
- **Dual-Mode Operation:**
  - **Real SDN Mode:** Integrates with Mininet virtual network topologies, physical Open vSwitch, and the Ryu SDN Controller.
  - **Demo / Standalone Mode:** Generates realistic synthetic traffic profiles (active devices, port-scanners, and high-rate botnet attackers) for testing in Docker or non-Linux environments.
- **Multi-Page Cyber Defense UI:** Modern, responsive dashboard featuring both **Light Theme** (clean high-visibility) and **Dark Theme** (tactical SOC mode).
- **ACID Database Auditing:** Every flow, ML prediction, alert ticket, and mitigation rule is permanently cataloged in SQLite (WAL mode).

---

## 🖥 Dashboard & Web Interface

The frontend is served via Nginx on port `8080` and consists of 6 dedicated pages:

| Page | File | Purpose |
| :--- | :--- | :--- |
| **Dashboard** | `pages/dashboard.html` | High-level overview: System health cards, Live Traffic graph, attack statistics, quick demo controls, and suspicious device alerts. |
| **Device Inventory** | `pages/devices.html` | Comprehensive inventory of all registered IoT nodes with status indicators (`Active`, `Suspicious`, `Blocked`), MAC addresses, and manual block/unblock buttons. |
| **Traffic Monitor** | `pages/traffic.html` | Real-time network telemetry feed showing packet rates, byte rates, duration, and protocol distribution. |
| **Threat Alerts** | `pages/alerts.html` | Categorized security alert feed with severity ratings (`CRITICAL`, `HIGH`, `WARNING`), confidence scores, and timestamps. |
| **Mitigations** | `pages/mitigations.html` | Complete audit log of all OpenFlow drop rules installed, target source IPs, reasons, and mitigation success statuses. |
| **System Diagnostics**| `pages/system.html` | Real-time diagnostic check for all microservices (Flask, SQLite, ML Model, MQTT, Ryu, OVS, Zeek). |

---

## 🚀 Quick Start Guide

### Option A: Docker (Recommended)

The easiest way to run the entire system is using Docker Compose. All microservices (Frontend Nginx, Backend Flask, and Mosquitto MQTT) are orchestrated automatically.

#### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.

#### One-Click Start (Windows)
Double-click `start_docker.bat` or run in terminal:
```powershell
docker-compose up -d --build
```

#### Access the Services
- 🌐 **Web Dashboard:** [http://localhost:8080](http://localhost:8080)
- 🔌 **Backend REST API:** [http://localhost:5000/api/health](http://localhost:5000/api/health)
- 📡 **MQTT Broker:** `localhost:1883`

#### Stopping Docker
Double-click `stop_docker.bat` or run:
```powershell
docker-compose down
```

---

### Option B: Local Python Development

If you wish to run the backend natively on your host machine without Docker:

#### 1. Setup Virtual Environment & Dependencies
```bash
# Navigate to backend directory
cd iot-ddos-filtering

# Create and activate virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### 2. Initialize Database & Train Model
```bash
# Train the Random Forest model (auto-generates dataset if missing)
python -m ml.train
```

#### 3. Start the Flask Backend
```bash
# Run Flask in DEMO mode
python app.py
```
Backend will start at `http://localhost:5000`.

#### 4. Launch the Frontend
You can open `frontend/index.html` in your browser or serve it using any local HTTP server (such as Python's built-in server or VS Code Live Server):
```bash
cd frontend
python -m http.server 8080
```
Then visit `http://localhost:8080`.

---

## 🧪 Testing the System (Demo Mode)

The built-in **Demo Mode** allows you to test the complete detection and mitigation pipeline without needing physical hardware or a Linux kernel:

1. Open the dashboard at **[http://localhost:8080](http://localhost:8080)**.
2. In the top-right control bar, click **"Start Demo"**.
3. **Observe the Pipeline in Action:**
   - **Baseline Traffic:** Normal devices (`10.0.0.1`, `10.0.0.3`, `10.0.0.4`, `10.0.0.5`) generate routine telemetry (10–40 pkts/s).
   - **Attack Burst:** Malicious node (`10.0.0.2`) starts a high-rate volumetric DDoS flood (3,000–8,500 pkts/s).
   - **Graph Spike:** The **Traffic Over Time** chart spikes sharply into the thousands.
   - **ML Detection:** The Random Forest classifier detects `DDOS` with $>98\%$ confidence.
   - **Automated Mitigation:** The decision engine executes `install_block_rule("10.0.0.2")`.
   - **Traffic Drops:** Packets from `10.0.0.2` are dropped; the traffic graph plunges immediately back to normal baseline levels!
   - **Counters Update:** The **Blocked IPs** card increments, and the mitigation record is cataloged in the **Mitigations** tab.
4. **Manual Admin Override:**
   - Notice device `10.0.0.6` (port-scanning bot) flagged as **Suspicious**.
   - Navigate to **Devices** or the **Suspicious Devices** list and click **"Block"** to test manual administrator enforcement.
   - Click **"Unblock"** to restore communication.

---

## 🛡 How Mitigation Works: Suspicious vs. Blocked

The system applies a clear, configurable policy:

```
[ Incoming Flow ] ──► [ Feature Extraction ] ──► [ Random Forest Classifier ]
                                                              │
                                       ┌──────────────────────┴──────────────────────┐
                                       ▼                                             ▼
                                   [ NORMAL ]                                     [ DDOS ]
                                       │                                             │
                                    (ALLOW)                       ┌──────────────────┴──────────────────┐
                                                                  ▼                                     ▼
                                                       Confidence < 0.80 OR                  Confidence >= 0.80 AND
                                                       Rate < 1000 pkts/s                    Rate >= 1000 pkts/s
                                                                  │                                     │
                                                                  ▼                                     ▼
                                                            [ SUSPICIOUS ]                         [ BLOCKED ]
                                                      • Status set to 'suspicious'           • Status set to 'blocked'
                                                      • Alert created (severity HIGH)        • OpenFlow DROP rule installed
                                                      • Manual Block button enabled          • Mitigated flow drops to 0
```

1. **`suspicious` State:**
   - Triggers when traffic exhibits scanning behaviors (>70 pkts/s) or DDoS confidence is below flood threshold (<1000 pkts/s).
   - The device is flagged on the UI and in database table `devices`. Packets are **not** dropped yet to prevent false positives.
2. **`blocked` State:**
   - Triggers when confidence $\ge 0.80$ and volumetric flood rate is confirmed ($\ge 1000$ pkts/s), or upon manual operator action.
   - Ryu injects an OpenFlow flow modification entry (`priority=100, nw_src=<IP>, actions=drop`) into Open vSwitch.
   - All subsequent packets from that IP address are discarded at the switch.

---

## 📡 REST API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Service health status and demo mode state. |
| `GET` | `/api/system/status` | Detailed status of Flask, DB, ML model, MQTT, OVS, and Ryu. |
| `GET` | `/api/traffic/flows` | Returns latest captured/analyzed network flow records. |
| `GET` | `/api/traffic/stats` | Aggregated traffic metrics (total packets, byte rates, averages). |
| `GET` | `/api/devices` | Registered device inventory with statuses (`active`, `suspicious`, `blocked`). |
| `GET` | `/api/alerts` | List of security alerts and threat incidents. |
| `GET` | `/api/mitigations` | History of installed OpenFlow mitigation rules. |
| `POST` | `/api/mitigate` | Manually block an IP (`{"source_ip": "10.0.0.4"}`). |
| `POST` | `/api/unblock` | Remove a block rule and restore device status. |
| `POST` | `/api/demo/start` | Start live telemetry generation and threat simulation. |
| `POST` | `/api/demo/stop` | Pause telemetry generation and simulation loop. |
| `POST` | `/api/predict` | Run manual ML inference on a custom feature payload. |

---

## 📁 Project Directory Structure

```
.
├── ARCHITECTURE.md              # In-depth technical architecture specification
├── DOCKER.md                    # Docker deployment and troubleshooting guide
├── INTEGRATION.md               # Backend-to-frontend integration notes
├── README.md                    # Primary repository overview (this document)
├── docker-compose.yml           # Multi-container orchestration (Frontend, Backend, MQTT)
├── start_docker.bat             # Windows one-click Docker startup script
├── stop_docker.bat              # Windows one-click Docker teardown script
│
├── frontend/                    # Web Presentation Layer
│   ├── Dockerfile               # Nginx Alpine container definition
│   ├── nginx.conf               # Nginx reverse proxy configuration
│   ├── index.html               # Frontend entry redirector
│   ├── pages/                   # Multi-page dashboard views
│   │   ├── dashboard.html       # Overview & live charts
│   │   ├── devices.html         # IoT inventory & management
│   │   ├── traffic.html         # Network flow analysis
│   │   ├── alerts.html          # Threat alert feed
│   │   ├── mitigations.html     # OpenFlow rules audit table
│   │   └── system.html          # Service health monitoring
│   ├── css/                     # Responsive CSS3 styles (Light & Dark theme variables)
│   └── js/                      # Modular JavaScript client (API client, charts, state)
│
└── iot-ddos-filtering/          # Backend Application & ML Pipeline
    ├── Dockerfile               # Python 3.11 backend container definition
    ├── app.py                   # Flask application entry point
    ├── config.py                # System settings and thresholds
    ├── requirements.txt         # Python dependencies
    ├── api/                     # REST API Blueprint routes
    ├── database/                # SQLite connection pool and repository
    ├── mitigation/              # Decision engine & OpenFlow rule manager
    ├── ml/                      # Scikit-Learn training, inference, and models
    │   └── artifacts/           # Serialized model, scaler, and metrics
    ├── monitoring/              # Flow extraction and background traffic daemon
    ├── network/                 # Mininet topology, OVS manager, and MQTT client
    └── ryu/                     # Ryu SDN OpenFlow 1.3 controller client
```

---

## 🤖 Machine Learning Details

- **Algorithm:** Random Forest Classifier (`RandomForestClassifier`)
- **Number of Trees:** 100
- **Evaluation Metrics:**
  - **Accuracy:** $> 99.2\%$
  - **Precision:** $> 99.4\%$
  - **Recall:** $> 99.1\%$
  - **F1 Score:** $> 99.2\%$
  - **False Positive Rate (FPR):** $< 0.5\%$
- **Key Features Extracted from Network Flows:**
  1. `duration` (connection duration in seconds)
  2. `packet_count` (total packets in flow)
  3. `byte_count` (total payload in bytes)
  4. `packet_rate` (packets transmitted per second)
  5. `byte_rate` (bytes transmitted per second)
  6. `avg_packet_size` (average payload size per packet)
  7. `protocol` (TCP / UDP / ICMP encoding)
  8. `source_port` & `destination_port`

---

## 🛠 Technology Stack

- **Backend:** Python 3.11, Flask 3.x, Werkzeug
- **Machine Learning:** Scikit-Learn, NumPy, Pandas, Joblib
- **Database:** SQLite 3 (WAL mode with thread-local pooling)
- **SDN & Networking:** Ryu SDN Controller, OpenFlow 1.3, Open vSwitch (OVS), Mininet
- **Messaging:** Eclipse Mosquitto, Paho-MQTT
- **Frontend:** HTML5, CSS3 Variables (Light/Dark themes), Vanilla JavaScript (ES6+), Chart.js
- **Web Server:** Nginx 1.25 Alpine
- **Containerization:** Docker, Docker Compose

---

## 📄 Academic Notice & License

This project was developed as an **Academic Mid-Semester Engineering Project** to demonstrate the feasibility of combining Machine Learning classification with Software-Defined Networking (SDN) for real-time cyber defense in Internet of Things networks.

Released under the **MIT License**. Free for educational, research, and non-commercial development.

