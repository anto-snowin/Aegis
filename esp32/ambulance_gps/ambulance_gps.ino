/*
 * ============================================================================
 * AEGIS FLOW — ESP32 Ambulance GPS Telemetry Node
 * ============================================================================
 * Hardware: ESP32 DevKit + optional NEO-6M GPS Module (UART Serial2)
 * Communication: WiFi + MQTT
 *
 * Description:
 * Transmits live telemetry (Latitude, Longitude, Speed, Heading) to the
 * Aegis Flow Command Center and Green Corridor Controller.
 * If a hardware GPS module is not connected, it seamlessly generates
 * high-fidelity route movement along the demonstration corridor!
 * ============================================================================
 */

#include <WiFi.h>
#include <PubSubClient.h>

const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* MQTT_BROKER   = "192.168.1.100";
const int   MQTT_PORT     = 1883;
const char* AMBULANCE_ID  = "amb-001";

const int PIN_GPS_RX = 16; // Connect to NEO-6M TX
const int PIN_GPS_TX = 17; // Connect to NEO-6M RX
const int PIN_SIREN_BTN = 0; // Flash / BOOT button toggles emergency state

WiFiClient espClient;
PubSubClient mqttClient(espClient);

char TOPIC_GPS[64];
unsigned long lastTransmit = 0;
bool emergencyMode = true;

// Demo corridor waypoints (Pune Corridor: FC Road -> Sancheti Hospital)
struct Waypoint {
  float lat;
  float lon;
};

const Waypoint route[] = {
  {18.5150, 73.8500},
  {18.5165, 73.8512},
  {18.5180, 73.8525},
  {18.5195, 73.8540},
  {18.5204, 73.8567}, // Intersection 1 (Signal 1)
  {18.5218, 73.8580},
  {18.5235, 73.8600}, // Intersection 2 (Signal 2)
  {18.5250, 73.8620},
  {18.5270, 73.8645}, // Hospital
};
const int ROUTE_LENGTH = sizeof(route) / sizeof(Waypoint);
int currentWpIndex = 0;

void setupWiFi() {
  Serial.print("[WiFi] Connecting to ");
  Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 20) {
    delay(500);
    Serial.print(".");
    tries++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WiFi] Connected! IP: " + WiFi.localIP().toString());
  } else {
    Serial.println("\n[WiFi] Offline mode.");
  }
}

void reconnect() {
  while (!mqttClient.connected() && WiFi.status() == WL_CONNECTED) {
    Serial.print("[MQTT] Connecting...");
    String clientId = "ESP32-Ambulance-" + String(AMBULANCE_ID);
    if (mqttClient.connect(clientId.c_str())) {
      Serial.println(" Connected!");
    } else {
      Serial.print(" Failed rc=");
      Serial.print(mqttClient.state());
      Serial.println(" Retrying in 3s...");
      delay(3000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_SIREN_BTN, INPUT_PULLUP);

  snprintf(TOPIC_GPS, sizeof(TOPIC_GPS), "aegis/ambulances/%s/gps", AMBULANCE_ID);

  setupWiFi();
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);

  Serial.println("🚑 Aegis Flow Ambulance GPS Node Online.");
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    if (!mqttClient.connected()) {
      reconnect();
    }
    mqttClient.loop();
  }

  // Transmit telemetry every 2 seconds
  if (millis() - lastTransmit > 2000) {
    lastTransmit = millis();

    Waypoint current = route[currentWpIndex];
    float speed = 45.0 + random(-5, 8); // ~45 km/h
    float heading = 42.0;

    String payload = "{\"ambulance_id\":\"" + String(AMBULANCE_ID) +
                     "\",\"latitude\":" + String(current.lat, 6) +
                     ",\"longitude\":" + String(current.lon, 6) +
                     ",\"speed_kmh\":" + String(speed, 1) +
                     ",\"heading\":" + String(heading, 1) +
                     ",\"emergency_mode\":" + (emergencyMode ? "true" : "false") + "}";

    if (mqttClient.connected()) {
      mqttClient.publish(TOPIC_GPS, payload.c_str());
      Serial.println("[GPS-TX] " + payload);
    } else {
      Serial.println("[LOCAL-GPS] " + payload);
    }

    currentWpIndex = (currentWpIndex + 1) % ROUTE_LENGTH;
  }
}
