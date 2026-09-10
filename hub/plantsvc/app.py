"""FastAPI application factory.

    plantsvc serve            -> uvicorn on PLANT_HOST:PLANT_PORT (default 0.0.0.0:8080)
    create_app(settings, camera_backend=FakeBackend(), led_mode="noop", mqtt=False)   (tests)
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from . import __version__
from .api import camera as api_camera
from .api import capture as api_capture
from .api import config as api_config
from .api import dashboard as api_dashboard
from .api import images as api_images
from .api import system as api_system
from .api import ws as api_ws
from .context import AppContext, build_context
from .settings import Settings

FALLBACK_HTML = """<!doctype html><meta charset="utf-8"><title>plantsvc</title>
<body style="font-family:system-ui;padding:40px;color:#173046;background:#F2F2F2">
<h1>plantsvc {version}</h1>
<p>The API is running, but the web UI has not been built yet.</p>
<pre>cd web &amp;&amp; npm ci &amp;&amp; npm run build        # or: scripts/install.sh --web=release</pre>
<p><a href="/api/summary">/api/summary</a> · <a href="/api/system/status">/api/system/status</a> ·
<a href="/api/docs">/api/docs</a></p></body>"""


def create_app(settings: Settings | None = None, *, camera_backend=None, led_mode: str | None = None,
               mqtt: bool | None = None, context: AppContext | None = None) -> FastAPI:
    ctx = context or build_context(settings, camera_backend=camera_backend, led_mode=led_mode, mqtt=mqtt)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        ctx.hub.bind(asyncio.get_running_loop())
        ctx.led.force_off()
        if ctx.bridge is not None:
            ctx.bridge.start()
        try:
            yield
        finally:
            ctx.close()

    app = FastAPI(title="plantsvc", version=__version__, lifespan=lifespan,
                  docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
    app.state.ctx = ctx

    @app.exception_handler(HTTPException)
    async def _http_err(request: Request, exc: HTTPException):
        d = exc.detail
        if isinstance(d, dict) and "code" in d:
            body = {"error": d}
        else:
            body = {"error": {"code": "http_error", "message": str(d), "details": None}}
        return JSONResponse(body, status_code=exc.status_code)

    for r in (api_dashboard.router, api_dashboard.an, api_camera.router, api_capture.router,
              api_config.router, api_images.router, api_system.router, api_ws.router):
        app.include_router(r)

    dist: Path = ctx.paths.web_dist

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        if path.startswith("api/") or path == "ws":
            raise HTTPException(404, "not found")
        if dist.exists():
            target = (dist / path).resolve() if path else dist / "index.html"
            if path and target.is_relative_to(dist.resolve()) and target.is_file():
                return FileResponse(target)
            return FileResponse(dist / "index.html")
        return HTMLResponse(FALLBACK_HTML.format(version=__version__))

    return app
