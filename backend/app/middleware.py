"""One ASGI middleware: request context, auth enforcement, metrics, access log.

- Every request gets a request id (from `X-Request-Id` if the caller sent one, so
  a render can be traced app → API → worker) and the caller's IP resolved once.
- Every `/v1/*` path except `/v1/auth/*` requires a valid access token. A missing
  or bad token is a `401` with an `Error` body — `token_expired` if it was ours
  but aged out, `apple_token_invalid` otherwise (ORCH-QUESTIONS Q3).
- One structured log line per request, and the Prometheus HTTP counters/histogram.

Auth is enforced here rather than per-route because the frozen route signatures
have no place to hang a dependency.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import Callable

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from . import context, metrics
from .auth.tokens import TokenError, TokenExpired, decode_access
from .schemas import Error, ErrorCode

_log = logging.getLogger("app1.access")
_OPEN_PREFIXES = ("/v1/auth/",)
_REQUEST_ID_HEADER = b"x-request-id"
# Collapse ids so the metric label set stays small.
_ID_SEGMENT = re.compile(
    r"/(?:[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    r"|[0-9a-fA-F]{16,})"
)


class RequestMiddleware:
    def __init__(self, app: ASGIApp, *, secret_provider: Callable[[], str]) -> None:
        self.app = app
        self._secret_provider = secret_provider

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        request_id = headers.get(_REQUEST_ID_HEADER, uuid.uuid4().hex.encode()).decode()
        ctx = context.RequestContext(
            request_id=request_id,
            client_ip=_client_ip(scope, headers),
            method=scope.get("method", ""),
            path=scope["path"],
        )
        token = context.set_current(ctx)
        started = time.perf_counter()
        status_code = 500

        async def sender(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message.setdefault("headers", []).append((_REQUEST_ID_HEADER, request_id.encode()))
            await send(message)

        try:
            denied = self._check_auth(scope["path"], headers, ctx)
            if denied is not None:
                status_code = denied[0]
                await _send_error(sender, denied, request_id)
            else:
                await self.app(scope, receive, sender)
        finally:
            elapsed = time.perf_counter() - started
            route = _route_label(scope["path"])
            _record(route, ctx, status_code, elapsed)
            context.reset(token)

    def _check_auth(
        self, path: str, headers: dict[bytes, bytes], ctx: context.RequestContext
    ) -> tuple[int, Error] | None:
        if not path.startswith("/v1/") or path.startswith(_OPEN_PREFIXES):
            return None
        raw = headers.get(b"authorization", b"").decode()
        scheme, _, value = raw.partition(" ")
        if scheme.lower() != "bearer" or not value:
            ctx.error_code = ErrorCode.apple_token_invalid.value
            return 401, Error(code=ErrorCode.apple_token_invalid, message="Please sign in.")
        try:
            claims = decode_access(value, self._secret_provider())
        except TokenExpired:
            ctx.error_code = ErrorCode.token_expired.value
            return 401, Error(code=ErrorCode.token_expired, message="Your session expired.")
        except TokenError:
            ctx.error_code = ErrorCode.apple_token_invalid.value
            return 401, Error(code=ErrorCode.apple_token_invalid, message="Please sign in again.")
        ctx.user_id = claims.user_id
        return None


def _record(route: str, ctx: context.RequestContext, status_code: int, elapsed: float) -> None:
    method = ctx.method or "-"
    metrics.HTTP_REQUESTS.labels(route, method, str(status_code)).inc()
    metrics.HTTP_DURATION.labels(route, method).observe(elapsed)
    _log.info(
        "request",
        extra={
            "request_id": ctx.request_id,
            "method": method,
            "route": route,
            "status": status_code,
            "duration_ms": round(elapsed * 1000, 1),
            "user_id": ctx.user_id,
            "error_code": ctx.error_code,
        },
    )


def _route_label(path: str) -> str:
    return _ID_SEGMENT.sub("/{id}", path)


def _client_ip(scope: Scope, headers: dict[bytes, bytes]) -> str:
    # We terminate TLS at a single reverse proxy in every environment, so the
    # first hop in X-Forwarded-For is the real client. No proxy → the socket peer.
    xff = headers.get(b"x-forwarded-for")
    if xff:
        return xff.decode().split(",")[0].strip()
    client = scope.get("client")
    return client[0] if client else "unknown"


async def _send_error(send: Send, denied: tuple[int, Error], request_id: str) -> None:
    # `send` here is the wrapper, which stamps the request-id header itself.
    status, error = denied
    body = error.model_dump_json().encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
