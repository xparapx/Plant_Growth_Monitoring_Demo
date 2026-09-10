"""Config read/write/check."""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Body, Depends, Header

from ..config_check import check
from ..config_store import ConfigError
from ..db import ro_connect
from .deps import ApiError, ctx

router = APIRouter(prefix="/api/config", tags=["config"])


def _doc(c) -> dict[str, Any]:
    cfg = c.store.get()
    return {"config": cfg.model_dump(mode="json"), "path": str(c.store.path), "mtime": c.store.mtime_ns,
            "warnings": c.store.warnings, "check": check(cfg)}


@router.get("")
def get_config(c=Depends(ctx)) -> dict[str, Any]:
    return _doc(c)


def _deep_merge(base: dict, patch: dict) -> dict:
    out = dict(base)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _write(c, data: dict[str, Any], if_match: str | None):
    if if_match and str(c.store.mtime_ns) != if_match:
        raise ApiError(409, "stale", "config changed since you loaded it — reload and retry")
    try:
        cfg = c.store.replace(data)
    except ConfigError as e:
        raise ApiError(422, "invalid_config", str(e)) from e
    rep = check(cfg)
    if c.camera.state == "open":
        try:
            c.camera.apply_controls(cfg.capture)
        except Exception:
            pass
    return {**_doc(c), "check": rep}


@router.put("")
def put_config(c=Depends(ctx), body: dict[str, Any] = Body(...), if_match: str | None = Header(None)) -> dict[str, Any]:
    return _write(c, body, if_match)


@router.patch("")
def patch_config(c=Depends(ctx), body: dict[str, Any] = Body(...), if_match: str | None = Header(None)) -> dict[str, Any]:
    return _write(c, _deep_merge(c.store.get().model_dump(mode="json"), body), if_match)


@router.get("/check")
def get_check(c=Depends(ctx)) -> dict[str, Any]:
    return check(c.store.get())


@router.get("/db-check")
def db_check(c=Depends(ctx)) -> dict[str, Any]:
    """Read-only port of check_db.py: DB labels vs config.json rois[].treat."""
    want = c.store.get().roi_map()
    conn = ro_connect(c.paths.db)
    out: dict[str, Any] = {"want": want, "tables": {}, "mismatched_rows": 0}
    if conn is None:
        return out
    try:
        for t in ("soil", "pump_log", "growth"):
            try:
                rows = list(conn.execute(f"SELECT plant_id, treat, COUNT(*), MIN(ts), MAX(ts) FROM {t} "
                                         f"GROUP BY plant_id, treat ORDER BY plant_id, treat"))
            except sqlite3.OperationalError:
                continue
            items = []
            for pid, tr, n, lo, hi in rows:
                ok = want.get(pid, "\0") == (tr or "")
                items.append({"plant_id": pid, "treat": tr, "rows": n, "min_ts": lo, "max_ts": hi, "ok": ok,
                              "config_treat": want.get(pid)})
                if not ok:
                    out["mismatched_rows"] += n
            out["tables"][t] = items
    finally:
        conn.close()
    return out
