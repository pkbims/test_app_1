"""Process-wide handles (pool, storage, settings, ...), set up once at startup.

The frozen route signatures in `main.py` take no dependency parameters, so the
route bodies reach shared resources through this module rather than through
FastAPI's `Depends`. Keeping it in one place means tests can swap it out.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from jwt import PyJWKClient
from psycopg_pool import ConnectionPool

from .auth.apple import APPLE_JWKS_URL, AppleIdentity, verify_dev_token, verify_identity_token
from .db import make_pool
from .migrate import apply_all
from .ratelimit import InProcessRateLimiter, RateLimiter
from .settings import Settings, load
from .storage import LocalDiskStorage, Storage

AppleVerifier = Callable[[str], AppleIdentity]


@dataclass
class Runtime:
    settings: Settings
    pool: ConnectionPool
    storage: Storage
    rate_limiter: RateLimiter
    apple_verifier: AppleVerifier


_rt: Runtime | None = None


def get() -> Runtime:
    if _rt is None:
        raise RuntimeError("runtime not started")
    return _rt


def start(settings: Settings | None = None) -> Runtime:
    global _rt
    settings = settings or load()
    pool = make_pool(settings)
    with pool.connection() as conn:
        apply_all(conn)
    _rt = Runtime(
        settings=settings,
        pool=pool,
        storage=LocalDiskStorage(settings.photo_dir),
        rate_limiter=InProcessRateLimiter(),
        apple_verifier=make_apple_verifier(settings),
    )
    return _rt


def stop() -> None:
    global _rt
    if _rt is not None:
        _rt.pool.close()
        _rt = None


def make_apple_verifier(settings: Settings) -> AppleVerifier:
    if settings.apple_client_id:
        jwks = PyJWKClient(APPLE_JWKS_URL)
        return lambda token: verify_identity_token(
            token, client_id=settings.apple_client_id, jwk_client=jwks
        )
    if settings.app_env == "production":
        raise RuntimeError("APPLE_CLIENT_ID must be set when APP_ENV=production")
    return lambda token: verify_dev_token(token, secret=settings.jwt_secret)
