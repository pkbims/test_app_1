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
from .imagegen import DisabledImageEditor, FakeImageEditor, ImageEditor, OpenAIImageEditor
from .migrate import apply_all
from .ratelimit import InProcessRateLimiter, RateLimiter
from .settings import Settings, load
from .shopping.judge import FakeShoppingModel, OpenAIShoppingModel, ShoppingModel
from .shopping.pipeline import ShoppingConfig
from .shopping.searchapi import FakeSearchApi, RealSearchApi, SearchApi
from .storage import LocalDiskStorage, Storage
from .vision import DisabledVision, FakeVision, OpenAIVision, Vision

AppleVerifier = Callable[[str], AppleIdentity]


@dataclass
class Runtime:
    settings: Settings
    pool: ConnectionPool
    storage: Storage
    rate_limiter: RateLimiter
    apple_verifier: AppleVerifier
    vision: Vision
    image_editor: ImageEditor


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
        vision=make_vision(settings),
        image_editor=make_image_editor(settings),
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


def make_vision(settings: Settings) -> Vision:
    if settings.vision_backend == "fake":
        return FakeVision()
    if settings.openai_api_key:
        return OpenAIVision(settings.openai_api_key)
    if settings.app_env == "production":
        raise RuntimeError("OPENAI_API_KEY must be set when APP_ENV=production")
    return DisabledVision()


def make_image_editor(settings: Settings) -> ImageEditor:
    if settings.vision_backend == "fake":
        return FakeImageEditor()
    if settings.openai_api_key:
        return OpenAIImageEditor(settings.openai_api_key)
    if settings.app_env == "production":
        raise RuntimeError("OPENAI_API_KEY must be set when APP_ENV=production")
    return DisabledImageEditor()


# ── shopping ("shop your restyle", post-v1) — worker-only, not part of Runtime;
# nothing in the API process runs the pipeline synchronously (shopping_proto/
# HANDOFF.md §4.2). `None` means "skip the pipeline, write `none`" — used for
# both SHOPPING_BACKEND=off and (outside production) a backend with no key
# configured, since a job that would only ever fail isn't worth retrying twice.
def make_shopping_model(settings: Settings) -> ShoppingModel | None:
    if settings.shopping_backend == "fake":
        return FakeShoppingModel()
    if settings.shopping_backend == "openai_searchapi" and settings.openai_api_key:
        return OpenAIShoppingModel(
            settings.openai_api_key,
            describe_model=settings.shopping_describe_model,
            judge_model=settings.shopping_judge_model,
        )
    if settings.app_env == "production" and settings.shopping_backend != "off":
        raise RuntimeError("OPENAI_API_KEY must be set when SHOPPING_BACKEND=openai_searchapi in production")
    return None


def make_shopping_searchapi(settings: Settings) -> SearchApi | None:
    if settings.shopping_backend == "fake":
        return FakeSearchApi()
    if settings.shopping_backend == "openai_searchapi" and settings.searchapi_key:
        return RealSearchApi(settings.searchapi_key)
    if settings.app_env == "production" and settings.shopping_backend != "off":
        raise RuntimeError("SEARCHAPI_KEY must be set when SHOPPING_BACKEND=openai_searchapi in production")
    return None


def make_shopping_config(settings: Settings) -> ShoppingConfig:
    return ShoppingConfig(
        max_items=settings.shopping_max_items,
        search_url_ttl_s=settings.shopping_search_url_ttl_s,
        public_base_url=settings.public_base_url,
        file_url_secret=settings.file_url_secret,
    )
