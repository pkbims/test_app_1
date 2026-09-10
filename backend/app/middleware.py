"""One ASGI middleware: request context + auth enforcement.

- Every request gets a request id (from `X-Request-Id` if the caller sent one, so
  it can be traced from the app through the API into the worker) and the caller's
  IP resolved once.
- Every `/v1/*` path except `/v1/auth/*` requires a valid access token. A missing
  or bad token is a `401` with an `Error` body — `token_expired` if it was ours
  but aged out, `apple_token_invalid` otherwise (per ORCH-QUESTIONS Q3).

Auth is enforced here rather than per-route because the frozen route signatures
have no place to hang a dependency.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from . import context
from .auth.tokens import TokenError, TokenExpired, decode_access
from .schemas import Error, ErrorCode

_OPEN_PREFIXES = ("/v1/auth/",)
_REQUEST_ID_HEADER = b"x-request-id"


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
        try:
            denied = self._check_auth(scope["path"], headers, ctx)
            if denied is not None:
                await _send_error(send, denied, request_id)
                return
            await self.app(scope, receive, _with_request_id(send, request_id))
        finally:
            context.reset(token)

    def _check_auth(
        self, path: str, headers: dict[bytes, bytes], ctx: context.RequestContext
    ) -> tuple[int, Error] | None:
        if not path.startswith("/v1/") or path.startswith(_OPEN_PREFIXES):
            return None
        raw = headers.get(b"authorization", b"").decode()
        scheme, _, value = raw.partition(" ")
        if scheme.lower() != "bearer" or not value:
            return 401, Error(code=ErrorCode.apple_token_invalid, message="Please sign in.")
        try:
            claims = decode_access(value, self._secret_provider())
        except TokenExpired:
            return 401, Error(code=ErrorCode.token_expired, message="Your session expired.")
        except TokenError:
            return 401, Error(code=ErrorCode.apple_token_invalid, message="Please sign in again.")
        ctx.user_id = claims.user_id
        return None


def _client_ip(scope: Scope, headers: dict[bytes, bytes]) -> str:
    # We terminate TLS at a single reverse proxy in every environment, so the
    # first hop in X-Forwarded-For is the real client. No proxy → the socket peer.
    xff = headers.get(b"x-forwarded-for")
    if xff:
        return xff.decode().split(",")[0].strip()
    client = scope.get("client")
    return client[0] if client else "unknown"


def _with_request_id(send: Send, request_id: str) -> Send:
    async def wrapped(message: Message) -> None:
        if message["type"] == "http.response.start":
            headers = message.setdefault("headers", [])
            headers.append((_REQUEST_ID_HEADER, request_id.encode()))
        await send(message)

    return wrapped


async def _send_error(send: Send, denied: tuple[int, Error], request_id: str) -> None:
    status, error = denied
    body = error.model_dump_json().encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (_REQUEST_ID_HEADER, request_id.encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
