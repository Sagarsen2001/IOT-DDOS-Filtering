"""
network/mqtt_client.py
======================
Thin MQTT client wrapper around paho-mqtt.

Responsibilities
----------------
- Connect to the Mosquitto broker.
- Publish IoT telemetry messages.
- Subscribe to topics and hand messages to a callback.
- Handle reconnection gracefully.
- Report connection status to the health API.
"""

import json
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional

import config

logger = logging.getLogger(__name__)

# Try importing paho; degrade gracefully if not installed
try:
    import paho.mqtt.client as mqtt_paho
    PAHO_AVAILABLE = True
except ImportError:
    PAHO_AVAILABLE = False
    logger.warning("paho-mqtt not installed — MQTT client will be unavailable")


class MQTTClient:
    """
    Thread-safe MQTT client.

    Parameters
    ----------
    broker_host  : Mosquitto host (default from config).
    broker_port  : Mosquitto port (default 1883).
    client_id    : MQTT client identifier.
    on_message   : Optional callback(topic: str, payload: dict) invoked on receive.
    """

    def __init__(
        self,
        broker_host: str = config.MQTT_BROKER_HOST,
        broker_port: int = config.MQTT_BROKER_PORT,
        client_id: str = config.MQTT_CLIENT_ID,
        on_message: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> None:
        self._host = broker_host
        self._port = broker_port
        self._client_id = client_id
        self._on_message_cb = on_message
        self._client = None
        self._connected = False
        self._lock = threading.Lock()

        if PAHO_AVAILABLE:
            # Use CallbackAPIVersion.VERSION1 if available (paho-mqtt >= 2.0)
            try:
                self._client = mqtt_paho.Client(
                    mqtt_paho.CallbackAPIVersion.VERSION1,
                    client_id=client_id,
                    clean_session=True,
                )
            except AttributeError:
                # paho-mqtt < 2.0 fallback
                self._client = mqtt_paho.Client(client_id=client_id, clean_session=True)
            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect
            self._client.on_message = self._on_message

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> bool:
        """
        Attempt to connect to the broker.
        Returns True if successful, False otherwise.
        Never raises.
        """
        if not PAHO_AVAILABLE:
            logger.warning("paho-mqtt not available — skipping MQTT connect")
            return False
        try:
            self._client.connect(self._host, self._port, keepalive=config.MQTT_KEEPALIVE)
            self._client.loop_start()
            # Give it a moment to establish the connection
            time.sleep(1.5)
            logger.info("MQTT connected to %s:%d", self._host, self._port)
            return True
        except Exception as exc:
            logger.error("MQTT connection failed (%s:%d): %s", self._host, self._port, exc)
            return False

    def subscribe(self, topic: str = config.MQTT_TOPIC) -> None:
        """Subscribe to a topic.  Silently skips if not connected."""
        if not self._connected:
            logger.warning("MQTT not connected — cannot subscribe to %s", topic)
            return
        self._client.subscribe(topic)
        logger.info("MQTT subscribed to topic: %s", topic)

    def publish(self, topic: str, payload: Dict[str, Any], qos: int = 0) -> bool:
        """
        Publish a JSON payload to a topic.
        Returns True if message was queued, False on error.
        """
        if not PAHO_AVAILABLE:
            logger.debug("[DEMO] MQTT publish skipped (paho not available): %s", topic)
            return False
        if not self._connected:
            logger.warning("MQTT not connected — publish dropped for topic %s", topic)
            return False
        try:
            msg = json.dumps(payload)
            self._client.publish(topic, msg, qos=qos)
            logger.debug("MQTT published to %s: %s", topic, msg[:120])
            return True
        except Exception as exc:
            logger.error("MQTT publish failed: %s", exc)
            return False

    def disconnect(self) -> None:
        """Cleanly disconnect from the broker."""
        if self._client and PAHO_AVAILABLE:
            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False
            logger.info("MQTT disconnected")

    # ------------------------------------------------------------------
    # Paho callbacks
    # ------------------------------------------------------------------

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected = True
            logger.info("MQTT broker connection established (rc=0)")
        else:
            self._connected = False
            logger.error("MQTT connection refused (rc=%d)", rc)

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        if rc != 0:
            logger.warning("MQTT unexpected disconnect (rc=%d) — will attempt reconnect", rc)

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.warning("MQTT: malformed payload on %s: %s", topic, exc)
            return
        if self._on_message_cb:
            try:
                self._on_message_cb(topic, payload)
            except Exception as exc:
                logger.error("MQTT message callback error: %s", exc)
