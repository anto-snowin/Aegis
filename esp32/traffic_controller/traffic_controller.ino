/*
 * ============================================================================
 * AEGIS FLOW — ESP32 Dynamic Traffic Signal Controller
 * ============================================================================
 * Project: Aegis Flow - AI Emergency Response & Dynamic Traffic Signal Control
 * Target Hardware: ESP32 Dev Module / NodeMCU-32S
 * Communication: WiFi + MQTT (PubSubClient)
 *
 * Description:
 * Controls a 4-way physical traffic signal model with two distinct approaches:
 * - Approach 1: North-South (NS) - Main Emergency Priority Corridor
 * - Approach 2: East-West (EW)   - Cross Street
 *
 * Features:
 * - Autonomous local cyclic timer (fail-safe when offline or normal)
 * - MQTT Remote Emergency Priority Preemption
 * - Staged Transitions: NORMAL -> PREPARE -> EMERGENCY -> CLEARANCE -> NORMAL
 * - Hardware Watchdog / Fail-Safe Timeout (auto-reverts if connection lost)
 * - Heartbeat telemetry published to Aegis Flow cloud/backend
 * ============================================================================
 */

#include <WiFi.h>
#include <PubSubClient.h>

// ═══════════════════════════════════════════════════════════════
// 1. PIN CONFIGURATION (ESP32 GPIOs)
// ═══════════════════════════════════════════════════════════════
// North-South Approach (Main Corridor)
const int PIN_NS_RED    = 23;
const int PIN_NS_YELLOW = 22;
const int PIN_NS_GREEN  = 21;

// East-West Approach (Cross Street)
const int PIN_EW_RED    = 19;
const int PIN_EW_YELLOW = 18;
const int PIN_EW_GREEN  = 5;

// Status & Emergency Indicators
const int PIN_BUZZER    = 4;   // Optional Piezo Buzzer for Emergency Siren
const int PIN_STATUS_LED= 2;   // Onboard Blue LED (WiFi/MQTT indicator)

// ═══════════════════════════════════════════════════════════════
// 2. NETWORK & MQTT CONFIGURATION
// ═══════════════════════════════════════════════════════════════
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// IP Address of laptop running Aegis Flow backend (or MQTT broker)
const char* MQTT_BROKER   = "192.168.1.100";
const int   MQTT_PORT     = 1883;
const char* SIGNAL_ID     = "sig-001"; // Must match signal ID in database

// MQTT Topics
char TOPIC_COMMAND[64];
char TOPIC_STATUS[64];

WiFiClient espClient;
PubSubClient mqttClient(espClient);

// ═══════════════════════════════════════════════════════════════
// 3. STATE DEFINITIONS
// ═══════════════════════════════════════════════════════════════
enum SignalState {
  STATE_NORMAL,
  STATE_PREPARE,
  STATE_EMERGENCY_PRIORITY,
  STATE_CLEARANCE,
  STATE_MANUAL_HOLD
};

SignalState currentState = STATE_NORMAL;
String priorityLane = "NS";

// Timing & Watchdog
unsigned long stateStartTime = 0;
unsigned long emergencyExpiryDurationMs = 45000; // 45 seconds default fail-safe
unsigned long lastHeartbeat = 0;
unsigned long normalCycleTimer = 0;
int normalCycleStep = 0;

// Autonomous Cycle Timings (milliseconds)
const unsigned long TIME_NS_GREEN  = 12000;
const unsigned long TIME_NS_YELLOW = 3000;
const unsigned long TIME_ALL_RED   = 2000;
const unsigned long TIME_EW_GREEN  = 10000;
const unsigned long TIME_EW_YELLOW = 3000;

// ═══════════════════════════════════════════════════════════════
// 4. HARDWARE OUTPUT CONTROLS
// ═══════════════════════════════════════════════════════════════
void setLights(bool nsR, bool nsY, bool nsG, bool ewR, bool ewY, bool ewG) {
  // Safety Invariant: Never allow simultaneous NS and EW Green
  if (nsG && ewG) {
    nsG = false;
    ewG = false;
    nsR = true;
    ewR = true;
  }

  digitalWrite(PIN_NS_RED,    nsR ? HIGH : LOW);
  digitalWrite(PIN_NS_YELLOW, nsY ? HIGH : LOW);
  digitalWrite(PIN_NS_GREEN,  nsG ? HIGH : LOW);

  digitalWrite(PIN_EW_RED,    ewR ? HIGH : LOW);
  digitalWrite(PIN_EW_YELLOW, ewY ? HIGH : LOW);
  digitalWrite(PIN_EW_GREEN,  ewG ? HIGH : LOW);
}

void soundAlarm(bool active) {
  if (PIN_BUZZER > 0) {
    if (active) {
      tone(PIN_BUZZER, 880); // 880 Hz audible alert
    } else {
      noTone(PIN_BUZZER);
    }
  }
}

