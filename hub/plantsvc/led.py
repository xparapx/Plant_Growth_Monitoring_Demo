"""Capture LED - the hook is final, the hardware is not installed yet.

The routine always walks led_on -> warm-up -> shoot -> led_off through this
interface.  With the default config (led.enabled=false, driver=noop) the
NoopDriver records "not installed" and the warm-up collapses to 0 s, so the
job/UI shapes are identical before and after the lamp arrives.

When installed: gpiozero.OutputDevice(pin, active_high, initial_value=False),
claimed ONLY while the lamp is on (lgpio line claims are exclusive per
process; a long-lived claim in the service would block the CLI capture).
A watchdog turns the lamp off after led.max_on_s no matter what.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any, Protocol

from .config_model import Led
from .timeutil import iso_utc, now_utc


class LedNotInstalled(RuntimeError):
    pass


class LedDriver(Protocol):
    kind: str
    reason: str

    def on(self) -> None: ...
    def off(self) -> None: ...
    def close(self) -> None: ...


class NoopDriver:
    kind = "noop"

    def __init__(self, reason: str = "LED not installed (led.enabled=false)"):
        self.reason = reason
        self.is_on = False

    def on(self) -> None:
        self.is_on = True

    def off(self) -> None:
        self.is_on = False

    def close(self) -> None:
        self.is_on = False


class GpiozeroDriver:
    """Thin gpiozero wrapper.  Written against gpiozero 2.x (lgpio on Pi 5);
    hardware verification is deferred until the lamp is wired."""
    kind = "gpiozero"

    def __init__(self, pin: int, active_high: bool = True):
        self.pin, self.active_high = pin, active_high
        self.reason = ""
        self._dev = None
        self.is_on = False

    def _device(self):
        if self._dev is None:
            from gpiozero import OutputDevice  # apt python3-gpiozero (+ python3-lgpio)
            self._dev = OutputDevice(self.pin, active_high=self.active_high, initial_value=False)
        return self._dev

    def on(self) -> None:
        self._device().on()
        self.is_on = True

    def off(self) -> None:
        try:
            if self._dev is not None:
                self._dev.off()
        finally:
            self.is_on = False
            self.close()

    def close(self) -> None:
        if self._dev is not None:
            try:
                self._dev.close()
            except Exception:
                pass
            self._dev = None


def gpio_available() -> tuple[bool, str]:
    try:
        import gpiozero  # noqa: F401
    except Exception as e:  # noqa: BLE001
        return False, f"gpiozero not importable ({type(e).__name__})"
    import glob
    if not glob.glob("/dev/gpiochip*"):
        return False, "no /dev/gpiochip* on this host"
    return True, ""


def make_driver(led: Led, mode_override: str | None = None) -> LedDriver:
    if not led.enabled:
        return NoopDriver("LED not installed (led.enabled=false)")
    mode = mode_override or led.driver
    if mode == "noop":
        return NoopDriver("driver=noop")
    if mode in ("auto", "gpiozero"):
        ok, why = gpio_available()
        if ok:
            return GpiozeroDriver(led.pin, led.active_high)
        if mode == "gpiozero":
            return NoopDriver(f"gpiozero requested but unavailable: {why}")
        return NoopDriver(f"auto: {why}")
    return NoopDriver(f"unknown driver {mode!r}")


class LedController:
    def __init__(self, store, events=None, hub=None, *, mode_override: str | None = None):
        self.store = store
        self.events = events
        self.hub = hub
        self.mode_override = mode_override
        self._lock = threading.RLock()
        self._driver: LedDriver | None = None
        self._since = None
        self._auto_off_at = None
        self._watchdog: threading.Timer | None = None
        self._reason = ""

    # ---- info ---------------------------------------------------------------
    @property
    def cfg(self) -> Led:
        return self.store.get().led

    def _probe(self) -> LedDriver:
        return make_driver(self.cfg, self.mode_override)

    @property
    def installed(self) -> bool:
        d = self._driver or self._probe()
        return self.cfg.enabled and d.kind != "noop"

    @property
    def is_on(self) -> bool:
        return bool(self._driver and getattr(self._driver, "is_on", False))

    def status(self) -> dict[str, Any]:
        led = self.cfg
        d = self._driver or self._probe()
        return {"installed": self.installed, "enabled": led.enabled, "driver": d.kind,
                "reason": getattr(d, "reason", "") or None, "state": "on" if self.is_on else "off",
                "pin": led.pin, "active_high": led.active_high, "warmup_s": led.warmup_s,
                "max_on_s": led.max_on_s, "since": iso_utc(self._since) if self._since else None,
                "auto_off_at": iso_utc(self._auto_off_at) if self._auto_off_at else None,
                "last_reason": self._reason or None}

    def _emit(self, kind: str, **data: Any) -> None:
        payload = {**self.status(), **data}
        if self.events is not None:
            self.events.add(f"led.{kind}", payload)
        if self.hub is not None:
            self.hub.broadcast("led", payload)

    # ---- control ------------------------------------------------------------
    def on(self, *, reason: str = "manual", max_on_s: int | None = None, strict: bool = True) -> dict[str, Any]:
        with self._lock:
            if not self.installed:
                if strict:
                    raise LedNotInstalled(self.status()["reason"] or "LED not installed")
                self._reason = reason
                self._emit("skipped", reason=reason)
                return self.status()
            if self._driver is None:
                self._driver = self._probe()
            self._driver.on()
            self._since = now_utc()
            self._reason = reason
            limit = max_on_s or self.cfg.max_on_s
            self._arm_watchdog(limit)
            self._emit("on", reason=reason)
            return self.status()

    def off(self, *, reason: str = "manual") -> dict[str, Any]:
        with self._lock:
            self._disarm_watchdog()
            was_on = self.is_on
            if self._driver is not None:
                try:
                    self._driver.off()
                finally:
                    try:
                        self._driver.close()
                    except Exception:
                        pass
                    self._driver = None
            self._since = None
            self._auto_off_at = None
            self._reason = reason
            if was_on:
                self._emit("off", reason=reason)
            return self.status()

    def force_off(self) -> None:
        """Startup/shutdown/ExecStopPost path: never raises."""
        try:
            self.off(reason="force_off")
        except Exception:
            pass

    def test(self, seconds: float = 2.0) -> dict[str, Any]:
        import time
        self.on(reason="test", max_on_s=int(seconds) + 5)
        try:
            time.sleep(seconds)
        finally:
            self.off(reason="test_done")
        return self.status()

    @contextmanager
    def lit(self, reason: str = "capture", *, use_led: bool = True):
        """on -> yield status -> off in finally.  Not installed => yields a 'skipped' status."""
        st = self.on(reason=reason, strict=False) if use_led else self.status()
        try:
            yield st
        finally:
            self.off(reason=f"{reason}_done")

    # ---- watchdog -----------------------------------------------------------
    def _arm_watchdog(self, seconds: int) -> None:
        self._disarm_watchdog()
        from datetime import timedelta
        self._auto_off_at = now_utc() + timedelta(seconds=seconds)
        t = threading.Timer(seconds, self._watchdog_fire)
        t.daemon = True
        t.start()
        self._watchdog = t

    def _disarm_watchdog(self) -> None:
        if self._watchdog is not None:
            self._watchdog.cancel()
            self._watchdog = None

    def _watchdog_fire(self) -> None:
        try:
            self.off(reason="watchdog")
        except Exception:
            pass
