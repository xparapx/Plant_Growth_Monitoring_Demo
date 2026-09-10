"""WebSocket fan-out.  Producers (MQTT bridge, capture runner, LED, camera) run in
threads; `broadcast` is thread-safe and never blocks them.  Slow clients get a
bounded queue - drop-oldest - so one stalled phone cannot back up the hub."""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any

from .timeutil import iso_utc, now_utc


class Hub:
    def __init__(self, queue_size: int = 64):
        self._loop: asyncio.AbstractEventLoop | None = None
        self._clients: set[asyncio.Queue] = set()
        self._lock = threading.Lock()
        self.queue_size = queue_size
        self.sent = 0

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=self.queue_size)
        with self._lock:
            self._clients.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self._lock:
            self._clients.discard(q)

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def envelope(self, type_: str, data: Any) -> str:
        return json.dumps({"type": type_, "ts": iso_utc(now_utc()), "data": data}, ensure_ascii=False, default=str)

    def broadcast(self, type_: str, data: Any) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        msg = self.envelope(type_, data)
        with self._lock:
            clients = list(self._clients)
        if not clients:
            return

        def _deliver():
            for q in clients:
                if q.full():
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                try:
                    q.put_nowait(msg)
                except asyncio.QueueFull:
                    pass
            self.sent += 1
        try:
            loop.call_soon_threadsafe(_deliver)
        except RuntimeError:
            pass
