"""Signed read URLs for photos and render images (ORCH-QUESTIONS Q1).

The client is handed a full URL and just loads it; it never builds one. The URL
carries an expiry and an HMAC over `"{scope}/{key}:{exp}"`, so a link works for
24h and cannot be tampered into pointing at another object.

`key` is storage-relative (no `photos/` or `renders/` prefix — the scope is that
prefix). The bytes are served by the `include_in_schema=False` route in
`files_route.py`.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import urlencode

SCOPES = ("photos", "renders", "crops")


def _signature(scope: str, key: str, exp: int, secret: str) -> str:
    msg = f"{scope}/{key}:{exp}".encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def signed_url(
    base_url: str, scope: str, key: str, secret: str, ttl_s: int, *, now: int | None = None
) -> str:
    issued = now if now is not None else int(time.time())
    exp = issued + ttl_s
    query = urlencode({"exp": exp, "sig": _signature(scope, key, exp, secret)})
    return f"{base_url.rstrip('/')}/files/{scope}/{key}?{query}"


def verify(
    scope: str, key: str, exp: int, sig: str, secret: str, *, now: int | None = None
) -> bool:
    checked_at = now if now is not None else int(time.time())
    if scope not in SCOPES or exp < checked_at:
        return False
    return hmac.compare_digest(sig, _signature(scope, key, exp, secret))
