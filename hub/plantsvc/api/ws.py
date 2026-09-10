"""/ws - live events (env/soil/pump/growth from MQTT, capture progress, LED, camera, config)."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .. import __version__
from ..timeutil import iso_utc, now_utc

router = APIRouter()


@router.websocket("/ws")
async def ws(websocket: WebSocket):
    ctx = websocket.app.state.ctx
    await websocket.accept()
    q = ctx.hub.subscribe()
    try:
        fr = ctx.frames()
        await websocket.send_text(ctx.hub.envelope("hello", {"server_time": iso_utc(now_utc()), "version": __version__,
                                                             "dummy": fr.dummy, "mqtt": ctx.bridge.status() if ctx.bridge else None}))
        recv = asyncio.ensure_future(websocket.receive_text())
        while True:
            get = asyncio.ensure_future(q.get())
            done, _ = await asyncio.wait({recv, get}, return_when=asyncio.FIRST_COMPLETED)
            if recv in done:
                try:
                    msg = recv.result()
                except WebSocketDisconnect:
                    get.cancel()
                    break
                try:
                    d = json.loads(msg)
                except ValueError:
                    d = {}
                if d.get("type") == "ping":
                    await websocket.send_text(ctx.hub.envelope("pong", {}))
                recv = asyncio.ensure_future(websocket.receive_text())
            if get in done:
                await websocket.send_text(get.result())
            else:
                get.cancel()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        ctx.hub.unsubscribe(q)