// ═══════════════════════════════════════════════════════════════
// 5. WIFI & MQTT MANAGEMENT
// ═══════════════════════════════════════════════════════════════
void setupWiFi() {
  Serial.print("[WiFi] Connecting to: ");
  Serial.println(WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int retries = 0;
  while (WiFi.status() != WL_CONNECTED && retries < 20) {
    delay(500);
    Serial.print(".");
    digitalWrite(PIN_STATUS_LED, !digitalRead(PIN_STATUS_LED));
    retries++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WiFi] Connected! IP: " + WiFi.localIP().toString());
    digitalWrite(PIN_STATUS_LED, HIGH);
  } else {
    Serial.println("\n[WiFi] Connection timeout. Operating in offline autonomous mode.");
    digitalWrite(PIN_STATUS_LED, LOW);
  }
}

void mqttCallback(char* topic, byte* message, unsigned int length) {
  String payload = "";
  for (unsigned int i = 0; i < length; i++) {
    payload += (char)message[i];
  }

  Serial.println("[MQTT] Received on " + String(topic) + ": " + payload);

  // Parse command JSON
  // Example payload: {"state":"EMERGENCY_PRIORITY","phase":"GREEN","priority_lane":"NS","duration_sec":45}
  if (payload.indexOf("EMERGENCY_PRIORITY") >= 0) {
    currentState = STATE_EMERGENCY_PRIORITY;
    stateStartTime = millis();

    // Check duration
    int durIdx = payload.indexOf("\"duration_sec\":");
    if (durIdx > 0) {
      int durSec = payload.substring(durIdx + 15).toInt();
      if (durSec > 5 && durSec < 120) {
        emergencyExpiryDurationMs = (unsigned long)durSec * 1000;
      }
    }

    if (payload.indexOf("EW") >= 0) {
      priorityLane = "EW";
    } else {
      priorityLane = "NS";
    }

    Serial.println("🚨 [CORRIDOR ACTIVATED] Priority Green wave granted to: " + priorityLane);
  }
  else if (payload.indexOf("PREPARE") >= 0) {
    currentState = STATE_PREPARE;
    stateStartTime = millis();
    Serial.println("⚠️ [CORRIDOR PREPARE] Clearing intersection queues...");
  }
  else if (payload.indexOf("CLEARANCE") >= 0) {
    currentState = STATE_CLEARANCE;
    stateStartTime = millis();
    Serial.println("🔄 [CORRIDOR CLEARANCE] Reverting to normal cycle...");
  }
  else if (payload.indexOf("NORMAL") >= 0) {
    currentState = STATE_NORMAL;
    soundAlarm(false);
    normalCycleTimer = millis();
    normalCycleStep = 0;
    Serial.println("✅ [NORMAL] Standard cyclic scheduling resumed.");
  }
}

void reconnectMQTT() {
  if (WiFi.status() != WL_CONNECTED) return;
  if (!mqttClient.connected()) {
    Serial.print("[MQTT] Connecting to broker...");
    String clientId = "ESP32-Signal-" + String(SIGNAL_ID);
    if (mqttClient.connect(clientId.c_str())) {
      Serial.println(" Connected!");
      mqttClient.subscribe(TOPIC_COMMAND);
      publishStatus("ONLINE", "NORMAL");
    } else {
      Serial.print(" Failed (rc=");
      Serial.print(mqttClient.state());
      Serial.println("). Retrying in loop.");
    }
  }
}

void publishStatus(String connState, String sigState) {
  if (!mqttClient.connected()) return;
  String json = "{\"signal_id\":\"" + String(SIGNAL_ID) +
                "\",\"status\":\"" + connState +
                "\",\"state\":\"" + sigState +
                "\",\"uptime_sec\":" + String(millis() / 1000) + "}";
  mqttClient.publish(TOPIC_STATUS, json.c_str());
}

