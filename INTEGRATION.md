# Frontend-Backend Integration Map

## Overview
This document maps each frontend screen of the IoT DDoS Monitor to its respective JavaScript controller and the backend Flask API endpoints it consumes.

## 1. Dashboard (`pages/dashboard.html`)
**Controller:** `js/dashboard.js`

| Backend Endpoint | Method | Params | Response Shape | Frontend Fields Used |
|------------------|--------|--------|----------------|----------------------|
| `/api/health` | GET | None | `{ status, service, demo_mode }` | Connection status dot |
| `/api/system/status` | GET | None | `{ flask, database, ml_model, mqtt, zeek, ryu, ovs, demo_running }` | System Status grid icons |
| `/api/devices` | GET | None | `{ devices: [...], count }` | KPIs: total devices, active devices |
| `/api/traffic` | GET | `?limit=100` | `{ flows: [...], count }` | Chart: Traffic Over Time & Distribution |
| `/api/alerts` | GET | `?limit=50` | `{ alerts: [...], count }` | Recent Alerts list |
| `/api/detections` | GET | `?limit=50` | `{ detections: [...], count }` | Suspicious Devices list |
| `/api/mitigations` | GET | `?limit=5` | `{ mitigations: [...], count }` | Used for KPI checks |
| `/api/metrics` | GET | None | `{ ml, network, security, timestamp }` | KPIs: ML Accuracy, False Positive Rate |
| `/api/mitigate` | POST | `{ source_ip }` | `{ success, simulated, action, rule_id }` | Quick block actions |
| `/api/demo/start` | POST | None | `{ message, demo_mode }` | Start Demo Button |
| `/api/demo/stop` | POST | None | `{ message }` | Stop Demo Button |

---

## 2. IoT Devices (`pages/devices.html`)
**Controller:** `js/devices.js`

| Backend Endpoint | Method | Params | Response Shape | Frontend Fields Used |
|------------------|--------|--------|----------------|----------------------|
| `/api/devices` | GET | None | `{ devices: [...], count }` | Table: ID, IP, MAC, Status, Last Seen |
| `/api/detections`| GET | `?limit=10` | `{ detections: [...], count }` | Prediction badge on table row & modal |
| `/api/mitigate` | POST | `{ source_ip }` | `{ success, action }` | Block Device action in modal |

---

## 3. Traffic Monitor (`pages/traffic.html`)
**Controller:** `js/traffic.js`

| Backend Endpoint | Method | Params | Response Shape | Frontend Fields Used |
|------------------|--------|--------|----------------|----------------------|
| `/api/traffic` | GET | `?limit=X` | `{ flows: [...], count }` | Table: Timestamp, Src/Dst IP, Ports, Protocol, Duration, Packet Rate, Prediction |
| `/api/mitigate` | POST | `{ source_ip }` | `{ success, action }` | Quick block inline button |

---

## 4. Detections & Alerts (`pages/alerts.html`)
**Controller:** `js/alerts.js`

| Backend Endpoint | Method | Params | Response Shape | Frontend Fields Used |
|------------------|--------|--------|----------------|----------------------|
| `/api/alerts` | GET | `?limit=200` | `{ alerts: [...], count }` | Alerts Table: Date, Device, Alert Type, Severity |
| `/api/detections`| GET | `?limit=200` | `{ detections: [...], count }` | Detections Table: Flow info, Prediction |
| `/api/mitigate` | POST | `{ source_ip }` | `{ success, action }` | Mitigate Source action |

---

## 5. Mitigations (`pages/mitigations.html`)
**Controller:** `js/mitigations.js`

| Backend Endpoint | Method | Params | Response Shape | Frontend Fields Used |
|------------------|--------|--------|----------------|----------------------|
| `/api/mitigations`| GET | `?limit=500` | `{ mitigations: [...], count }` | Mitigations Table: Date, Source IP, Action, Success, Simulated |
| `/api/mitigate` | POST | `{ source_ip }` | `{ success, action, simulated }` | Manual Mitigate action |

---

## 6. System Status (`pages/system.html`)
**Controller:** `js/system.js`

| Backend Endpoint | Method | Params | Response Shape | Frontend Fields Used |
|------------------|--------|--------|----------------|----------------------|
| `/api/system/status` | GET | None | `{ flask, db, ... }` | Full status grid details |
| `/api/metrics` | GET | None | `{ ml: {...}, network: {...} }` | ML Metrics (Accuracy, Precision, Recall, FPR) & Network Metrics (Throughput, Duration) |

## Data Envelopes

### Backend Standard Response
All frontend endpoints expect this wrapper structure:
```json
{
  "success": true,
  "data": { ... payload ... },
  "timestamp": "2026-10-04T10:00:00Z"
}
```

### Backend Error Response
```json
{
  "success": false,
  "error": { "code": "ERR_CODE", "message": "Error details" },
  "timestamp": "2026-10-04T10:00:00Z"
}
```

## Backend Compatibility Adjustments
1. **Traffic Prediction Mapping:** Modified `repository.py` to `LEFT JOIN predictions` on the `traffic_flows` fetch so `prediction`, `probability`, and `confidence` are returned synchronously.
2. **CORS:** The backend was already configured with `flask-cors` using `origins: "*"` out of the box in `app.py`. No changes were made here per instructions to leave functioning things alone.
3. **Number Truthiness:** The frontend was updated to securely parse SQLite's strict text/numeric representations correctly using flexible truthiness mapping for `simulated` and `success` responses.
