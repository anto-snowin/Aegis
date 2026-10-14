# 🚦 Aegis Flow — ESP32 Hardware Wiring & Setup Guide

This guide walks you through building and flashing the physical **ESP32 Dynamic Traffic Signal Controller** for the Aegis Flow hackathon demonstration.

---

## 1. Hardware Bill of Materials (BOM)

| Component | Quantity | Purpose | Approximate Cost |
| :--- | :--- | :--- | :--- |
| **ESP32 DevKit V1** (30 or 38 pin) | 1 | Microcontroller with WiFi & Dual-Core processing | ~$4 - $6 |
| **5mm LEDs (Red)** | 2 | Red lights (North-South & East-West) | ~$0.20 |
| **5mm LEDs (Yellow/Amber)** | 2 | Yellow caution lights | ~$0.20 |
| **5mm LEDs (Green)** | 2 | Green priority lights | ~$0.20 |
| **220Ω or 330Ω Resistors** | 6 | Current-limiting resistors for LEDs | ~$0.30 |
| **Piezo Buzzer (5V Active)** | 1 | Optional audio siren during emergency priority | ~$0.50 |
| **Breadboard (Half/Full size)** | 1 | Prototyping circuit board | ~$1.50 |
| **Male-to-Male Jumper Wires** | 12-15 | Connections | ~$1.00 |
| **Micro-USB Cable** | 1 | Programming and 5V power from laptop | Existing |

---

## 2. GPIO Pinout Table

### Approach 1: North-South (NS) — Main Emergency Priority Corridor
| LED Color | ESP32 GPIO | Resistor | Breadboard Wire Color |
| :--- | :--- | :--- | :--- |
| **Red (NS)** | `GPIO 23` | 220Ω to GND | Red |
| **Yellow (NS)** | `GPIO 22` | 220Ω to GND | Yellow / Orange |
| **Green (NS)** | `GPIO 21` | 220Ω to GND | Green |

### Approach 2: East-West (EW) — Conflicting Cross Street
| LED Color | ESP32 GPIO | Resistor | Breadboard Wire Color |
| :--- | :--- | :--- | :--- |
| **Red (EW)** | `GPIO 19` | 220Ω to GND | Brown / Dark Red |
| **Yellow (EW)** | `GPIO 18` | 220Ω to GND | White / Orange |
| **Green (EW)** | `GPIO 5` | 220Ω to GND | Blue / Green |

### Peripheral Indicators
| Device | ESP32 GPIO | Description |
| :--- | :--- | :--- |
| **Piezo Buzzer (+)** | `GPIO 4` | Audio warning during green wave |
| **Status LED** | `GPIO 2` | Onboard blue LED (blinks when connecting, solid when online) |
| **Common Ground** | `GND` | Connected to negative power rail of breadboard |

---

## 3. Circuit Schematic Diagram

```
         ESP32 DevKit
       ┌──────────────┐
       │              │
       │      GPIO 23 ├────[ 220Ω ]───(>|)───┐  [NS RED LED]
       │      GPIO 22 ├────[ 220Ω ]───(>|)───┤  [NS YELLOW LED]
       │      GPIO 21 ├────[ 220Ω ]───(>|)───┤  [NS GREEN LED]
       │              │                      │
       │      GPIO 19 ├────[ 220Ω ]───(>|)───┤  [EW RED LED]
       │      GPIO 18 ├────[ 220Ω ]───(>|)───┤  [EW YELLOW LED]
       │      GPIO  5 ├────[ 220Ω ]───(>|)───┤  [EW GREEN LED]
       │              │                      │
       │      GPIO  4 ├──────(+) [BUZZER] (─)┤  [PIEZO SIREN]
       │              │                      │
       │          GND ├──────────────────────┴── [COMMON GROUND RAIL]
       └──────────────┘
```

> **Note on LED Orientation:**
> - The **Longer Leg (Anode, +)** connects to the GPIO through the 220Ω resistor.
> - The **Shorter Leg (Cathode, -)** connects to the Common GND rail.

---

## 4. Software Setup & Flashing Instructions

### Option A: Using Arduino IDE

1. **Install Arduino IDE** (version 2.x recommended).
2. **Add ESP32 Board URL** in `Preferences -> Additional Board Manager URLs`:
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
3. Open `Tools -> Board -> Boards Manager`, search for **`esp32`** by Espressif Systems and click **Install**.
4. Open `Tools -> Manage Libraries...`, search and install:
   - **`PubSubClient`** by Nick O'Leary (for MQTT)
5. Open the firmware file:
   `d:\Aegis 26\esp32\traffic_controller\traffic_controller.ino`
6. Configure your WiFi credentials and your computer's IP address:
   ```cpp
   const char* WIFI_SSID     = "YOUR_MOBILE_HOTSPOT_OR_WIFI";
   const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
   const char* MQTT_BROKER   = "192.168.1.50"; // IP of your laptop running Aegis Flow
   ```
7. Connect your ESP32 to your PC via USB cable.
8. Select `Tools -> Board -> ESP32 Dev Module` and the appropriate COM Port (`COM3`, `COM4`, etc.).
9. Click **Upload** (Arrow button). If the console says *Connecting......*, hold down the **BOOT** button on the ESP32 for 2 seconds.

---

## 5. MQTT Topics Reference

| Topic | Publisher | Subscriber | Payload Schema | Description |
| :--- | :--- | :--- | :--- | :--- |
| `aegis/signals/sig-001/command` | Backend / AI | ESP32 | `{"state":"EMERGENCY_PRIORITY","phase":"GREEN","priority_lane":"NS","duration_sec":45}` | Commands priority green corridor |
| `aegis/signals/sig-001/status` | ESP32 | Backend | `{"signal_id":"sig-001","status":"ONLINE","state":"NORMAL","uptime_sec":120}` | Periodic heartbeat from hardware |
| `aegis/ambulances/amb-001/gps` | GPS Node / Sim | Backend | `{"ambulance_id":"amb-001","latitude":18.5204,"longitude":73.8567,"speed_kmh":52.0}` | Real-time vehicle telemetry |

---

## 6. Failsafe Safety Features

The firmware contains autonomous embedded safety logic:
1. **Never Conflicting Green:** If software ever commands both NS and EW green, the hardware controller overrides both to RED.
2. **Hardware Watchdog:** If an emergency command arrives, an autonomous `millis()` timer starts. If the WiFi disconnects or the backend loses connection, the ESP32 automatically triggers a 4-second YELLOW clearance, then reverts to normal cyclic operation.
3. **Yellow Clearance Buffer:** Transitions never jump abruptly from Green to Red; an enforced 3-4s Yellow clearance always runs.