// ═══════════════════════════════════════════════════════════════
// 6. STATE MACHINE EXECUTION
// ═══════════════════════════════════════════════════════════════
void runStateMachine() {
  unsigned long now = millis();

  switch (currentState) {
    case STATE_NORMAL: {
      soundAlarm(false);
      unsigned long elapsed = now - normalCycleTimer;

      // Normal Cyclic Phases:
      // 0: NS Green, EW Red (12s)
      // 1: NS Yellow, EW Red (3s)
      // 2: All Red Buffer (2s)
      // 3: NS Red, EW Green (10s)
      // 4: NS Red, EW Yellow (3s)
      // 5: All Red Buffer (2s)

      if (normalCycleStep == 0) {
        setLights(false, false, true, true, false, false);
        if (elapsed >= TIME_NS_GREEN) { normalCycleStep = 1; normalCycleTimer = now; }
      }
      else if (normalCycleStep == 1) {
        setLights(false, true, false, true, false, false);
        if (elapsed >= TIME_NS_YELLOW) { normalCycleStep = 2; normalCycleTimer = now; }
      }
      else if (normalCycleStep == 2) {
        setLights(true, false, false, true, false, false);
        if (elapsed >= TIME_ALL_RED) { normalCycleStep = 3; normalCycleTimer = now; }
      }
      else if (normalCycleStep == 3) {
        setLights(true, false, false, false, false, true);
        if (elapsed >= TIME_EW_GREEN) { normalCycleStep = 4; normalCycleTimer = now; }
      }
      else if (normalCycleStep == 4) {
        setLights(true, false, false, false, true, false);
        if (elapsed >= TIME_EW_YELLOW) { normalCycleStep = 5; normalCycleTimer = now; }
      }
      else if (normalCycleStep == 5) {
        setLights(true, false, false, true, false, false);
        if (elapsed >= TIME_ALL_RED) { normalCycleStep = 0; normalCycleTimer = now; }
      }
      break;
    }

    case STATE_PREPARE: {
      // Flashing Yellow for priority approach, Solid Red for opposing approach
      bool flash = (now / 350) % 2 == 0;
      if (priorityLane == "NS") {
        setLights(false, flash, false, true, false, false);
      } else {
        setLights(true, false, false, false, flash, false);
      }

      // Auto-transition timeout: if no emergency command arrives in 25s, revert
      if (now - stateStartTime > 25000) {
        Serial.println("[WATCHDOG] Prepare state timed out without emergency. Reverting.");
        currentState = STATE_NORMAL;
        normalCycleTimer = now;
        normalCycleStep = 0;
      }
      break;
    }

    case STATE_EMERGENCY_PRIORITY: {
      // Solid GREEN on priority approach, strict RED on conflicting cross approach
      soundAlarm(true);
      if (priorityLane == "NS") {
        setLights(false, false, true, true, false, false);
      } else {
        setLights(true, false, false, false, false, true);
      }

      // FAIL-SAFE WATCHDOG: If ambulance passed or backend disconnected
      if (now - stateStartTime > emergencyExpiryDurationMs) {
        Serial.println("🚨 [WATCHDOG] Emergency priority timer expired! Entering clearance.");
        currentState = STATE_CLEARANCE;
        stateStartTime = now;
      }
      break;
    }

    case STATE_CLEARANCE: {
      soundAlarm(false);
      // Yellow clearance buffer (4 seconds) followed by All-Red (2 seconds)
      unsigned long elapsed = now - stateStartTime;
      if (elapsed < 4000) {
        if (priorityLane == "NS") {
          setLights(false, true, false, true, false, false);
        } else {
          setLights(true, false, false, false, true, false);
        }
      } else if (elapsed < 6000) {
        setLights(true, false, false, true, false, false); // All-Red
      } else {
        currentState = STATE_NORMAL;
        normalCycleTimer = now;
        normalCycleStep = 0;
        Serial.println("✅ [CYCLE RESUMED] Normal operation safe.");
      }
      break;
    }

    case STATE_MANUAL_HOLD: {
      soundAlarm(false);
      setLights(true, false, false, true, false, false); // Safe All-Red hold
      break;
    }
  }
}

// ═══════════════════════════════════════════════════════════════
// 7. SETUP & MAIN LOOP
// ═══════════════════════════════════════════════════════════════
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n==============================================");
  Serial.println("  AEGIS FLOW — ESP32 Smart Traffic Controller ");
  Serial.println("  Signal ID: " + String(SIGNAL_ID));
  Serial.println("==============================================");

  // Configure Pins
  pinMode(PIN_NS_RED, OUTPUT);
  pinMode(PIN_NS_YELLOW, OUTPUT);
  pinMode(PIN_NS_GREEN, OUTPUT);
  pinMode(PIN_EW_RED, OUTPUT);
  pinMode(PIN_EW_YELLOW, OUTPUT);
  pinMode(PIN_EW_GREEN, OUTPUT);
  pinMode(PIN_STATUS_LED, OUTPUT);
  if (PIN_BUZZER > 0) pinMode(PIN_BUZZER, OUTPUT);

  // Initialize with Safe All-Red for 1 second
  setLights(true, false, false, true, false, false);
  delay(1000);

  // Construct MQTT Topics
  snprintf(TOPIC_COMMAND, sizeof(TOPIC_COMMAND), "aegis/signals/%s/command", SIGNAL_ID);
  snprintf(TOPIC_STATUS, sizeof(TOPIC_STATUS), "aegis/signals/%s/status", SIGNAL_ID);

  setupWiFi();

  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);

  normalCycleTimer = millis();
  normalCycleStep = 0;
}

void loop() {
  // Maintain WiFi and MQTT connection
  if (WiFi.status() == WL_CONNECTED) {
    if (!mqttClient.connected()) {
      reconnectMQTT();
    }
    mqttClient.loop();

    // Publish periodic heartbeat every 5 seconds
    if (millis() - lastHeartbeat > 5000) {
      lastHeartbeat = millis();
      String stStr = "NORMAL";
      if (currentState == STATE_EMERGENCY_PRIORITY) stStr = "EMERGENCY_PRIORITY";
      else if (currentState == STATE_PREPARE) stStr = "PREPARE";
      else if (currentState == STATE_CLEARANCE) stStr = "CLEARANCE";
      publishStatus("ONLINE", stStr);
    }
  }

  // Execute signal state machine
  runStateMachine();
}
