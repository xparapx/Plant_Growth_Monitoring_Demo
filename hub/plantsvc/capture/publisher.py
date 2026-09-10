"""MQTT publish of one growth payload.  Never raises - the jsonl line is already written.

★ qos=1: publish.single() disconnects right after sending.  With qos=0 the
message can vanish before the broker processes it; qos=1 waits for PUBACK so
"published" means "arrived".
"""

from __future__ import annotations


def publish(payload: str, topic: str = "plant/tray/growth", host: str = "localhost",
            port: int = 1883, timeout: float = 10.0) -> tuple[bool, str]:
    try:
        import paho.mqtt.publish as mqtt
        mqtt.single(topic, payload, qos=1, hostname=host, port=port, keepalive=int(timeout))
        return True, ""
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"
