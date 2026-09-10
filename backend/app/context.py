"""Per-request context, carried in a ContextVar.

The frozen route signatures take no `Request`, so anything a route body needs
about the current request — the request id, the caller's IP for rate limiting,
the authenticated user — is read from here. `RequestMiddleware` populates it.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

_current: ContextVar[RequestContext | None] = ContextVar("request_context", default=None)


@dataclass
class RequestContext:
    request_id: str
    client_ip: str
    method: str
    path: str
    user_id: str | None = None
    error_code: str | None = None  # set by the ApiError handler, read by the access log


def set_current(ctx: RequestContext):
    return _current.set(ctx)


def reset(token) -> None:
    _current.reset(token)


def current() -> RequestContext:
    ctx = _current.get()
    if ctx is None:
        raise RuntimeError("no request context — is RequestMiddleware installed?")
    return ctx


def current_or_none() -> RequestContext | None:
    return _current.get()
