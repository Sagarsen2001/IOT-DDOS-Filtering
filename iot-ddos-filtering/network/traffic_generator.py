"""
network/traffic_generator.py
============================
Controlled traffic generator for DEMO / lab use ONLY.

Modes
-----
  normal : Simulates legitimate IoT sensor telemetry at a low rate.
  attack : Simulates a high-rate DDoS-like burst (strictly within lab).

Safety
------
  - Target IPs are restricted to the configured lab topology.
  - No real external network traffic is generated.
  - All "packets" are JSON messages sent over MQTT or logged locally.

CLI Usage
---------
    python -m network.traffic_generator --mode normal
    python -m network.traffic_generator --mode attack --rate 500 --duration 10
"""

import argparse
import logging
import random
import time
from typing import Optional

import config
from network.mqtt_client import MQTTClient

logger = logging.getLogger(__name__)

# Allowed lab IPs — never touch external addresses
_ALLOWED_SRC_IPS = [f"10.0.0.{i}" for i in range(1, 11)]
_ALLOWED_DST_IPS = ["192.168.1.1", "192.168.1.2"]


def _make_normal_payload(device_id: str) -> dict:
    return {
        "device_id": device_id,
        "temperature": round(random.uniform(20, 30), 2),
        "humidity": round(random.uniform(40, 60), 2),
        "motion": random.choice([0, 1]),
        "timestamp": time.time(),
    }


def _make_attack_payload(device_id: str) -> dict:
    # Simulates a flood — high-frequency identical message
    return {
        "device_id": device_id,
        "payload": "X" * 64,   # Padded to mimic amplification
        "timestamp": time.time(),
    }


class TrafficGenerator:
    """
    Generates simulated MQTT traffic for IoT demo scenarios.

    Parameters
    ----------
    mode       : 'normal' or 'attack'.
    rate       : Messages per second (attack mode).
    duration   : Total run time in seconds (0 = run until stop()).
    src_ip     : Source IP to announce in payloads (must be in lab range).
    mqtt_client: Injected MQTTClient; creates one if None.
    """

    def __init__(
        self,
        mode: str = "normal",
        rate: float = 5.0,
        duration: float = 0.0,
        src_ip: Optional[str] = None,
        mqtt_client: Optional[MQTTClient] = None,
    ) -> None:
        if mode not in ("normal", "attack"):
            raise ValueError(f"Invalid mode '{mode}'. Use 'normal' or 'attack'.")

        self.mode = mode
        self.rate = max(0.1, rate)
        self.duration = duration
        self.src_ip = src_ip or random.choice(_ALLOWED_SRC_IPS)

        if self.src_ip not in _ALLOWED_SRC_IPS:
            raise ValueError(
                f"src_ip '{self.src_ip}' is not in the allowed lab range. "
                "The traffic generator is restricted to the local emulation."
            )

        self._mqtt = mqtt_client
        self._stop = False
        self._count = 0

    def start(self) -> None:
        """Run the generator (blocking).  Use a thread for background use."""
        self._stop = False
        self._count = 0
        device_id = f"device-{self.src_ip.split('.')[-1]}"
        topic = f"iot/{device_id}/telemetry"

        interval = 1.0 / self.rate
        start_ts = time.time()

        mode_label = "NORMAL" if self.mode == "normal" else "ATTACK (DDoS simulation)"
        logger.info(
            "TrafficGenerator starting — mode=%s rate=%.1f/s src=%s",
            mode_label, self.rate, self.src_ip,
        )

        while not self._stop:
            if self.duration > 0 and (time.time() - start_ts) >= self.duration:
                logger.info("TrafficGenerator: duration reached — stopping")
                break

            payload = (
                _make_normal_payload(device_id)
                if self.mode == "normal"
                else _make_attack_payload(device_id)
            )
            payload["src_ip"] = self.src_ip
            payload["mode"] = self.mode

            if self._mqtt and self._mqtt.is_connected:
                self._mqtt.publish(topic, payload)
            else:
                # Fallback: just log so the demo still "shows" activity
                logger.debug("[LOCAL] %s → %s : %s", self.src_ip, topic, payload)

            self._count += 1
            time.sleep(interval)

        logger.info(
            "TrafficGenerator stopped — %d messages sent (mode=%s)",
            self._count, self.mode,
        )

    def stop(self) -> None:
        self._stop = True

    @property
    def messages_sent(self) -> int:
        return self._count


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    config.configure_logging()
    parser = argparse.ArgumentParser(description="IoT Lab Traffic Generator")
    parser.add_argument("--mode", choices=["normal", "attack"], default="normal")
    parser.add_argument("--rate", type=float, default=5.0, help="Messages per second")
    parser.add_argument("--duration", type=float, default=30.0, help="Seconds to run (0=forever)")
    parser.add_argument("--src-ip", default=None, help="Source IP (must be lab IP)")
    parser.add_argument("--no-mqtt", action="store_true", help="Disable MQTT publishing")
    args = parser.parse_args()

    mqtt_client = None
    if not args.no_mqtt:
        mqtt_client = MQTTClient()
        connected = mqtt_client.connect()
        if not connected:
            logger.warning("MQTT not available — generating traffic locally only")

    gen = TrafficGenerator(
        mode=args.mode,
        rate=args.rate,
        duration=args.duration,
        src_ip=args.src_ip,
        mqtt_client=mqtt_client,
    )
    try:
        gen.start()
    except KeyboardInterrupt:
        gen.stop()
    finally:
        if mqtt_client:
            mqtt_client.disconnect()
