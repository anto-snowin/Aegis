# 🚑 Aegis Flow — AI-Powered Emergency Response & Dynamic Traffic Signal Control System

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![MQTT](https://img.shields.io/badge/MQTT-paho--mqtt-660066.svg?logo=eclipsemosquitto&logoColor=white)](https://mqtt.org)
[![ESP32](https://img.shields.io/badge/Hardware-ESP32-E7352C.svg?logo=espressif&logoColor=white)](https://espressif.com)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> **⚠️ Academic Innovation Prototype:** Aegis Flow is a functional software-first emergency coordination prototype built for college innovation competitions and hackathons. It is not connected to real emergency or municipal infrastructure.

---

## 🌟 Executive Summary

In acute medical emergencies like cardiac arrests and severe trauma, patient survival depends directly on the **"Golden Hour"**. In congested urban centers, ambulances spend up to 45% of their transit time halted at red traffic signals, trapped in long vehicle queues.

**Aegis Flow** eliminates intersection delays through an intelligent, AI-governed **Dynamic Green Wave**:
- Coordinates emergency requests, intelligent dispatch, and real-time hospital bed readiness.
- Tracks ambulance GPS telemetry and predicts approach timings.
- Automatically clears intersection queues in advance (**PREPARE** state).
- Switches traffic lights along the ambulance trajectory to solid **GREEN**, while safely holding cross-traffic **RED**.
- Interfaces seamlessly with physical **ESP32 dual-approach traffic signal hardware** over MQTT.
- Enforces strict safety guarantees: green conflict locks, yellow clearance intervals, and a hardware watchdog fail-safe.

---

## 🏛️ System Architecture

```
                      ┌─────────────────────────────────────────┐
                      │        Aegis Flow Web Interface         │
                      │  (Emergency SOS / Driver / Command Ctr)  │
                      └────────────────────┬────────────────────┘
                                           │ HTTP / WebSocket (Port 8000)
                                           ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                           FastAPI Backend Server                              │
│                                                                               │
│   ┌─────────────────────┐   ┌────────────────────────┐   ┌────────────────┐   │
│   │   REST API Layer    │   │  WebSocket Broadcast   │   │ SQLite / Auth  │   │
│   └──────────┬──────────┘   └───────────┬────────────┘   └───────┬────────┘   │
│              │                          │                        │            │
│              ▼                          ▼                        ▼            │
│   ┌───────────────────────────────────────────────────────────────────────┐   │
│   │                           AI Decision Core                            │   │
│   │  • Priority Engine (0-100)       • Dynamic ETA & Green Wave Savings   │   │
│   │  • Traffic Queue Density         • Corridor Preemption Controller     │   │
│   └─────────────────────────────────────┬─────────────────────────────────┘   │
│                                         │                                     │
│                                         ▼                                     │
│   ┌───────────────────────────────────────────────────────────────────────┐   │
│   │                        MQTT Communication Layer                       │   │
│   │           Topics: aegis/signals/{id}/command, /status, /gps           │   │
│   └─────────────────────────────────────┬─────────────────────────────────┘   │
└─────────────────────────────────────────┼─────────────────────────────────────┘
                                          │ MQTT (Port 1883)
                                          ▼
                      ┌─────────────────────────────────────────┐
                      │    ESP32 Physical Traffic Controller    │
                      │  • NS Approach LEDs (Red, Yellow, Green)│
                      │  • EW Approach LEDs (Red, Yellow, Green)│
                      │  • Hardware Watchdog & Fail-Safe Timer  │
                      └─────────────────────────────────────────┘
```

---

## ✨ Key Features & Capabilities

| Module | Features |
| :--- | :--- |
| **🚨 Citizen Emergency SOS** | One-tap emergency dispatch with geolocation, medical classification, and live tracking token. |
| **🚑 Driver Navigation Dashboard** | Turn-by-turn tracking, speed monitor, assignment accept/reject, and automated simulated GPS streaming. |
| **🏥 Hospital Command Center** | Real-time map displaying all active ambulances, signals, hospital bed availability, and live incident audit logs. |
| **🧠 Explainable AI Engine** | Transparent multi-factor scoring (severity, medical urgency, congestion index, response delay) with estimated minutes saved. |
| **🚦 Dynamic Traffic Signal Control** | Staged sequence (`NORMAL` ➔ `PREPARE` ➔ `EMERGENCY_PRIORITY` ➔ `CLEARANCE` ➔ `NORMAL`). |
| **⚡ ESP32 IoT Integration** | Production-ready Arduino C++ firmware with dual-approach LED drivers, hardware watchdog, and MQTT telemetry. |
| **🛡️ Authority Manual Override** | Traffic police/operators can instantly force red or seize manual control at any intersection. |

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- **Python 3.10+** (Tested on Python 3.12)
- **Node.js** (Optional, frontend runs natively via FastAPI static mounts)
- **Arduino IDE 2.x** (If running physical ESP32 hardware)

### 2. Installation
Clone the repository and install the backend requirements:
```bash
git clone https://github.com/your-org/aegis-flow.git
cd aegis-flow

# Install Python dependencies
pip install -r backend/requirements.txt
```

### 3. Start the Server
Launch the unified FastAPI server (serves both API and Web UI):
```bash
uvicorn backend.app.main:app --reload --port 8000
```
- **Web Application:** [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternative Redoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

### 4. Default Demo Accounts
Pre-seeded demo credentials (all accounts use password `demo1234`):
- **Citizen / Patient:** `patient1`
- **Ambulance Driver:** `driver1` or `driver2`
- **Hospital Operator:** `hospital1`
- **Traffic Authority:** `traffic1`
- **Administrator:** `admin` (password: `admin1234`)

---

## 🎮 Running the Live Demonstration

### Option A: Complete In-Browser Demo
1. Open [http://localhost:8000](http://localhost:8000).
2. Click **"Request Emergency"** and submit a **Cardiac (Critical)** incident.
3. Switch to **Driver Dashboard** (`#/driver`), select Ambulance **`MH-12-AE-1001`**, and click **"Accept Emergency"**.
4. Click **"▶ Start Simulation"** to stream GPS telemetry along the Pune corridor.
5. Navigate to **Traffic Signals** (`#/traffic/signals`) to watch Junction 1 and Junction 2 automatically transition from `NORMAL` ➔ `PREPARE` ➔ `EMERGENCY_PRIORITY` as the vehicle approaches!

### Option B: Automated Multi-Agent Simulator
Run the Python simulation script in a separate terminal:
```bash
python simulation/traffic_sim.py
```
This triggers an emergency, dispatches an ambulance, streams live GPS waypoints, activates the green corridor, and restores normal signal cycles upon hospital arrival.

### Option C: Computer Vision Camera Detector
Simulate vehicle counting and intersection congestion estimation:
```bash
python simulation/camera_detector_sim.py
```

---

## 🔌 ESP32 Hardware Setup

For physical demonstration using breadboard and LEDs:
1. Open `esp32/traffic_controller/traffic_controller.ino` in Arduino IDE.
2. Install `PubSubClient` via Library Manager.
3. Connect 6 LEDs (2 Red, 2 Yellow, 2 Green) to the ESP32 GPIOs:
   - **North-South (Corridor):** Red (`GPIO 23`), Yellow (`GPIO 22`), Green (`GPIO 21`)
   - **East-West (Cross Street):** Red (`GPIO 19`), Yellow (`GPIO 18`), Green (`GPIO 5`)
4. Flash the ESP32. Detailed schematics and wiring diagrams are in [docs/esp32_guide.md](esp32/WIRING_AND_SETUP.md).

---

## 🧪 Automated Test Suite

Aegis Flow includes comprehensive unit and integration tests covering the AI decision engines, signal state machine, and REST endpoints:
```bash
python -m pytest tests/ -v
```
**Test Results:**
```
tests/test_ai.py::test_priority_engine_critical_cardiac PASSED
tests/test_ai.py::test_priority_engine_low_severity PASSED
tests/test_ai.py::test_conflict_resolution PASSED
tests/test_ai.py::test_eta_engine_green_corridor_savings PASSED
tests/test_ai.py::test_traffic_analyzer PASSED
tests/test_ai.py::test_approach_timings PASSED
tests/test_api.py::test_system_health PASSED
tests/test_api.py::test_auth_and_login PASSED
tests/test_api.py::test_emergency_lifecycle PASSED
tests/test_api.py::test_traffic_signals_and_override PASSED
tests/test_ai.py::test_ai_analysis_endpoint PASSED
tests/test_signals.py::test_valid_transitions PASSED
tests/test_signals.py::test_invalid_safety_transitions PASSED
tests/test_signals.py::test_dual_approach_conflict_safety PASSED
tests/test_signals.py::test_command_watchdog_expiry PASSED

======================= 15 passed in 5.81s ========================
```

---

## 📂 Repository Layout

```
Aegis 26/
├── backend/
│   ├── app/
│   │   ├── ai/              # AI decision engines (Priority, ETA, Corridor, Traffic)
│   │   ├── api/             # FastAPI REST endpoints (Emergencies, Signals, etc.)
│   │   ├── database/        # SQLite connection, schema initialization, and demo seeds
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── schemas/         # Pydantic validation schemas
│   │   ├── services/        # MQTT service, signal state machine, JWT auth
│   │   └── main.py          # FastAPI application & WebSocket channels
│   └── requirements.txt     # Python backend dependencies
├── frontend/
│   ├── css/main.css         # Glassmorphism dark-mode responsive design system
│   ├── js/api.js            # REST API client & auto-reconnecting WebSocket
│   ├── js/app.js            # SPA router, Leaflet maps, and dashboard state
│   └── index.html           # Single-Page Application interface
├── esp32/
│   ├── traffic_controller/  # Dual-approach ESP32 C++ firmware with fail-safe timer
│   ├── ambulance_gps/       # ESP32 GPS tracking node firmware
│   └── WIRING_AND_SETUP.md  # Schematics, pin tables, and flashing guide
├── simulation/
│   ├── traffic_sim.py       # Multi-agent vehicle and corridor simulator
│   └── camera_detector_sim.py # Computer vision vehicle counter simulator
├── tests/
│   ├── test_ai.py           # Unit tests for AI modules
│   ├── test_api.py          # API integration tests
│   └── test_signals.py      # State machine and safety conflict tests
├── docs/
│   ├── architecture.md      # Detailed system architecture and sequence diagrams
│   ├── demo_script.md       # Hackathon live presentation script and judge Q&A
│   └── mqtt_spec.md         # MQTT protocol and topic schemas
└── README.md                # Project documentation
```

---

## 📜 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
