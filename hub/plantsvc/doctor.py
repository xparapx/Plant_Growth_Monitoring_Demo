"""plantsvc doctor - one table of OK / WARN / FAIL / SKIP with a one-line fix per row."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
from typing import Any

from .config_check import check
from .db import ro_connect, table_counts
from .settings import Paths, Settings
from .timeutil import add_minutes, seconds_between_hhmm


def _row(name: str, status: str, detail: str = "", fix: str = "") -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail, "fix": fix}


def run(settings: Settings, paths: Paths, *, led_test: bool = False) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    on_pi = sys.platform.startswith("linux") and os.path.exists("/proc/device-tree/model")

    # venv
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    cfgp = os.path.join(sys.prefix, "pyvenv.cfg")
    ssp = os.path.exists(cfgp) and "include-system-site-packages = true" in open(cfgp, encoding="utf-8").read()
    rows.append(_row("venv", "OK" if in_venv and (ssp or not on_pi) else ("FAIL" if on_pi else "WARN"),
                     f"{sys.prefix}" + ("" if ssp else " (system-site-packages off)"),
                     "uv venv --system-site-packages --python /usr/bin/python3 && uv sync --frozen"))

    # imports
    for mod, need_pi in (("cv2", True), ("numpy", True), ("pandas", True), ("fastapi", True), ("paho.mqtt", True),
                         ("picamera2", True), ("libcamera", True), ("gpiozero", False), ("lgpio", False)):
        try:
            __import__(mod)
            rows.append(_row(f"import {mod}", "OK"))
        except Exception as e:  # noqa: BLE001
            hw_only = mod in ("picamera2", "libcamera", "gpiozero", "lgpio")
            st = "FAIL" if (on_pi and need_pi and not settings.fake_hw) else ("WARN" if hw_only else "FAIL")
            if hw_only and not on_pi:
                st = "SKIP"
            rows.append(_row(f"import {mod}", st, f"{type(e).__name__}", "sudo apt install python3-picamera2 python3-gpiozero python3-lgpio"))

    # config
    try:
        from .config_store import ConfigStore
        store = ConfigStore(paths.config, example=paths.example_config)
        cfg = store.get()
        rep = check(cfg)
        rows.append(_row("config.json", "OK" if rep["ok"] else "WARN", "; ".join(rep["bad"][:3]) or f"{len(cfg.rois)} ROI",
                         "open the web UI camera setup"))
        for w in store.warnings:
            rows.append(_row("config migrate", "WARN", w))
    except Exception as e:  # noqa: BLE001
        rows.append(_row("config.json", "FAIL", str(e)))
        cfg = None

    # data dir
    try:
        paths.ensure()
        du = shutil.disk_usage(paths.data_dir)
        rows.append(_row("data dir", "OK" if du.free > 1_000_000_000 else "WARN",
                         f"{paths.data_dir}  free {du.free // 1_000_000} MB", "free disk space"))
    except Exception as e:  # noqa: BLE001
        rows.append(_row("data dir", "FAIL", str(e)))
    rows.append(_row("calib.jpg", "OK" if paths.calib.exists() else "WARN",
                     str(paths.calib) if paths.calib.exists() else "missing", "camera setup step 5"))

    # db
    conn = ro_connect(paths.db)
    if conn is None:
        rows.append(_row("plant.db", "WARN", "not created yet (start planthub, or `plantsvc seed` for dummy)"))
    else:
        try:
            tc = table_counts(conn)
            rows.append(_row("plant.db", "OK", ", ".join(f"{t}={v['rows']}" for t, v in tc.items())))
            if tc.get("growth", {}).get("max_ts") is None:
                rows.append(_row("growth rows", "WARN", "no measurements yet"))
        finally:
            conn.close()

    # broker
    host, port = (cfg.mqtt.host, cfg.mqtt.port) if cfg else ("localhost", 1883)
    try:
        with socket.create_connection((host, port), timeout=2):
            rows.append(_row("mqtt broker", "OK", f"{host}:{port}"))
    except OSError as e:
        rows.append(_row("mqtt broker", "WARN" if not on_pi else "FAIL", f"{host}:{port} {e}", "sudo systemctl start mosquitto"))

    # camera
    mode = settings.camera_mode
    if mode == "fake":
        rows.append(_row("camera", "SKIP", "fake backend (PLANT_CAMERA=fake / PLANT_FAKE_HW=1)"))
    else:
        try:
            from picamera2 import Picamera2
            info = Picamera2.global_camera_info()
            rows.append(_row("camera", "OK" if info else "FAIL", f"{len(info)} camera(s)", "check the ribbon cable; rpicam-hello"))
        except Exception as e:  # noqa: BLE001
            rows.append(_row("camera", "SKIP" if not on_pi else "FAIL", f"{type(e).__name__}"))
    from .camera.manager import FileLock
    pid = FileLock(paths.camera_lock).holder_pid() if paths.camera_lock.exists() else None
    rows.append(_row("camera lock", "OK" if pid in (None, os.getpid()) else "WARN",
                     "free" if pid in (None, os.getpid()) else f"held by pid {pid}"))

    # led
    if cfg is None or not cfg.led.enabled:
        rows.append(_row("led", "SKIP", "not installed (led.enabled=false)"))
    else:
        from .led import gpio_available
        ok, why = gpio_available()
        rows.append(_row("led", "OK" if ok else "FAIL", f"gpio {cfg.led.pin}" if ok else why,
                         "sudo apt install python3-gpiozero python3-lgpio; usermod -aG gpio $USER"))
        if led_test and ok:
            try:
                from .led import LedController
                LedController(store).test(1.0)
                rows.append(_row("led test", "OK", "1 s on/off"))
            except Exception as e:  # noqa: BLE001
                rows.append(_row("led test", "FAIL", str(e)))

    # schedule / time
    if cfg is not None:
        warm = cfg.led.warmup_s if cfg.led.enabled else 0
        shot = add_minutes(cfg.schedule.dawn, warm // 60 + 2)
        late = seconds_between_hhmm(shot, "06:00") < 0
        rows.append(_row("schedule", "WARN" if late else "OK",
                         f"dawn {cfg.schedule.dawn} (+{warm}s warm-up → shot ≈ {shot}), pm {cfg.schedule.pm}, tz {cfg.tz}",
                         "move schedule.dawn earlier" if late else ""))
    if shutil.which("timedatectl"):
        try:
            out = subprocess.run(["timedatectl", "show"], capture_output=True, text=True, timeout=3).stdout
            d = dict(ln.split("=", 1) for ln in out.strip().splitlines() if "=" in ln)
            tzok = (cfg is None) or d.get("Timezone") == cfg.tz
            rows.append(_row("timezone", "OK" if tzok else "WARN", d.get("Timezone", "?"),
                             f"sudo timedatectl set-timezone {cfg.tz if cfg else 'Asia/Seoul'}"))
            rows.append(_row("ntp sync", "OK" if d.get("NTPSynchronized") == "yes" else "WARN", d.get("NTPSynchronized", "?"),
                             "sudo systemctl enable --now systemd-time-wait-sync"))
        except Exception:
            pass
    if shutil.which("systemctl"):
        for u in ("mosquitto", "planthub", "plantsvc", "plantsnap.timer", "plantsnap-catchup"):
            try:
                r = subprocess.run(["systemctl", "is-active", u], capture_output=True, text=True, timeout=3).stdout.strip()
                rows.append(_row(f"unit {u}", "OK" if r == "active" else "WARN", r, f"sudo systemctl enable --now {u}"))
            except Exception:
                pass

    # web
    rows.append(_row("web/dist", "OK" if (paths.web_dist / "index.html").exists() else "WARN",
                     str(paths.web_dist), "scripts/install.sh --web=release  (or npm run build in web/)"))
    return rows


def format_table(rows: list[dict[str, Any]], brief: bool = False) -> str:
    out = []
    for r in rows:
        if brief and r["status"] == "OK":
            continue
        line = f"  {r['status']:<5} {r['name']:<20} {r['detail']}"
        if r["fix"] and r["status"] in ("WARN", "FAIL"):
            line += f"\n        → {r['fix']}"
        out.append(line)
    n = {s: sum(1 for r in rows if r["status"] == s) for s in ("OK", "WARN", "FAIL", "SKIP")}
    out.append(f"\n  {n['OK']} ok · {n['WARN']} warn · {n['FAIL']} fail · {n['SKIP']} skipped")
    return "\n".join(out)


def to_json(rows: list[dict[str, Any]]) -> str:
    return json.dumps(rows, ensure_ascii=False, indent=2)
