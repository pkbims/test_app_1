"""One exception type for every expected error, mapped to the contract's codes.

Route bodies raise `ApiError(ErrorCode.x, "message")`; a handler turns it into the
`Error` JSON body with the right status. The message is shown to the user verbatim
(contract), so keep it plain.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import context
from .schemas import Error, ErrorCode

_STATUS: dict[ErrorCode, int] = {
    ErrorCode.apple_token_invalid: 401,
    ErrorCode.token_expired: 401,
    ErrorCode.no_credits: 402,
    ErrorCode.rate_limited: 429,
    ErrorCode.photo_too_large: 413,
    ErrorCode.photo_unsupported: 400,
    ErrorCode.no_photos: 400,
    ErrorCode.no_inventory: 400,
    ErrorCode.inventory_failed: 500,
    ErrorCode.render_failed: 500,
    ErrorCode.not_found: 404,
}


class ApiError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        status: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status = status or _STATUS[code]
        self.headers = headers or {}
        super().__init__(message)

    def to_response(self) -> JSONResponse:
        return JSONResponse(
            status_code=self.status,
            content=Error(code=self.code, message=self.message).model_dump(mode="json"),
            headers=self.headers,
        )


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
        ctx = context.current_or_none()
        if ctx is not None:
            ctx.error_code = exc.code.value
        return exc.to_response()
