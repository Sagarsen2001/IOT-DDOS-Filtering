# 🐳 Docker Setup — IoT DDoS Filtering System

> **Intelligent ML-Based Traffic Filtering and DDoS Detection for IoT Networks**

This guide explains how to run the complete project using Docker Compose.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Docker Compose Network                       │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │   Frontend   │    │   Backend    │    │    Mosquitto     │   │
│  │   (Nginx)   │───▶│   (Flask)   │───▶│   MQTT Broker     │   │
│  │  Port 8080   │    │  Port 5000   │    │   Port 1883      │   │
│  │              │    │              │    │                  │   │
│  │  Dashboard   │    │  ML Model    │    │  IoT Telemetry   │   │
│  │  HTML/CSS/JS │    │  SQLite DB   │    │                  │   │
│  └──────────────┘    └──────────────┘    └──────────────────┘   │
│         │                   │                                   │
│         │   /api/* proxy    │                                   │
│         └───────────────────┘                                   │
└─────────────────────────────────────────────────────────────────┘
          │
    Browser → http://localhost:8080
```

**Request flow:**
1. Browser opens `http://localhost:8080` → Nginx serves the dashboard HTML/CSS/JS
2. Dashboard JavaScript calls `/api/health`, `/api/traffic`, etc.
3. Nginx proxies `/api/*` requests to the Flask backend container on the internal Docker network
4. Flask processes the request (ML inference, SQLite queries, etc.) and returns JSON
5. Dashboard renders the response

---

## Prerequisites

| Requirement | Version |
|---|---|
| **Docker Desktop** (Windows/macOS) or **Docker Engine** (Linux) | ≥ 24.0 |
| **Docker Compose** (V2, included with Docker Desktop) | ≥ 2.20 |
| **Disk space** | ~1.5 GB for images |
| **RAM** | ≥ 4 GB recommended |

### Windows-Specific
- Docker Desktop must be running (check the system tray icon)
- WSL 2 backend is recommended (Docker Desktop → Settings → General → Use WSL 2)
- If using Hyper-V, ensure it's enabled in Windows Features

### Verify Docker
```bash
docker --version          # Docker version 29.x+
docker compose version    # Docker Compose version v5.x+
```

---

## Directory Structure

```
E:\MidSemProject\
├── docker-compose.yml          ← Orchestrates all services
├── .env.docker.example         ← Environment variable template
├── .env                        ← Your local settings (create from template)
├── .gitignore
├── DOCKER.md                   ← This file
│
├── iot-ddos-filtering/         ← Flask backend
│   ├── Dockerfile              ← Backend container image
│   ├── .dockerignore
│   ├── app.py                  ← Entry point
│   ├── config.py               ← All env var configuration
│   ├── requirements.txt
│   ├── ml/artifacts/           ← Trained ML model (included in image)
│   │   ├── rf_model.joblib
│   │   ├── scaler.joblib
│   │   ├── encoder.joblib
│   │   └── metrics.json
│   ├── data/                   ← SQLite database (Docker volume)
│   ├── docker/
│   │   └── mosquitto.conf      ← MQTT broker configuration
│   └── ...
│
└── frontend/                   ← Static dashboard
    ├── Dockerfile              ← Frontend container image
    ├── .dockerignore
    ├── nginx.conf              ← Nginx + API reverse proxy
    ├── index.html
    ├── pages/                  ← Dashboard pages
    ├── css/                    ← Stylesheets
    ├── js/                     ← JavaScript (API client, config)
    └── assets/                 ← Icons, images
```

---

## Quick Start

### 1. Environment Setup (optional)

```bash
# Copy the example env file
cp .env.docker.example .env

# Edit .env if you need to change ports or settings
# Default values work out of the box
```

### 2. Build and Start

```bash
# From E:\MidSemProject (where docker-compose.yml lives)
docker compose up --build
```

This will:
1. Build the Flask backend image (installs Python deps, copies ML model)
2. Build the Nginx frontend image (copies HTML/CSS/JS, configures proxy)
3. Start Mosquitto MQTT broker
4. Start the Flask backend (initializes DB, loads ML model)
5. Wait for backend health check to pass
6. Start the Nginx frontend

### 3. Open the Dashboard

Open your browser and go to:

> **[http://localhost:8080](http://localhost:8080)**

You'll be redirected to the dashboard. Click **Start Demo** to begin generating synthetic traffic.

---

## Commands Reference

| Action | Command |
|---|---|
| Build + start (foreground) | `docker compose up --build` |
| Build + start (background) | `docker compose up --build -d` |
| View all logs | `docker compose logs -f` |
| View backend logs | `docker compose logs -f backend` |
| View frontend logs | `docker compose logs -f frontend` |
| View MQTT logs | `docker compose logs -f mosquitto` |
| Check service status | `docker compose ps` |
| Stop services | `docker compose down` |
| Stop + delete data volumes | `docker compose down -v` |
| Rebuild after code changes | `docker compose up --build` |
| Restart a single service | `docker compose restart backend` |

---

## URLs

| Service | URL | Purpose |
|---|---|---|
| Dashboard | http://localhost:8080 | Main frontend UI |
| Flask API (direct) | http://localhost:5000/api/health | Backend health check (debug) |
| API via proxy | http://localhost:8080/api/health | Same API through Nginx |
| MQTT Broker | localhost:1883 | IoT device telemetry |

---

## Environment Variables

Create a `.env` file from the template:

```bash
cp .env.docker.example .env
```

| Variable | Default | Description |
|---|---|---|
| `FRONTEND_HOST_PORT` | `8080` | Host port for the dashboard |
| `BACKEND_HOST_PORT` | `5000` | Host port for direct API access |
| `MQTT_HOST_PORT` | `1883` | Host port for MQTT broker |
| `DEMO_MODE` | `true` | Enable synthetic traffic generation |
| `FLASK_DEBUG` | `false` | Flask debug mode (disable in production) |
| `SECRET_KEY` | `change-me-in-production` | Flask session secret |
| `DETECTION_THRESHOLD` | `0.7` | ML detection confidence threshold |
| `MITIGATION_ENABLED` | `false` | Enable OVS/Ryu mitigation rules |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `MONITOR_INTERVAL_SECONDS` | `5.0` | Traffic monitoring poll interval |

> [!IMPORTANT]
> `MITIGATION_ENABLED` is `false` by default for safety. In Docker demo mode, mitigation is always **simulated** regardless of this setting.

---

## Database Persistence

SQLite data is stored in a Docker named volume (`backend-data`):

- **Survives** `docker compose down` (normal stop)
- **Deleted by** `docker compose down -v` (explicit volume removal)

The volume maps to `/app/data/` inside the backend container.

To inspect the database:
```bash
docker compose exec backend sqlite3 /app/data/iot_ddos.db ".tables"
```

---

## ML Model

The trained model artifacts are **baked into the Docker image** at build time:
- `ml/artifacts/rf_model.joblib` — Random Forest classifier
- `ml/artifacts/scaler.joblib` — Feature scaler
- `ml/artifacts/encoder.joblib` — Protocol label encoder
- `ml/artifacts/metrics.json` — Evaluation metrics

### If the model is missing

If you see `ML model not loaded` in the logs, train it first:

```bash
cd iot-ddos-filtering
python -m ml.train
```

Then rebuild:
```bash
docker compose up --build
```

### Model Compatibility

The model was trained with:
- Python 3.13 / scikit-learn ≥ 1.4 / joblib ≥ 1.3
- The Docker image uses Python 3.11 (compatible with scikit-learn ≥ 1.4)

If you encounter version mismatch errors, retrain the model inside Docker:
```bash
docker compose exec backend python -m ml.train
```

---

## MQTT Configuration

Mosquitto runs with a minimal configuration (`docker/mosquitto.conf`):
- Listener on port 1883 (TCP)
- Anonymous access allowed (lab environment)
- WebSocket listener on port 9001 (optional)

The backend connects to MQTT using the Docker Compose service name `mosquitto` (not `localhost`).

---

## Troubleshooting

### Port Conflicts

If port 8080, 5000, or 1883 is already in use:

```bash
# Option 1: Change in .env
FRONTEND_HOST_PORT=8081
BACKEND_HOST_PORT=5001

# Option 2: Inline override
FRONTEND_HOST_PORT=8081 docker compose up --build
```

### "Backend unreachable" in Dashboard

1. Check if backend is running: `docker compose ps`
2. Check backend logs: `docker compose logs backend`
3. Test health endpoint: `curl http://localhost:5000/api/health`
4. The frontend depends on the backend health check — if the backend is slow to start, wait ~15 seconds

### Docker Desktop Not Running (Windows)

```
failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine
```

→ Open Docker Desktop from the Start menu or system tray.

### WSL 2 Issues

If Docker Desktop fails to start:
1. Ensure WSL 2 is installed: `wsl --install`
2. Update WSL: `wsl --update`
3. Restart Docker Desktop

### Container Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend

# Last 100 lines
docker compose logs --tail 100 backend
```

### Rebuild From Scratch

```bash
docker compose down -v              # Stop + delete volumes
docker compose build --no-cache     # Force full rebuild
docker compose up -d                # Start fresh
```

---

## Linux/Ubuntu Lab Networking

> [!WARNING]
> Mininet, Open vSwitch, Ryu Controller, and Zeek **cannot run inside standard Docker containers**. They require Linux kernel networking features (network namespaces, kernel modules, packet capture capabilities).

### What Works in Docker
| Component | Docker Status |
|---|---|
| Flask API + ML | ✅ Fully functional |
| SQLite database | ✅ Persistent volume |
| MQTT broker | ✅ Mosquitto container |
| Dashboard UI | ✅ Nginx container |
| Demo Mode (synthetic traffic) | ✅ Built-in |

### What Requires Ubuntu Host
| Component | Requirement |
|---|---|
| Mininet | Linux kernel, `sudo apt install mininet` |
| Open vSwitch | Kernel modules, `sudo apt install openvswitch-switch` |
| Ryu Controller | Python 3.8 recommended, `pip install ryu` |
| Zeek IDS | Linux, `sudo apt install zeek` |

### Running the Full Lab on Ubuntu

1. Install host dependencies:
   ```bash
   sudo apt install mininet openvswitch-switch zeek
   pip install ryu
   ```

2. Start the Docker services (backend, frontend, MQTT):
   ```bash
   docker compose up -d
   ```

3. Start Ryu on the host:
   ```bash
   ryu-manager iot-ddos-filtering/ryu/ddos_controller.py --observe-links
   ```

4. Configure the backend to connect to host services:
   ```bash
   # In .env
   DEMO_MODE=false
   MITIGATION_ENABLED=true
   RYU_HOST=host.docker.internal    # Docker's host gateway
   ```

5. Start the Mininet topology on the host:
   ```bash
   sudo python iot-ddos-filtering/network/mininet_topology.py
   ```

> [!CAUTION]
> Setting `MITIGATION_ENABLED=true` will install **real OVS flow rules** that drop traffic. Only enable this in a controlled lab environment with Mininet virtual networks.

---

## Known Limitations

1. **DEMO MODE only on Windows/macOS**: Mininet and OVS require a Linux host. Docker containers always run in demo mode on non-Linux systems.

2. **SQLite concurrency**: SQLite uses WAL mode for concurrent reads, but heavy write loads may encounter locking. This is acceptable for the academic demo workload.

3. **No hot-reload**: Code changes require `docker compose up --build` to take effect.

4. **Model retraining**: Must be done locally (`python -m ml.train`) followed by a Docker rebuild, or inside the container (`docker compose exec backend python -m ml.train`).

5. **Simulated mitigation**: In Docker demo mode, all mitigation actions (IP blocking) are simulated and clearly labeled as such in the dashboard. No real network rules are installed.

---

## Security Notes

- The backend runs as a **non-root user** inside the container
- No privileged capabilities are used
- MQTT uses anonymous auth (appropriate for isolated lab use)
- `SECRET_KEY` should be changed from the default for any non-lab deployment
- The Flask API allows CORS from any origin (required for the separate frontend)
- No host filesystem mounts are used (data lives in Docker volumes)

