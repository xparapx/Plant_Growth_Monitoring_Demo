"""Evidence images (raw / debug / mask / calib / data) and CSV export.

Path safety: name must match a strict pattern and the resolved path must stay
inside the kind's directory.  The old `python -m http.server 8080` exposed
plant.db - that must never come back.
"""

from __future__ import annotations

import io
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, Response, StreamingResponse

from .deps import ApiError, ctx

router = APIRouter(prefix="/api", tags=["images"])

NAME_RE = re.compile(r"^[A-Za-z0-9_\-.]+\.(jpg|jpeg|png)$")
KINDS = ("raw", "debug", "mask", "calib", "data")


def _dir(c, kind: str) -> Path:
    if kind == "raw":
        return c.paths.raw
    if kind == "debug":
        return c.paths.debug
    if kind == "mask":
        return c.paths.mask
    if kind in ("calib", "data"):
        return c.paths.data_dir
    raise ApiError(404, "bad_kind", f"kind must be one of {KINDS}")


def _safe(c, kind: str, name: str) -> Path:
    if not NAME_RE.match(name) or ".." in name:
        raise ApiError(404, "not_found", name)
    base = _dir(c, kind).resolve()
    p = (base / name).resolve()
    if not p.is_relative_to(base) or not p.is_file():
        raise ApiError(404, "not_found", name)
    return p


@router.get("/images")
def list_images(c=Depends(ctx), kind: str = "raw", limit: int = 50, before: str | None = None) -> dict[str, Any]:
    d = _dir(c, kind)
    if not d.exists():
        return {"kind": kind, "files": []}
    files = sorted((p for p in d.iterdir() if p.is_file() and NAME_RE.match(p.name)), key=lambda p: p.name, reverse=True)
    if before:
        files = [p for p in files if p.name < before]
    out = []
    for p in files[:limit]:
        st = p.stat()
        m = re.match(r"^(fake_)?(\d{4}-\d{2}-\d{2}_\d{4})(?:_(p\d+))?\.", p.name)
        out.append({"name": p.name, "size": st.st_size, "mtime": int(st.st_mtime),
                    "stem": m.group(2) if m else None, "plant_id": m.group(3) if m else None,
                    "fake": bool(m and m.group(1)), "url": f"/api/images/{kind}/{p.name}"})
    return {"kind": kind, "files": out}


@lru_cache(maxsize=32)
def _thumb(path: str, mtime: int, w: int) -> bytes:
    img = cv2.imread(path)
    if img is None:
        return b""
    h = int(img.shape[0] * w / img.shape[1])
    small = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 82])
    return buf.tobytes() if ok else b""


@router.get("/images/{kind}/{name}")
def get_image(kind: str, name: str, c=Depends(ctx), w: int | None = None):
    p = _safe(c, kind, name)
    if w and 32 <= w <= 2048:
        data = _thumb(str(p), int(p.stat().st_mtime), int(w))
        if data:
            return Response(data, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=3600"})
    media = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    return FileResponse(p, media_type=media, headers={"Cache-Control": "public, max-age=3600"})


# ---- export ------------------------------------------------------------------
TABLE_FRAME = {"readings": "env", "soil": "soil", "pump_log": "pump", "growth": "grow"}
TABLE_FAKE = {"readings": "env", "soil": "soil", "pump_log": "pump", "growth": "growth"}


@router.get("/export/{table}.csv")
def export_csv(table: str, c=Depends(ctx), dummy: str | None = None):
    if table not in TABLE_FRAME:
        raise ApiError(404, "bad_table", f"table must be one of {list(TABLE_FRAME)}")
    fr = c.frames(dummy)
    df = getattr(fr, TABLE_FRAME[table])
    is_fake = TABLE_FAKE[table] in fr.fake
    buf = io.StringIO()
    df.to_csv(buf, index=False, date_format="%Y-%m-%d %H:%M:%S")
    buf.seek(0)
    fname = f"{table}{'.dummy' if is_fake else ''}.csv"
    headers = {"Content-Disposition": f'attachment; filename="{fname}"'}
    if is_fake:
        headers["X-Plant-Dummy"] = "1"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers=headers)
