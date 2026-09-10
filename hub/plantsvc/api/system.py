"""System status: versions, services, disk, DB counts, logs."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import time
from typing import Any

from fastapi import APIRouter, Depends

from .. import __version__
from ..db import ro_connect, table_counts
from ..timeutil import iso_utc, now_utc
from .deps import ApiError, ctx

router = APIRouter(prefix="/api/system", tags=["system"])
UNITS = ("mosquitto", "planthub", "plantsvc", "plantsnap.timer", "plantsnap-catchup")


def _ver(mod: str) -> str | None:
    try:
        m = __import__(mod)
        return getattr(m, "__version__", None) or "present"
    except Exception:
        return None


def _git_rev(root) -> str | None:
    try:
        return subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, timeout=3).stdout.strip() or None
    except Exception:
        return None


def services_status() -> dict[str, Any] | None:
    if not shutil.which("systemctl"):
        return None
    out: dict[str, Any] = {}
    for u in UNITS:
        try:
            r = subprocess.run(["systemctl", "show", u, "--property=ActiveState,SubState,ActiveEnterTimestamp,UnitFileState"],
                               capture_output=True, text=True, timeout=3).stdout
            d = dict(ln.split("=", 1) for ln in r.strip().splitlines() if "=" in ln)
            out[u] = {"active": d.get("ActiveState"), "sub": d.get("SubState"), "since": d.get("ActiveEnterTimestamp") or None,
                      "enabled": d.get("UnitFileState")}
        except Exception as e:  # noqa: BLE001
            out[u] = {"active": None, "error": str(e)}
    return out


def _cpu_temp() -> float | None:
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return round(int(f.read().strip()) / 1000, 1)
    except Exception:
        return None


def _uptime_s() -> int | None:
    try:
        with open("/proc/uptime") as f:
            return int(float(f.read().split()[0]))
    except Exception:
        return None


@router.get("/status")
def status(c=Depends(ctx)) -> dict[str, Any]:
    conn = ro_connect(c.paths.db)
    try:
        counts = table_counts(conn)
    finally:
        if conn is not None:
            conn.close()
    du = shutil.disk_usage(c.paths.data_dir)
    photos = {}
    for k, d in (("raw", c.paths.raw), ("debug", c.paths.debug), ("mask", c.paths.mask)):
        try:
            photos[k] = sum(1 for p in d.iterdir() if p.is_file())
        except FileNotFoundError:
            photos[k] = 0
    cfg = c.store.get()
    return {"version": __version__, "git_rev": _git_rev(c.paths.repo_root), "python": sys.version.split()[0],
            "platform": platform.platform(), "hostname": platform.node(),
            "opencv": _ver("cv2"), "picamera2": _ver("picamera2"), "gpiozero": _ver("gpiozero"),
            "tz": cfg.tz, "time": iso_utc(now_utc()), "uptime_s": _uptime_s(),
            "service_uptime_s": int((now_utc() - c.started_at).total_seconds()), "cpu_temp_c": _cpu_temp(),
            "data_dir": str(c.paths.data_dir), "repo_root": str(c.paths.repo_root),
            "disk": {"total": du.total, "used": du.used, "free": du.free},
            "db": {"path": str(c.paths.db), "exists": c.paths.db.exists(),
                   "size": c.paths.db.stat().st_size if c.paths.db.exists() else 0, "tables": counts},
            "photos": photos, "services": services_status(),
            "camera": c.camera.status(), "led": c.led.status(),
            "mqtt": c.bridge.status() if c.bridge else {"connected": False, "broker": None, "disabled": True},
            "ws_clients": c.hub.client_count, "web_dist": c.paths.web_dist.exists(),
            "dummy_fill": cfg.analysis.dummy_fill, "pid": os.getpid(), "started_at": iso_utc(c.started_at)}


@router.get("/logs")
def logs(unit: str = "plantsvc", lines: int = 100) -> dict[str, Any]:
    if unit not in UNITS and unit != "plantsnap":
        raise ApiError(400, "bad_unit", f"unit must be one of {UNITS + ('plantsnap',)}")
    if not shutil.which("journalctl"):
        return {"unit": unit, "lines": [], "available": False}
    try:
        r = subprocess.run(["journalctl", "-u", unit, "-n", str(min(max(lines, 1), 1000)), "--no-pager", "-o", "short-iso"],
                           capture_output=True, text=True, timeout=5)
        return {"unit": unit, "lines": r.stdout.splitlines(), "available": True}
    except Exception as e:  # noqa: BLE001
        return {"unit": unit, "lines": [], "available": False, "error": str(e)}


@router.get("/time")
def server_time() -> dict[str, Any]:
    return {"time": iso_utc(now_utc()), "epoch": time.time()}
