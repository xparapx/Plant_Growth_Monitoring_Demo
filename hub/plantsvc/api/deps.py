from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from ..context import AppContext


class ApiError(HTTPException):
    def __init__(self, status: int, code: str, message: str, details: Any = None):
        super().__init__(status_code=status, detail={"code": code, "message": message, "details": details})
        self.code = code


def ctx(request: Request) -> AppContext:
    return request.app.state.ctx


def base_meta(fr) -> dict[str, Any]:
    from ..timeutil import iso_utc
    return {"now": iso_utc(fr.now.to_pydatetime()) if fr.now is not None else None,
            "now_real": iso_utc(fr.now_real.to_pydatetime()) if fr.now_real is not None else None,
            "dummy": fr.dummy}
