# 📡 Aegis Flow — MQTT Communication Protocol Specification

This document defines the MQTT messaging architecture, topic hierarchy, and payload schemas connecting the Aegis Flow backend, ESP32 IoT signal controllers, and ambulance tracking nodes.

---

## 1. Topic Hierarchy & Roles

```
aegis/
 ├── signals/
 │    └── {signal_id}/
 │         ├── command    [Server -> Controller] : Preemption commands
 │         ├── status     [Controller -> Server] : Heartbeats & phase telemetry
 │         └── override   [Server -> Controller] : Authority manual overrides
 ├── ambulances/
 │    └── {ambulance_id}/
 │         └── gps        [Vehicle -> Server]    : Real-time GPS coordinates
 └── emergency/
      └── broadcast       [Server -> All]        : City-wide priority alerts
```

---

## 2. Topic Schemas & Payloads

### 2.1 Signal Command Topic
- **Topic:** `aegis/signals/{signal_id}/command`
- **Publisher:** Aegis Flow Backend / Corridor Controller
- **Subscriber:** ESP32 Traffic Light Controller
- **QoS:** `1` (At least once) | **Retain:** `False`
- **Payload Schema (JSON):**
```json
{
  "signal_id": "signal-001",
  "state": "EMERGENCY_PRIORITY",
  "phase": "GREEN",
  "priority_lane": "NS",
  "opposing_lane": "RED",
  "duration_sec": 45,
  "timestamp": "2026-10-14T12:00:00Z"
}
```

### 2.2 Signal Status Heartbeat Topic
- **Topic:** `aegis/signals/{signal_id}/status`
- **Publisher:** ESP32 Controller (every 5 seconds)
- **Subscriber:** Aegis Flow Backend / Command Center
- **QoS:** `0` | **Retain:** `False`
- **Payload Schema (JSON):**
```json
{
  "signal_id": "sig-001",
  "status": "ONLINE",
  "state": "NORMAL",
  "uptime_sec": 452
}
```

### 2.3 Ambulance Telemetry Topic
- **Topic:** `aegis/ambulances/{ambulance_id}/gps`
- **Publisher:** Ambulance GPS Hardware Node / Simulator
- **Subscriber:** Aegis Flow Backend
- **QoS:** `0` | **Retain:** `False`
- **Payload Schema (JSON):**
```json
{
  "ambulance_id": "amb-001",
  "latitude": 18.520412,
  "longitude": 73.856721,
  "speed_kmh": 52.4,
  "heading": 42.0,
  "emergency_mode": true,
  "timestamp": "2026-10-14T12:00:02Z"
}
```

---

## 3. Communication Quality & Safety

1. **Broker Configuration:**
   - Default Broker Host: `localhost` (Port: `1883`)
   - Configurable via `MQTT_BROKER` and `MQTT_PORT` in `.env`.
2. **Keep-Alive:**
   - Keep-alive interval: `60 seconds`.
3. **Hardware Watchdog Protection:**
   - If an ESP32 receives an `EMERGENCY_PRIORITY` command and does not receive a refresh within `duration_sec`, the ESP32 automatically transitions to `CLEARANCE` (4s Yellow) then returns to `NORMAL` operation.
