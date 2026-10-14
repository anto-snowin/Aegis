"""
Aegis Flow - MQTT Communication Service
Handles real-time publish/subscribe communication with ESP32 IoT signal controllers
and ambulance GPS hardware trackers.
"""

import json
import logging
import os
import threading
from typing import Callable, Dict, Any, Optional
from datetime import datetime, timezone

try:
    import paho.mqtt.client as mqtt
    PAHO_AVAILABLE = True
except ImportError:
    PAHO_AVAILABLE = False

logger = logging.getLogger("aegis.mqtt")


class MQTTService:
    """
    MQTT client manager with automatic reconnection, graceful fallback,
    and structured topic routing for IoT traffic hardware.
    """

    def __init__(self):
        self.broker = os.getenv("MQTT_BROKER", "localhost")
        self.port = int(os.getenv("MQTT_PORT", 1883))
        self.client_id = f"aegis-flow-backend-{os.getpid()}"
        self.client: Optional[Any] = None
        self.is_connected = False
        self.simulation_mode = False
        self.subscriptions: Dict[str, list] = {}
        self.last_messages: Dict[str, Dict[str, Any]] = {}

    def start(self):
        """Initialize and start the MQTT connection in background thread."""
        if not PAHO_AVAILABLE:
            logger.warning("[MQTT] paho-mqtt not available; operating in simulation mode")
            self.simulation_mode = True
            return

        try:
            # Use CallbackAPIVersion.VERSION2 for paho-mqtt 2.x
            try:
                self.client = mqtt.Client(
                    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                    client_id=self.client_id
                )
            except (AttributeError, TypeError):
                # Fallback for older paho-mqtt 1.x
                self.client = mqtt.Client(client_id=self.client_id)

            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message

            # Connect non-blocking with timeout
            logger.info(f"[MQTT] Connecting to broker at {self.broker}:{self.port}...")
            self.client.connect_async(self.broker, self.port, 60)
            self.client.loop_start()
        except Exception as e:
            logger.warning(f"[MQTT] Could not connect to {self.broker}:{self.port} ({e}). Running in software simulation mode.")
            self.simulation_mode = True
            self.is_connected = False

    def stop(self):
        """Disconnect and stop background loop."""
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass
            self.is_connected = False
            logger.info("[MQTT] Disconnected from broker")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback when connection established."""
        # In paho 2.x, rc is a ReasonCode object; in 1.x, it's int
        rc_val = getattr(rc, "value", rc)
        if rc_val == 0:
            self.is_connected = True
            self.simulation_mode = False
            logger.info(f"[MQTT] Connected successfully to {self.broker}:{self.port}")
            # Resubscribe to core topics
            client.subscribe("aegis/signals/+/status", qos=1)
            client.subscribe("aegis/ambulances/+/gps", qos=1)
            client.subscribe("aegis/commands/#", qos=1)
        else:
            logger.warning(f"[MQTT] Connection returned code {rc}")
            self.simulation_mode = True

    def _on_disconnect(self, client, userdata, disconnect_flags, rc=None, properties=None):
        self.is_connected = False
        logger.info("[MQTT] Disconnected from broker")

    def _on_message(self, client, userdata, message):
        """Route incoming MQTT payload to registered listeners."""
        topic = message.topic
        try:
            payload_str = message.payload.decode("utf-8")
            data = json.loads(payload_str)
        except Exception:
            data = {"raw": message.payload.decode("utf-8", errors="ignore")}

        self.last_messages[topic] = {
            "data": data,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }

        # Dispatch to topic subscribers
        for pattern, callbacks in self.subscriptions.items():
            if self._topic_matches(pattern, topic):
                for cb in callbacks:
                    try:
                        cb(topic, data)
                    except Exception as e:
                        logger.error(f"[MQTT] Error in subscriber callback: {e}")

    def _topic_matches(self, pattern: str, topic: str) -> bool:
        """Check if an MQTT wildcard pattern matches a topic."""
        if pattern == topic or pattern == "#":
            return True
        p_parts = pattern.split("/")
        t_parts = topic.split("/")
        if len(p_parts) != len(t_parts) and not pattern.endswith("/#"):
            return False
        for p, t in zip(p_parts, t_parts):
            if p == "#":
                return True
            if p != "+" and p != t:
                return False
        return len(p_parts) == len(t_parts)

    def subscribe(self, topic: str, callback: Callable[[str, Dict[str, Any]], None]):
        """Register a callback for an MQTT topic."""
        if topic not in self.subscriptions:
            self.subscriptions[topic] = []
            if self.is_connected and self.client:
                self.client.subscribe(topic, qos=1)
        self.subscriptions[topic].append(callback)

    def publish(self, topic: str, payload: Any, qos: int = 1, retain: bool = False) -> bool:
        """Publish JSON or string payload to an MQTT topic."""
        if isinstance(payload, (dict, list)):
            body = json.dumps(payload)
        else:
            body = str(payload)

        # Store in local message cache for simulation/testing
        self.last_messages[topic] = {
            "data": payload if isinstance(payload, dict) else {"raw": body},
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }

        if self.is_connected and self.client:
            try:
                self.client.publish(topic, body, qos=qos, retain=retain)
                logger.debug(f"[MQTT] Published to {topic}: {body}")
                return True
            except Exception as e:
                logger.error(f"[MQTT] Publish error on {topic}: {e}")
                return False
        else:
            # Software simulation logging
            logger.info(f"[MQTT-SIM] Virtual publish to {topic}: {body}")
            return True

    def publish_signal_command(
        self,
        signal_id: str,
        state: str,
        phase: str = "GREEN",
        priority_lane: str = "MAIN",
        duration_sec: int = 45,
    ):
        """Publish emergency corridor preemption command to ESP32."""
        topic = f"aegis/signals/{signal_id}/command"
        payload = {
            "signal_id": signal_id,
            "state": state.upper(),
            "phase": phase.upper(),
            "priority_lane": priority_lane,
            "opposing_lane": "RED",
            "duration_sec": duration_sec,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return self.publish(topic, payload)

    def publish_ambulance_gps(
        self,
        ambulance_id: str,
        lat: float,
        lon: float,
        speed_kmh: float = 0.0,
        heading: float = 0.0,
    ):
        """Publish live ambulance GPS telemetry."""
        topic = f"aegis/ambulances/{ambulance_id}/gps"
        payload = {
            "ambulance_id": ambulance_id,
            "latitude": lat,
            "longitude": lon,
            "speed_kmh": speed_kmh,
            "heading": heading,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return self.publish(topic, payload)


# Global singleton instance
mqtt_service = MQTTService()
