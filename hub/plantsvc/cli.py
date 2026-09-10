"""plantsvc command line.

  plantsvc serve [--host H] [--port P]
  plantsvc capture [--phase auto|dawn|pm] [--force] [--if-missing] [--no-led] [--warmup N]
                   [--allow-fake-publish] [--no-release]      <- what plantsnap.service runs
  plantsvc led on|off|test [--seconds N]
  plantsvc replay
  plantsvc seed [--days 7] [--force]                          <- dummy plant.db for PC/CI
  plantsvc check-config
  plantsvc doctor [--brief] [--json] [--led-test]
  plantsvc render-units [--user U] [--root DIR] [--data-dir DIR] [--out DIR]
  plantsvc migrate-data --from DIR [--dry-run]
  plantsvc version
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

from . import __version__
from .settings import Settings


def _settings(args) -> Settings:
    kw = {}
    if getattr(args, "data_dir", None):
        os.environ["PLANT_DATA_DIR"] = str(args.data_dir)
    return Settings(**kw)


# ---- serve -------------------------------------------------------------------
def cmd_serve(args) -> int:
    import uvicorn

    from .app import create_app
    s = _settings(args)
    host = args.host or s.host
    port = args.port or s.port
    app = create_app(s)
    print(f"plantsvc {__version__}  http://{host}:{port}  data={s.paths.data_dir}  camera={s.camera_mode}")
    uvicorn.run(app, host=host, port=port, log_level="info", access_log=False)
    return 0


# ---- capture -------------------------------------------------------------------
def _release_service(port: int) -> None:
    """Ask a running service to let go of the camera (best effort, 3 s)."""
    try:
        import httpx
        httpx.post(f"http://127.0.0.1:{port}/api/camera/release", timeout=3.0)
    except Exception:
        pass


def cmd_capture(args) -> int:
    from .context import build_context
    s = _settings(args)
    ctx = build_context(s, mqtt=False)
    if not args.no_release:
        _release_service(s.port)
    try:
        job = ctx.runner.run(args.phase, trigger="cli", warmup_s=args.warmup, use_led=not args.no_led,
                             force=args.force, if_missing=args.if_missing,
                             allow_fake_publish=args.allow_fake_publish)
    finally:
        ctx.close()
    print(f"[{job.id}] {job.phase} {job.state} ok={job.ok_rows}/{job.n_rows} img={job.img_file} "
          f"published={job.published} {('error=' + job.error) if job.error else ''}")
    if job.state == "skipped":
        return 0
    return 0 if job.state == "done" and job.ok_rows > 0 else 1


# ---- led -----------------------------------------------------------------------
def cmd_led(args) -> int:
    import time

    from .config_store import ConfigStore
    from .led import LedController, LedNotInstalled
    s = _settings(args)
    p = s.paths.ensure()
    store = ConfigStore(p.config, example=p.example_config)
    led = LedController(store, mode_override=s.led_mode)
    try:
        if args.action == "on":
            print(json.dumps(led.on(reason="cli", max_on_s=args.seconds), ensure_ascii=False))
            if args.seconds:
                time.sleep(args.seconds)
                led.off(reason="cli")
        elif args.action == "off":
            led.force_off()
            print(json.dumps(led.status(), ensure_ascii=False))
        else:
            print(json.dumps(led.test(args.seconds or 2.0), ensure_ascii=False))
    except LedNotInstalled as e:
        print(f"LED not installed: {e}")
        return 0
    return 0


# ---- replay / seed / check ----------------------------------------------------------
def cmd_replay(args) -> int:
    from .capture.replay import replay
    from .config_store import ConfigStore
    s = _settings(args)
    p = s.paths
    cfg = ConfigStore(p.config, example=p.example_config).get()
    out = replay(p, cfg, allow_fake=args.allow_fake_publish)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not out["errors"] else 1


def cmd_seed(args) -> int:
    from .analytics.dummy import synth
    from .config_store import ConfigStore
    from .schema import ensure_schema
    from .timeutil import DB_FMT
    s = _settings(args)
    p = s.paths.ensure()
    if p.db.exists() and not args.force:
        print(f"{p.db} exists — refusing to overwrite (use --force)")
        return 1
    if p.db.exists():
        p.db.unlink()
    cfg = ConfigStore(p.config, example=p.example_config).get()
    soil, pump, grow, env = synth(cfg, None, days=args.days)
    conn = sqlite3.connect(p.db)
    ensure_schema(conn, log=None)

    def rows(df, cols):
        for r in df.to_dict("records"):
            yield tuple(r["ts"].strftime(DB_FMT) if c == "ts" else (None if (isinstance(r.get(c), float) and r[c] != r[c]) else r.get(c)) for c in cols)
    ins = lambda t, cols, df: conn.executemany(  # noqa: E731
        f"INSERT INTO {t}({','.join(cols)}) VALUES({','.join('?' * len(cols))})", list(rows(df, cols)))
    ins("readings", ["ts", "node", "temp", "hum", "press", "vpd", "lux", "co2", "n"], env)
    ins("soil", ["ts", "node", "plant_id", "treat", "raw", "pct", "n"], soil)
    ins("pump_log", ["ts", "node", "plant_id", "treat", "dur_ms", "soil_before", "soil_after", "raw_before", "raw_after", "shots", "reason"], pump)
    ins("growth", ["ts", "plant_id", "treat", "phase", "area_cm2", "area_px", "px_per_cm", "img_file", "contour", "ok"], grow)
    conn.commit()
    conn.close()
    print(f"seeded {p.db}: readings={len(env)} soil={len(soil)} pump_log={len(pump)} growth={len(grow)} (node='dummy')")
    return 0


def cmd_check_config(args) -> int:
    from .config_check import check, format_report
    from .config_store import ConfigError, ConfigStore
    s = _settings(args)
    p = s.paths
    try:
        cfg = ConfigStore(p.config, example=p.example_config).get()
    except ConfigError as e:
        print(e)
        return 1
    rep = check(cfg)
    print(format_report(rep))
    return 0 if rep["ok"] else 1


def cmd_doctor(args) -> int:
    from . import doctor
    s = _settings(args)
    rows = doctor.run(s, s.paths, led_test=args.led_test)
    print(doctor.to_json(rows) if args.json else doctor.format_table(rows, brief=args.brief))
    return 1 if any(r["status"] == "FAIL" for r in rows) else 0


# ---- deploy helpers --------------------------------------------------------------------
def cmd_render_units(args) -> int:
    from .config_store import ConfigStore
    s = _settings(args)
    p = s.paths
    root = Path(args.root or p.repo_root).resolve()
    user = args.user or os.environ.get("USER") or os.environ.get("USERNAME") or "pi"
    cfg = ConfigStore(p.config, example=p.example_config).get()
    warm = cfg.led.warmup_s if cfg.led.enabled else 0
    values = {"PLANT_USER": user, "PLANT_DIR": str(root), "PLANT_DATA_DIR": str(Path(args.data_dir or p.data_dir).resolve()),
              "DAWN_TIME": cfg.schedule.dawn, "PM_TIME": cfg.schedule.pm, "LED_WARMUP_S": str(warm),
              "SNAP_TIMEOUT_S": str(max(900, warm + 600)), "PLANT_PORT": str(s.port)}
    tdir = root / "deploy" / "systemd"
    out = Path(args.out) if args.out else tdir / "rendered"
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for t in sorted(tdir.glob("*.tmpl")):
        txt = t.read_text(encoding="utf-8")
        for k, v in values.items():
            txt = txt.replace("${" + k + "}", v)
        if "${" in txt:
            print(f"WARN {t.name}: unresolved placeholder", file=sys.stderr)
        (out / t.name[:-5]).write_text(txt, encoding="utf-8", newline="\n")
        n += 1
    print(json.dumps({"rendered": n, "out": str(out), **values}, ensure_ascii=False, indent=2))
    return 0


def cmd_migrate_data(args) -> int:
    import shutil
    s = _settings(args)
    p = s.paths.ensure()
    src = Path(args.src).expanduser().resolve()
    if not src.exists():
        print(f"{src} does not exist")
        return 1
    plan = []
    for name in ("plant.db", "config.json", "calib.jpg", "truth.json"):
        if (src / name).exists():
            plan.append((src / name, p.data_dir / name))
    if (src / "photos").exists():
        plan.append((src / "photos", p.photos))
    for a, b in plan:
        print(f"  {a}  ->  {b}")
    if args.dry_run:
        return 0
    for a, b in plan:
        if b.exists() and not args.force:
            print(f"  skip {b} (exists; use --force)")
            continue
        if a.name == "plant.db":
            srcc = sqlite3.connect(str(a))
            dst = sqlite3.connect(str(b))
            srcc.backup(dst)
            dst.close()
            srcc.close()
        elif a.is_dir():
            shutil.copytree(a, b, dirs_exist_ok=True)
        else:
            shutil.copy2(a, b)
    print("done — run `plantsvc doctor`")
    return 0


# ---- entry ----------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="plantsvc", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", help="override PLANT_DATA_DIR")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("serve")
    s.add_argument("--host")
    s.add_argument("--port", type=int)
    s.set_defaults(fn=cmd_serve)

    c = sub.add_parser("capture")
    c.add_argument("--phase", default="auto", choices=["auto", "dawn", "pm"])
    c.add_argument("--force", action="store_true")
    c.add_argument("--if-missing", action="store_true")
    c.add_argument("--no-led", action="store_true")
    c.add_argument("--warmup", type=int)
    c.add_argument("--allow-fake-publish", action="store_true")
    c.add_argument("--no-release", action="store_true", help="do not ask a running service to release the camera")
    c.set_defaults(fn=cmd_capture)

    led = sub.add_parser("led")
    led.add_argument("action", choices=["on", "off", "test"])
    led.add_argument("--seconds", type=float)
    led.set_defaults(fn=cmd_led)

    r = sub.add_parser("replay")
    r.add_argument("--allow-fake-publish", action="store_true")
    r.set_defaults(fn=cmd_replay)

    sd = sub.add_parser("seed")
    sd.add_argument("--days", type=int, default=7)
    sd.add_argument("--force", action="store_true")
    sd.set_defaults(fn=cmd_seed)

    sub.add_parser("check-config").set_defaults(fn=cmd_check_config)

    d = sub.add_parser("doctor")
    d.add_argument("--brief", action="store_true")
    d.add_argument("--json", action="store_true")
    d.add_argument("--led-test", action="store_true")
    d.set_defaults(fn=cmd_doctor)

    ru = sub.add_parser("render-units")
    ru.add_argument("--user")
    ru.add_argument("--root")
    ru.add_argument("--out")
    ru.set_defaults(fn=cmd_render_units)

    mg = sub.add_parser("migrate-data")
    mg.add_argument("--from", dest="src", required=True)
    mg.add_argument("--dry-run", action="store_true")
    mg.add_argument("--force", action="store_true")
    mg.set_defaults(fn=cmd_migrate_data)

    sub.add_parser("version").set_defaults(fn=lambda a: print(__version__) or 0)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.fn(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
