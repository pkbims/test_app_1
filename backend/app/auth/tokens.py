"""Our own tokens.

- **Access token**: a short-lived (~15 min) HS256 JWT. Stateless — the API checks
  the signature and expiry, no database hit. Held in memory by the client.
- **Refresh token**: ~30 days, an opaque 256-bit random string. Stored server-side
  as a SHA-256 hash only. The client keeps the raw value in the Keychain.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass

import jwt

_ACCESS_TYPE = "access"
_ALG = "HS256"


@dataclass(frozen=True)
class AccessClaims:
    user_id: str
    expires_at: int


class TokenError(Exception):
    """The token is not one we issued, or it is malformed."""


class TokenExpired(TokenError):
    """The token parsed and verified, but its `exp` has passed."""


def issue_access(
    user_id: str, secret: str, ttl_s: int, *, now: int | None = None
) -> tuple[str, int]:
    """Return `(jwt, expires_in_seconds)`."""
    issued = now if now is not None else int(time.time())
    payload = {
        "sub": user_id,
        "iat": issued,
        "exp": issued + ttl_s,
        "type": _ACCESS_TYPE,
    }
    return jwt.encode(payload, secret, algorithm=_ALG), ttl_s


def decode_access(token: str, secret: str) -> AccessClaims:
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[_ALG],
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpired(str(exc)) from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError(str(exc)) from exc
    if payload.get("type") != _ACCESS_TYPE:
        raise TokenError("not an access token")
    return AccessClaims(user_id=str(payload["sub"]), expires_at=int(payload["exp"]))


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
