"""Subscribe to the same four topics as the collector and push them to browsers.

The bridge never writes plant.db.  A retained `pump` message is re-delivered
on every (re)connect - it is flagged so the UI does not toast it as new.
"""

from __future__ import annotations

import json
import threading
from typing import Any

from .timeutil import iso_utc, now_utc

TOPICS = ("plant/+/env", "plant/+/soil", "plant/+/pump", "plant/+/growth")


class MqttBridge:
    def __init__(self, host: str, port: int, hub, cache=None, events=None, log=print):
        self.host, self.port = host, port
        self.hub, self.cache, self.events, self.log = hub, cache, events, log
        self.connected = False
        self.last_msg: str | None = None
        self.last_error: str | None = None
        self.count = 0
        self._client = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def status(self) -> dict[str, Any]:
        return {"connected": self.connected, "broker": f"{self.host}:{self.port}", "last_msg": self.last_msg,
                "messages": self.count, "error": self.last_error}

    def start(self) -> None:
        try:
            import paho.mqtt.client as mqtt
        except Exception as e:  # noqa: BLE001
            self.last_error = f"paho unavailable: {e}"
            return
        c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        c.on_connect = self._on_connect
        c.on_disconnect = self._on_disconnect
        c.on_message = self._on_message
        c.reconnect_delay_set(min_delay=2, max_delay=30)
        self._client = c

        def _run():
            try:
                c.connect(self.host, self.port, keepalive=60)
            except Exception as e:  # noqa: BLE001
                self.last_error = f"{type(e).__name__}: {e}"
                self.log(f"[mqtt] connect failed: {self.last_error} — retrying in background")
                while not self._stop.is_set():
                    if self._stop.wait(10):
                        return
                    try:
                        c.connect(self.host, self.port, keepalive=60)
                        break
                    except Exception as e2:  # noqa: BLE001
                        self.last_error = f"{type(e2).__name__}: {e2}"
            c.loop_forever(retry_first_connection=True)

        self._thread = threading.Thread(target=_run, name="mqtt-bridge", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._client is not None:
            try:
                self._client.disconnect()
            except Exception:
                pass

    # ---- callbacks -------------------------------------------------------------
    def _on_connect(self, c, u, f, rc, props=None):
        self.connected = True
        self.last_error = None
        for t in TOPICS:
            c.subscribe(t)
        self.hub.broadcast("mqtt.state", self.status())
        if self.events is not None:
            self.events.add("mqtt.connect", {"rc": str(rc)})

    def _on_disconnect(self, c, u, flags=None, rc=None, props=None):
        self.connected = False
        self.hub.broadcast("mqtt.state", self.status())

    def _on_message(self, c, u, msg):
        try:
            d = json.loads(msg.payload.decode())
        except Exception:
            return
        self.count += 1
        self.last_msg = iso_utc(now_utc())
        kind = msg.topic.rsplit("/", 1)[-1]
        if kind not in ("env", "soil", "pump", "growth"):
            return
        if self.cache is not None:
            self.cache.invalidate()
        data: dict[str, Any] = {"topic": msg.topic, "retained": bool(getattr(msg, "retain", False)), "row": d}
        if kind == "growth":
            data["row"] = {**d, "plants": [{k: v for k, v in p.items() if k != "contour"} for p in d.get("plants", [])]}
        self.hub.broadcast(kind, data)
