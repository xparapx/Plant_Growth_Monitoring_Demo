"""CameraManager - the one owner of the camera inside a process.

  * ops_lock  (RLock) : long operations - auto-exposure cycle, findleaf, the capture job
  * dev_lock  (Lock)  : every single device call; the grab thread takes only this one
  * file lock         : cross-process arbitration (data/camera.lock) so a CLI capture
                        and the service never fight for /dev/media0

Preview opens on demand and closes `idle_close_s` after the last viewer leaves.
`release_for_capture()` closes the device for an external job and reopens it
for waiting viewers once the file lock is free again.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from ..timeutil import iso_utc, next_occurrence, now_utc, parse_hhmm
from .backends import CameraBackend, CameraUnavailable


class CameraBusy(RuntimeError):
    pass


class FileLock:
    """Advisory cross-process lock on a file (flock on POSIX, msvcrt on Windows)."""

    def __init__(self, path: str | os.PathLike):
        self.path = Path(path)
        self._fh = None

    def _try(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self.path, "a+", encoding="utf-8")
        try:
            if os.name == "nt":
                import msvcrt
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            raise
        try:
            fh.seek(0)
            fh.truncate()
            fh.write(str(os.getpid()))
            fh.flush()
        except OSError:
            pass
        self._fh = fh

    def acquire(self, timeout: float = 0.0) -> bool:
        deadline = time.monotonic() + timeout
        while True:
            try:
                self._try()
                return True
            except OSError:
                if time.monotonic() >= deadline:
                    return False
                time.sleep(0.5)

    def release(self) -> None:
        fh, self._fh = self._fh, None
        if fh is None:
            return
        try:
            if os.name == "nt":
                import msvcrt
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        fh.close()

    @property
    def held(self) -> bool:
        return self._fh is not None

    def holder_pid(self) -> int | None:
        """PID written by whoever holds the lock, if it is currently locked by someone else."""
        if self.held:
            return os.getpid()
        try:
            self._try()
        except OSError:
            try:
                return int(self.path.read_text(encoding="utf-8").strip() or 0) or None
            except (OSError, ValueError):
                return -1
        self.release()
        return None


class CameraManager:
    def __init__(self, backend_factory: Callable[[], CameraBackend], store, *, lock_path: str | os.PathLike | None,
                 hub=None, events=None, idle_close_s: int = 30, max_clients: int = 3,
                 quiet_window_s: int = 60, log=print):
        self.backend_factory = backend_factory
        self.store = store
        self.hub = hub
        self.events = events
        self.idle_close_s = idle_close_s
        self.max_clients = max_clients
        self.quiet_window_s = quiet_window_s
        self.log = log
        self.flock = FileLock(lock_path) if lock_path else None

        self.ops_lock = threading.RLock()
        self.dev_lock = threading.Lock()
        self._backend: CameraBackend | None = None
        self.state = "closed"          # closed | opening | open | error
        self.driver = ""
        self.error: str | None = None
        self.prev_stream = "lores"
        self.clients = 0
        self.paused_for: str | None = None
        self._latest: np.ndarray | None = None
        self._latest_at = 0.0
        self._grab: threading.Thread | None = None
        self._grab_stop = threading.Event()
        self._idle_timer: threading.Timer | None = None
        self._watch: threading.Thread | None = None
        self.opened_at: datetime | None = None
        self.ops_busy: str | None = None

    # ---- info ---------------------------------------------------------------------
    def probe_driver(self) -> str:
        try:
            return self.backend_factory().kind
        except Exception:
            return "unavailable"

    def status(self) -> dict[str, Any]:
        cfg = self.store.get()
        holder = self.flock.holder_pid() if self.flock and not self.flock.held else None
        preview = "unavailable" if self.state == "error" else ("paused_capture" if self.paused_for else "live")
        return {"state": self.state, "driver": self.driver or self.probe_driver(), "clients": self.clients,
                "preview": preview, "paused_for": self.paused_for, "error": self.error,
                "preview_size": list(cfg.preview.size), "capture_size": list(cfg.capture.size),
                "scale": round(cfg.scale, 6), "opened_at": iso_utc(self.opened_at) if self.opened_at else None,
                "lock_holder_pid": holder, "ops_busy": self.ops_busy,
                "quiet_window": self._quiet_window_info(cfg)}

    def _quiet_windows(self, cfg) -> list[tuple[datetime, datetime]]:
        out = []
        warm = cfg.led.warmup_s if cfg.led.enabled else 0
        for hhmm in (cfg.schedule.dawn, cfg.schedule.pm):
            try:
                parse_hhmm(hhmm)
            except ValueError:
                continue
            nxt = next_occurrence(hhmm, cfg.tz, after=now_utc() - timedelta(seconds=warm + 600))
            out.append((nxt - timedelta(seconds=self.quiet_window_s), nxt + timedelta(seconds=warm + 300)))
        return out

    def _quiet_window_info(self, cfg) -> dict[str, Any] | None:
        now = now_utc()
        for a, b in self._quiet_windows(cfg):
            if a <= now <= b:
                return {"until": iso_utc(b)}
        return None

    def in_quiet_window(self) -> bool:
        return self._quiet_window_info(self.store.get()) is not None

    # ---- open / close ---------------------------------------------------------------
    def ensure_open(self, *, for_capture: bool = False) -> None:
        with self.dev_lock:
            if self.state == "open" and self._backend is not None:
                return
            if not for_capture:
                if self.paused_for:
                    raise CameraBusy(f"camera released for {self.paused_for}")
                if self.in_quiet_window():
                    raise CameraBusy("scheduled capture window — preview paused")
            if self.flock is not None and not self.flock.held:
                if not self.flock.acquire(timeout=480.0 if for_capture else 0.0):
                    pid = self.flock.holder_pid()
                    raise CameraBusy(f"camera lock held by pid {pid}")
            cfg = self.store.get()
            self.state = "opening"
            self.error = None
            try:
                be = self.backend_factory()
                self.prev_stream = be.open(tuple(cfg.capture.size), tuple(cfg.preview.size))
                be.apply_manual(cfg.capture.model_dump())
                time.sleep(2.0 if be.kind != "fake" else 0.05)
                self._backend = be
                self.driver = be.kind
                self.state = "open"
                self.opened_at = now_utc()
            except Exception as e:  # noqa: BLE001
                self.state = "error"
                self.error = f"{type(e).__name__}: {e}"
                if self.flock is not None:
                    self.flock.release()
                raise CameraUnavailable(self.error) from e
        self._emit("camera.open")

    def close(self) -> None:
        self._stop_grab()
        with self.dev_lock:
            be, self._backend = self._backend, None
            if be is not None:
                try:
                    be.close()
                except Exception:
                    pass
            if self.state != "error":
                self.state = "closed"
            self.opened_at = None
            if self.flock is not None:
                self.flock.release()
        self._emit("camera.close")

    def _emit(self, kind: str) -> None:
        st = {"state": self.state, "clients": self.clients, "preview": self.status()["preview"], "driver": self.driver}
        if self.events is not None:
            try:
                self.events.add(kind, st)
            except Exception:
                pass
        if self.hub is not None:
            self.hub.broadcast("camera.state", st)

    @contextmanager
    def exclusive(self, timeout: float = 120.0, label: str = "job"):
        if not self.ops_lock.acquire(timeout=timeout):
            raise CameraBusy(f"camera busy ({self.ops_busy})")
        self.ops_busy = label
        try:
            yield
        finally:
            self.ops_busy = None
            self.ops_lock.release()

    # ---- device ops -----------------------------------------------------------------
    def apply_controls(self, capture) -> None:
        cap = capture.model_dump() if hasattr(capture, "model_dump") else dict(capture)
        with self.dev_lock:
            if self._backend is not None:
                self._backend.apply_manual(cap)

    def preview_frame(self) -> np.ndarray:
        self.ensure_open()
        with self.dev_lock:
            assert self._backend is not None
            return self._backend.capture_array()

    def capture_still(self, path: str | os.PathLike) -> None:
        self.ensure_open(for_capture=True)
        with self.dev_lock:
            assert self._backend is not None
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self._backend.capture_file(str(path))

    def auto_cycle(self) -> dict[str, Any]:
        """Let the camera converge (AE/AWB/AF), read the values back, lock manual again."""
        self.ensure_open()
        with self.exclusive(timeout=30, label="auto"):
            with self.dev_lock:
                self._backend.enable_auto()
            time.sleep(3.0 if self.driver != "fake" else 0.1)
            with self.dev_lock:
                self._backend.autofocus_cycle()
            time.sleep(1.0 if self.driver != "fake" else 0.05)
            with self.dev_lock:
                m = self._backend.capture_metadata()
            cap = self.store.get().capture
            exp = int(m.get("ExposureTime") or cap.exposure_us)
            gain = float(m.get("AnalogueGain") or cap.gain)
            cg = m.get("ColourGains") or cap.colour_gains
            lens = float(m.get("LensPosition") if m.get("LensPosition") is not None else cap.lens_position)
            vals = {"exposure_us": exp, "gain": round(gain, 2),
                    "colour_gains": [round(float(cg[0]), 2), round(float(cg[1]), 2)],
                    "lens_position": round(lens, 2)}
            with self.dev_lock:
                self._backend.apply_manual({**cap.model_dump(), **vals})
            return vals

    # ---- preview streaming -------------------------------------------------------------
    def _grab_loop(self) -> None:
        cfg = self.store.get()
        period = max(0.03, cfg.preview.frame_ms / 1000)
        while not self._grab_stop.is_set():
            try:
                with self.dev_lock:
                    if self._backend is None or self.state != "open":
                        break
                    frame = self._backend.capture_array()
                self._latest = frame
                self._latest_at = time.time()
            except Exception as e:  # noqa: BLE001
                self.error = f"{type(e).__name__}: {e}"
                self.state = "error"
                break
            self._grab_stop.wait(period)

    def _start_grab(self) -> None:
        if self._grab is None or not self._grab.is_alive():
            self._grab_stop.clear()
            self._grab = threading.Thread(target=self._grab_loop, name="cam-grab", daemon=True)
            self._grab.start()

    def _stop_grab(self) -> None:
        self._grab_stop.set()
        t = self._grab
        if t is not None and t.is_alive() and threading.current_thread() is not t:
            t.join(timeout=2.0)
        self._grab = None

    def latest_frame(self, max_age: float = 2.0) -> np.ndarray | None:
        if self._latest is not None and time.time() - self._latest_at <= max_age:
            return self._latest
        try:
            return self.preview_frame()
        except CameraBusy:
            return None

    def encode(self, frame: np.ndarray, overlay: Callable[[np.ndarray], np.ndarray] | None = None) -> bytes:
        q = self.store.get().preview.jpeg_quality
        img = overlay(frame.copy()) if overlay else frame
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, int(q)])
        return buf.tobytes() if ok else b""

    def mjpeg(self, overlay: Callable[[np.ndarray], np.ndarray] | None = None) -> Iterator[bytes]:
        if self.clients >= self.max_clients:
            raise CameraBusy(f"too many preview streams ({self.max_clients})")
        self.ensure_open()
        self.clients += 1
        self._cancel_idle()
        self._start_grab()
        self._emit("camera.client")
        try:
            period = max(0.03, self.store.get().preview.frame_ms / 1000)
            last_sent = 0.0
            while self.state == "open" and not self.paused_for:
                if self._latest is not None and self._latest_at > last_sent:
                    last_sent = self._latest_at
                    jpg = self.encode(self._latest, overlay)
                    yield (b"--FRAME\r\nContent-Type: image/jpeg\r\nContent-Length: "
                           + str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n")
                time.sleep(period / 2)
        finally:
            self.clients = max(0, self.clients - 1)
            self._emit("camera.client")
            if self.clients == 0:
                self._schedule_idle()

    def frame_jpeg(self, overlay=None) -> bytes:
        fr = self.latest_frame()
        if fr is None:
            raise CameraBusy("no frame")
        return self.encode(fr, overlay)

    # ---- idle / release --------------------------------------------------------------
    def _schedule_idle(self) -> None:
        self._cancel_idle()
        t = threading.Timer(self.idle_close_s, self._idle_fire)
        t.daemon = True
        t.start()
        self._idle_timer = t

    def _cancel_idle(self) -> None:
        if self._idle_timer is not None:
            self._idle_timer.cancel()
            self._idle_timer = None

    def _idle_fire(self) -> None:
        if self.clients == 0 and self.ops_busy is None and self.state == "open":
            self.close()

    def release_for_capture(self, reason: str = "capture") -> dict[str, Any]:
        """Close the device for an external process and reopen for viewers when the lock is free."""
        self.paused_for = reason
        self._cancel_idle()
        self.close()
        self._emit("camera.paused")
        if self._watch is None or not self._watch.is_alive():
            self._watch = threading.Thread(target=self._watch_lock, name="cam-watch", daemon=True)
            self._watch.start()
        return self.status()

    def _watch_lock(self) -> None:
        deadline = time.monotonic() + 15 * 60
        time.sleep(3.0)                                    # give the other process time to take the lock
        while time.monotonic() < deadline:
            if self.flock is None or self.flock.holder_pid() is None:
                break
            time.sleep(2.0)
        self.paused_for = None
        self._emit("camera.resumed")
        if self.clients > 0:
            try:
                self.ensure_open()
                self._start_grab()
            except Exception:
                pass


__all__ = ["CameraManager", "CameraBusy", "FileLock"]
