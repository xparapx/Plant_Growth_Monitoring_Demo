"""Everything one process needs, wired once (the API app and the CLI share this)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .analytics.roster import Roster, build_roster
from .camera.backends import make_backend
from .camera.manager import CameraManager
from .camera.setup_actions import SetupSession
from .capture.runner import CaptureRunner
from .config_store import ConfigStore
from .db import FrameCache, Frames, load_frames
from .events import EventStore
from .led import LedController
from .mqtt_bridge import MqttBridge
from .realtime import Hub
from .settings import Paths, Settings, get_settings
from .timeutil import now_utc


@dataclass
class AppContext:
    settings: Settings
    paths: Paths
    store: ConfigStore
    cache: FrameCache
    events: EventStore
    hub: Hub
    camera: CameraManager
    led: LedController
    runner: CaptureRunner
    setup: SetupSession
    bridge: MqttBridge | None = None
    started_at: datetime = field(default_factory=now_utc)

    def frames(self, dummy: str | None = None) -> Frames:
        cfg = self.store.get()
        mode = dummy or cfg.analysis.dummy_fill
        key = (mode, cfg.analysis.soil_days, cfg.analysis.pump_limit, self.store.mtime_ns)
        return self.cache.get(key, lambda: load_frames(self.paths, cfg, dummy=mode))

    def roster(self, fr: Frames) -> Roster:
        return build_roster(fr.soil, fr.grow)

    def close(self) -> None:
        for step in (lambda: self.bridge and self.bridge.stop(), self.camera.close, self.led.force_off,
                     self.events.close):
            try:
                step()
            except Exception:
                pass


def build_context(settings: Settings | None = None, *, camera_backend: Any = None,
                  led_mode: str | None = None, mqtt: bool | None = None, log=print) -> AppContext:
    settings = settings or get_settings()
    paths = settings.paths.ensure()
    store = ConfigStore(paths.config, example=paths.example_config)
    store.load()
    for w in store.warnings:
        log(f"[config] {w}")
    events = EventStore(paths.events_db)
    hub = Hub()
    cache = FrameCache()

    def rois_getter():
        return [r.model_dump() for r in store.get().rois]

    if camera_backend is not None:
        factory = camera_backend if callable(camera_backend) else (lambda: camera_backend)
    else:
        factory = lambda: make_backend(settings.camera_mode, rois_getter, log=log)  # noqa: E731
    camera = CameraManager(factory, store, lock_path=paths.camera_lock, hub=hub, events=events,
                           idle_close_s=settings.preview_idle_close_s, max_clients=settings.max_stream_clients,
                           quiet_window_s=settings.quiet_window_s, log=log)
    led = LedController(store, events, hub, mode_override=led_mode or settings.led_mode)
    runner = CaptureRunner(paths, store, camera, led, events, hub)
    setup = SetupSession(store, camera, paths, events, hub)
    bridge = None
    if (settings.mqtt if mqtt is None else mqtt):
        m = store.get().mqtt
        bridge = MqttBridge(m.host, m.port, hub, cache, events, log=log)
    store.on_change(lambda cfg: (cache.invalidate(), hub.broadcast("config.changed", {"mtime": store.mtime_ns})))
    return AppContext(settings=settings, paths=paths, store=store, cache=cache, events=events, hub=hub,
                      camera=camera, led=led, runner=runner, setup=setup, bridge=bridge)
