"""Camera setup: status, MJPEG preview, actions, calib, drift."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response, StreamingResponse

from ..camera.backends import CameraUnavailable
from ..camera.manager import CameraBusy
from ..camera.overlay import draw
from .deps import ApiError, ctx

router = APIRouter(prefix="/api/camera", tags=["camera"])


@router.get("/status")
def status(c=Depends(ctx)) -> dict[str, Any]:
    return c.setup.status()


def _overlay_fn(c):
    def fn(img):
        cfg = c.store.get()
        return draw(img, [r.model_dump() for r in cfg.rois], cfg.scale, c.setup.pts,
                    c.setup.ppc_fixed or cfg.qc.px_per_cm_ref)
    return fn


@router.get("/stream.mjpg")
def stream(c=Depends(ctx), overlay: int = 0):
    try:
        gen = c.camera.mjpeg(_overlay_fn(c) if overlay else None)
        first = next(gen)          # opens the camera now so errors become HTTP errors, not a dead stream
    except CameraBusy as e:
        raise ApiError(409, "camera_busy", str(e)) from e
    except CameraUnavailable as e:
        raise ApiError(503, "camera_unavailable", str(e)) from e
    except StopIteration as e:
        raise ApiError(503, "camera_unavailable", "no frames") from e

    def chain():
        yield first
        yield from gen
    return StreamingResponse(chain(), media_type="multipart/x-mixed-replace; boundary=FRAME",
                             headers={"Cache-Control": "no-store"})


@router.get("/frame.jpg")
async def frame(c=Depends(ctx), overlay: int = 0):
    try:
        jpg = await run_in_threadpool(c.camera.frame_jpeg, _overlay_fn(c) if overlay else None)
    except CameraBusy as e:
        raise ApiError(409, "camera_busy", str(e)) from e
    except CameraUnavailable as e:
        raise ApiError(503, "camera_unavailable", str(e)) from e
    return Response(jpg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.post("/actions/{name}")
async def action(name: str, c=Depends(ctx), body: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    try:
        return await run_in_threadpool(c.setup.run, name, body or {})
    except KeyError as e:
        raise ApiError(404, "unknown_action", f"no action {name!r}") from e
    except CameraBusy as e:
        raise ApiError(409, "camera_busy", str(e)) from e
    except CameraUnavailable as e:
        raise ApiError(503, "camera_unavailable", str(e)) from e


@router.post("/release")
def release(c=Depends(ctx)) -> dict[str, Any]:
    """Internal: an external capture process asks the service to let go of the camera."""
    if c.led.is_on:
        c.led.off(reason="release")
    return c.camera.release_for_capture("capture")


@router.get("/calib.jpg")
def calib(c=Depends(ctx)):
    p = c.paths.calib
    if not p.exists():
        raise ApiError(404, "no_calib", "calib.jpg has not been taken yet")
    return FileResponse(p, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.get("/calib/info")
def calib_info(c=Depends(ctx)) -> dict[str, Any]:
    p = c.paths.calib
    if not p.exists():
        return {"exists": False}
    st = p.stat()
    return {"exists": True, "size": st.st_size, "mtime": int(st.st_mtime)}


@router.get("/drift")
async def drift(c=Depends(ctx)) -> dict[str, Any]:
    return await run_in_threadpool(c.setup.drift)
