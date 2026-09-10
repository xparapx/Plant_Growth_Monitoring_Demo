"""Capture jobs, schedule, LED, events."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from ..capture.replay import jsonl_tail, replay
from ..capture.runner import JobBusy
from ..led import LedNotInstalled
from ..timeutil import add_minutes, iso_utc, next_occurrence, now_utc, parse_systemd_ts
from .deps import ApiError, ctx

router = APIRouter(prefix="/api", tags=["capture"])


def _timer_info(tz: str | None = None) -> dict[str, Any] | None:
    if not shutil.which("systemctl"):
        return None
    try:
        out = subprocess.run(["systemctl", "show", "plantsnap.timer", "--property=ActiveState,NextElapseUSecRealtime,LastTriggerUSec"],
                             capture_output=True, text=True, timeout=3).stdout
    except Exception:
        return None
    d = dict(ln.split("=", 1) for ln in out.strip().splitlines() if "=" in ln)
    return {"unit": "plantsnap.timer", "active": d.get("ActiveState") == "active",
            "next": parse_systemd_ts(d.get("NextElapseUSecRealtime"), tz),
            "last": parse_systemd_ts(d.get("LastTriggerUSec"), tz),
            "next_raw": d.get("NextElapseUSecRealtime") or None}


@router.get("/capture/schedule")
def schedule(c=Depends(ctx)) -> dict[str, Any]:
    cfg = c.store.get()
    warm = cfg.led.warmup_s if (cfg.led.enabled and c.led.installed) else 0
    nd, npm = next_occurrence(cfg.schedule.dawn, cfg.tz), next_occurrence(cfg.schedule.pm, cfg.tz)
    nxt = min((nd, "dawn"), (npm, "pm"))
    return {"tz": cfg.tz, "dawn": cfg.schedule.dawn, "pm": cfg.schedule.pm, "warmup_s": warm,
            "expected_shot": {"dawn": add_minutes(cfg.schedule.dawn, warm // 60),
                              "pm": add_minutes(cfg.schedule.pm, warm // 60)},
            "next": {"phase": nxt[1], "at": iso_utc(nxt[0])},
            "timer": _timer_info(cfg.tz)}


@router.get("/capture/status")
def capture_status(c=Depends(ctx)) -> dict[str, Any]:
    jobs = c.events.jobs(limit=1)
    running = c.runner.current() or c.events.running_job()
    return {"job": running, "last": jobs[0] if jobs else None, "schedule": schedule(c),
            "led": c.led.status(), "camera": {"state": c.camera.state, "driver": c.camera.driver or c.camera.probe_driver(),
                                              "preview": c.camera.status()["preview"]}}


@router.post("/capture/run", status_code=202)
async def capture_run(c=Depends(ctx), phase: str = "auto", warmup_s: int | None = None, led: int = 1,
                      wait: int = 0, force: int = 0, allow_fake_publish: int = 0) -> dict[str, Any]:
    if c.runner.current():
        raise ApiError(409, "job_running", "a capture job is already running")
    if phase not in ("auto", "dawn", "pm"):
        raise ApiError(400, "bad_phase", "phase must be auto|dawn|pm")
    kwargs = dict(trigger="api", warmup_s=warmup_s, use_led=bool(led), force=bool(force),
                  allow_fake_publish=bool(allow_fake_publish))
    if wait:
        try:
            job = await run_in_threadpool(c.runner.run, phase, **kwargs)
        except JobBusy as e:
            raise ApiError(409, "job_running", str(e)) from e
        return {"job": job.to_dict()}
    loop = asyncio.get_running_loop()

    def _bg():
        try:
            c.runner.run(phase, **kwargs)
        except JobBusy:
            pass
    loop.run_in_executor(None, _bg)
    await asyncio.sleep(0.2)
    return {"job": c.runner.current() or {"state": "queued", "phase": phase}}


@router.post("/capture/cancel")
def capture_cancel(c=Depends(ctx)) -> dict[str, Any]:
    return {"cancelled": c.runner.cancel()}


@router.get("/capture/current")
def capture_current(c=Depends(ctx)) -> dict[str, Any]:
    return {"job": c.runner.current()}


@router.get("/capture/jobs")
def capture_jobs(c=Depends(ctx), limit: int = 20) -> dict[str, Any]:
    return {"jobs": c.events.jobs(limit=limit)}


@router.get("/capture/jobs/{job_id}")
def capture_job(job_id: str, c=Depends(ctx)) -> dict[str, Any]:
    j = c.events.job(job_id)
    if not j:
        raise ApiError(404, "no_job", job_id)
    return j


@router.post("/capture/replay")
async def capture_replay(c=Depends(ctx)) -> dict[str, Any]:
    return await run_in_threadpool(replay, c.paths, c.store.get(), log=None)


@router.get("/capture/jsonl")
def capture_jsonl(c=Depends(ctx), tail: int = 20) -> dict[str, Any]:
    return {"lines": jsonl_tail(c.paths, tail)}


# ---- LED ---------------------------------------------------------------------
@router.get("/led")
def led_status(c=Depends(ctx)) -> dict[str, Any]:
    return c.led.status()


def _led_call(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except LedNotInstalled as e:
        raise ApiError(409, "led_not_installed", str(e)) from e


@router.post("/led/on")
def led_on(c=Depends(ctx), max_s: int | None = None) -> dict[str, Any]:
    if c.runner.current():
        raise ApiError(409, "job_running", "capture job owns the LED right now")
    return _led_call(c.led.on, reason="api", max_on_s=max_s)


@router.post("/led/off")
def led_off(c=Depends(ctx)) -> dict[str, Any]:
    return c.led.off(reason="api")


@router.post("/led/test")
async def led_test(c=Depends(ctx), seconds: float = 2.0) -> dict[str, Any]:
    if c.runner.current():
        raise ApiError(409, "job_running", "capture job owns the LED right now")
    return await run_in_threadpool(lambda: _led_call(c.led.test, min(max(seconds, 0.2), 30.0)))


@router.get("/events")
def events(c=Depends(ctx), type: str | None = None, limit: int = 100) -> dict[str, Any]:
    return {"events": c.events.events(type, limit), "now": iso_utc(now_utc())}
