"""The single capture code path (CLI from the systemd timer, or the API button).

  queued -> lock -> led_on -> warmup -> camera_open -> controls -> settle -> capture
         -> led_off (finally) -> measure -> jsonl -> publish -> done | failed

Rules kept from run_capture.py: config.capture is re-applied right before the
shot (an unsaved auto-exposure in the browser cannot leak into a scheduled
frame); growth.jsonl is appended BEFORE the MQTT publish (qos=1); ok==0 means
the job failed so systemd records it.  New: dedupe/debounce so Persistent=true
catch-ups do not double-shoot, and fake-camera frames are never published.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from ..config_model import Config
from ..timeutil import (
    db_ts,
    iso_utc,
    local_day,
    local_stem,
    now_utc,
    parse_db_ts,
    phase_now,
    to_local,
)
from ..vision import leaf_measure
from .publisher import publish as _publish

DEBOUNCE_S = 30 * 60


class JobBusy(RuntimeError):
    pass


class JobCancelled(RuntimeError):
    pass


@dataclass
class JobRecord:
    id: str
    phase: str
    trigger: str
    state: str = "queued"          # queued | running | done | failed | skipped | cancelled
    step: str = "queued"
    started_at: str = ""
    finished_at: str | None = None
    img_file: str | None = None
    n_rows: int = 0
    ok_rows: int = 0
    published: bool = False
    error: str | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    warmup_s: int = 0
    warm_until: str | None = None
    led: dict[str, Any] | None = None
    fake: bool = False
    drift: dict[str, Any] | None = None
    log: list[str] = field(default_factory=list)
    publish_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["rows"] = [{k: v for k, v in r.items() if k != "contour"} for r in self.rows]
        return d


class CaptureRunner:
    def __init__(self, paths, store, camera, led, events=None, hub=None, *, publish=_publish):
        self.paths = paths
        self.store = store
        self.camera = camera
        self.led = led
        self.events = events
        self.hub = hub
        self._publish = publish
        self._lock = threading.Lock()
        self._current: JobRecord | None = None
        self._cancel = threading.Event()

    # ---- status ---------------------------------------------------------------
    def current(self) -> dict[str, Any] | None:
        j = self._current
        return j.to_dict() if j and j.state in ("queued", "running") else None

    def cancel(self) -> bool:
        if self._current and self._current.state in ("queued", "running"):
            self._cancel.set()
            return True
        return False

    # ---- helpers --------------------------------------------------------------
    def _mark(self, job: JobRecord, step: str, **extra: Any) -> None:
        now = now_utc()
        if job.steps:
            prev = job.steps[-1]
            prev["ms"] = int((now - parse_db_ts(prev["at"])).total_seconds() * 1000)
        job.steps.append({"name": step, "at": iso_utc(now), "ms": None})
        job.step = step
        for k, v in extra.items():
            setattr(job, k, v)
        self._persist(job)
        if self.hub is not None:
            self.hub.broadcast("capture.progress", job.to_dict())

    def _persist(self, job: JobRecord) -> None:
        if self.events is None:
            return
        d = job.to_dict()
        d["published"] = int(job.published)
        try:
            self.events.upsert_job(d)
        except Exception:
            pass

    def _log(self, job: JobRecord, msg: str) -> None:
        job.log.append(msg)
        try:
            print(msg, flush=True)
        except UnicodeEncodeError:            # cp949 console on Windows; never let logging kill a capture
            print(msg.encode("ascii", "replace").decode(), flush=True)

    def _existing(self, cfg: Config, phase: str) -> tuple[datetime | None, bool]:
        """(when, had_ok_rows) of the last jsonl entry for (today local, phase)."""
        if not self.paths.jsonl.exists():
            return None, False
        today = local_day(now_utc(), cfg.tz)
        best: tuple[datetime | None, bool] = (None, False)
        for line in self.paths.jsonl.read_text(encoding="utf-8").splitlines()[-200:]:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("phase") != phase or str(d.get("img", "")).startswith("fake_"):
                continue
            t = parse_db_ts(d.get("t"))
            if t is None or local_day(t, cfg.tz) != today:
                continue
            ok = any(int(p.get("ok") or 0) for p in d.get("plants", []))
            if ok and (best[0] is None or t > best[0]):
                best = (t, True)
        return best

    def _in_window(self, cfg: Config, phase: str) -> bool:
        h = to_local(now_utc(), cfg.tz).hour * 60 + to_local(now_utc(), cfg.tz).minute
        from ..timeutil import parse_hhmm
        if phase == "dawn":
            sh, sm = parse_hhmm(cfg.schedule.dawn)
            return sh * 60 + sm <= h < 12 * 60
        sh, sm = parse_hhmm(cfg.schedule.pm)
        return sh * 60 + sm <= h < 22 * 60

    def _wait(self, seconds: float, job: JobRecord) -> None:
        if seconds <= 0:
            return
        if self._cancel.wait(timeout=seconds):
            raise JobCancelled("cancelled during warm-up")

    # ---- the routine ------------------------------------------------------------
    def run(self, phase: str = "auto", *, trigger: str = "manual", warmup_s: int | None = None,
            use_led: bool = True, force: bool = False, if_missing: bool = False,
            allow_fake_publish: bool = False) -> JobRecord:
        if not self._lock.acquire(blocking=False):
            raise JobBusy("capture already running")
        self._cancel.clear()
        cfg = self.store.get()
        ph = phase if phase in ("dawn", "pm") else phase_now(cfg.tz)
        job = JobRecord(id=uuid.uuid4().hex[:12], phase=ph, trigger=trigger,
                        started_at=iso_utc(now_utc()))
        self._current = job
        try:
            return self._run(job, cfg, warmup_s, use_led, force, if_missing, allow_fake_publish)
        finally:
            job.finished_at = job.finished_at or iso_utc(now_utc())
            self._persist(job)
            if self.hub is not None:
                self.hub.broadcast("capture.done", job.to_dict())
            self._lock.release()

    def _run(self, job: JobRecord, cfg: Config, warmup_s, use_led, force, if_missing,
             allow_fake_publish) -> JobRecord:
        self._mark(job, "queued")
        job.state = "running"

        # -- dedupe -------------------------------------------------------------
        when, had_ok = self._existing(cfg, job.phase)
        if if_missing:
            if not self._in_window(cfg, job.phase):
                return self._finish(job, "skipped", f"outside window for {job.phase}")
            if had_ok:
                return self._finish(job, "skipped", f"already captured at {iso_utc(when)}")
        elif had_ok and not force and when and (now_utc() - when).total_seconds() < DEBOUNCE_S:
            return self._finish(job, "skipped", f"debounced: {job.phase} already captured at {iso_utc(when)}")

        self.paths.ensure()
        led_installed = bool(use_led and self.led is not None and self.led.installed)
        job.warmup_s = int(cfg.led.warmup_s if warmup_s is None else warmup_s) if led_installed else 0
        job.fake = (self.camera.driver or self.camera.probe_driver()) == "fake"
        stem = local_stem(now_utc(), cfg.tz)
        if job.fake:
            stem = "fake_" + stem
        path = self.paths.raw / f"{stem}.jpg"
        job.img_file = path.name

        try:
            self._mark(job, "lock")
            with self.camera.exclusive(timeout=120):
                # LED on -> warm-up -> shoot, off in finally
                self._mark(job, "led_on")
                if self.led is not None:
                    ctx = self.led.lit("capture", use_led=use_led)
                else:
                    from contextlib import nullcontext
                    ctx = nullcontext({"installed": False, "state": "off"})
                with ctx as led_status:
                    job.led = dict(led_status) if isinstance(led_status, dict) else None
                    if job.led and not job.led.get("installed"):
                        self._log(job, f"[LED] skipped — {job.led.get('reason') or 'not installed'}")
                    if job.warmup_s > 0:
                        job.warm_until = iso_utc(now_utc() + timedelta(seconds=job.warmup_s))
                        self._mark(job, "warmup")
                        self._log(job, f"[LED] on — warm-up {job.warmup_s}s")
                        self._wait(job.warmup_s, job)
                    self._mark(job, "camera_open")
                    self.camera.ensure_open(for_capture=True)
                    self._mark(job, "controls")
                    self.camera.apply_controls(self.store.get().capture)   # persisted values only
                    self._mark(job, "settle")
                    self._wait(0.1 if job.fake else 2.0, job)
                    self._mark(job, "capture")
                    self.camera.capture_still(path)
                    self._log(job, f"[{stem}] shot {path.name}")
                self._mark(job, "led_off")
        except JobCancelled as e:
            return self._finish(job, "cancelled", str(e))
        except Exception as e:  # noqa: BLE001
            return self._finish(job, "failed", f"{type(e).__name__}: {e}")

        # -- measure / record / publish --------------------------------------------
        try:
            self._mark(job, "measure")
            C = self.store.get().to_legacy_dict()
            rows = leaf_measure.measure(str(path), job.phase, self.paths.debug, self.paths.mask, C,
                                        ref_path=self.paths.calib, log=lambda m: self._log(job, m))
            job.rows = rows
            job.n_rows = len(rows)
            job.ok_rows = int(sum(int(r.get("ok") or 0) for r in rows))
        except Exception as e:  # noqa: BLE001
            return self._finish(job, "failed", f"measure: {type(e).__name__}: {e}")

        payload = json.dumps({"t": db_ts(), "phase": job.phase, "img": path.name, "plants": rows},
                             ensure_ascii=False)
        self._mark(job, "jsonl")
        with open(self.paths.jsonl, "a", encoding="utf-8") as f:     # ★ before publishing
            f.write(payload + "\n")

        self._mark(job, "publish")
        if job.fake and not allow_fake_publish:
            job.published = False
            job.publish_error = "fake camera frame — not published"
            self._log(job, "[publish] skipped: fake camera frame")
        else:
            m = self.store.get().mqtt
            sent, err = self._publish(payload, m.growth_topic, m.host, m.port)
            job.published = bool(sent)
            job.publish_error = err or None
            self._log(job, f"[{stem}] {job.phase}  {job.ok_rows}/{job.n_rows} ok  ->  "
                           + (f"{m.growth_topic} 발행" if sent else f"발행 실패({err}) — {self.paths.jsonl} 에는 저장됨"))
        for r in rows:
            self._log(job, f"  {r['plant_id']:>4} {str(r['area_cm2']):>8} cm2  "
                           f"{'ok' if r['ok'] else 'NG'}  {'contour' if r['contour'] else 'NO CONTOUR'}")
        if job.ok_rows == 0:
            return self._finish(job, "failed", "no valid measurement — check photos/debug")
        return self._finish(job, "done", None)

    def _finish(self, job: JobRecord, state: str, error: str | None) -> JobRecord:
        job.state = state
        job.error = error
        job.finished_at = iso_utc(now_utc())
        self._mark(job, state)
        if self.events is not None:
            try:
                self.events.add(f"capture.{state}", {"id": job.id, "phase": job.phase, "trigger": job.trigger,
                                                     "ok_rows": job.ok_rows, "n_rows": job.n_rows,
                                                     "img_file": job.img_file, "error": error})
            except Exception:
                pass
        return job


def wall_time_utc(h: int, m: int, tz: str) -> datetime:
    """Today's local HH:MM as UTC (helper for tests/doctor)."""
    from ..timeutil import tzinfo
    loc = datetime.now(tzinfo(tz)).replace(hour=h, minute=m, second=0, microsecond=0)
    return loc.astimezone(timezone.utc)


__all__ = ["CaptureRunner", "JobRecord", "JobBusy", "JobCancelled", "DEBOUNCE_S", "os", "time"]
