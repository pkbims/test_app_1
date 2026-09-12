"""Configuration, read once from the environment.

Everything the system needs to run is an env var, so the same image behaves
differently in dev, staging and production with no code change (PRD §17).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    photo_dir: str
    jwt_secret: str
    app_env: str = "dev"
    log_level: str = "info"

    # auth token lifetimes
    access_ttl_s: int = 15 * 60
    refresh_ttl_s: int = 30 * 24 * 60 * 60

    # external services
    openai_api_key: str = ""
    apple_client_id: str = ""
    sentry_dsn: str = ""
    # "openai" (real gpt-4.1 / gpt-image-2) or "fake" (deterministic, for local
    # compose without a key and for integration tests)
    vision_backend: str = "openai"

    # signed read URLs for photos / render images (ORCH-QUESTIONS Q1)
    public_base_url: str = "http://localhost:8000"
    file_url_secret: str = ""  # falls back to jwt_secret in load()
    file_url_ttl_s: int = 24 * 60 * 60

    # limits
    max_photo_bytes: int = 12 * 1024 * 1024

    # Credits granted on first sign-in (PRD: one free room). Overridable via
    # SIGNUP_FREE_CREDITS for local testing only — the committed default stays 1;
    # never set this in compose.env.
    signup_free_credits: int = 1

    # health thresholds (PRD §17)
    queue_depth_degraded: int = 100
    worker_heartbeat_timeout_s: int = 60

    # "shop your restyle" (post-v1, shopping_proto/HANDOFF.md §4.2)
    searchapi_key: str = ""  # secret, .env only, never logged
    # "openai_searchapi" (real), "fake" (deterministic two-item result, for local
    # compose and integration tests), or "off" (writes `none`, calls nothing)
    shopping_backend: str = "openai_searchapi"
    shopping_max_items: int = 7
    shopping_judge_model: str = "gpt-4.1"
    shopping_describe_model: str = "gpt-4.1-mini"
    # The render leaves our system for this call (SearchApi/Google fetch it) —
    # shortest expiry that survives one job, never the long-lived client-facing
    # after_url (shopping_proto/HANDOFF.md §6.3).
    shopping_search_url_ttl_s: int = 15 * 60

    # ── TEMPORARY, dev-only (ORCH-QUESTIONS Q11, HANDOFF §7.3) ──────────────────
    # A laptop's PUBLIC_BASE_URL is not reachable by SearchApi, so real prices
    # never come back on local runs. Setting this to "catbox" makes the shopping
    # pipeline upload the render to catbox.moe (a public host we do not control)
    # and hand SearchApi *that* URL instead of our own signed one. Empty string
    # (the default) is the only value load() allows in production — see the
    # guard below. Delete this field, its Settings.load() wiring, its
    # ShoppingConfig field, and pipeline.py's `_upload_to_catbox` once every
    # developer has a tunnel set up; it should never outlive that.
    shopping_dev_image_host: str = ""


def load() -> Settings:
    jwt_secret = os.environ.get("JWT_SECRET", "dev-insecure")
    app_env = os.environ.get("APP_ENV", "dev")
    if app_env == "production" and len(jwt_secret) < 32:
        raise RuntimeError("JWT_SECRET must be at least 32 bytes in production")
    shopping_dev_image_host = os.environ.get("SHOPPING_DEV_IMAGE_HOST", "")
    if app_env == "production" and shopping_dev_image_host:
        # TEMPORARY dev-only escape hatch (ORCH-QUESTIONS Q11) — never in
        # production: no deletion guarantee on the upload host, no terms
        # agreed, and it breaks the TR4 promise (the render would leave the
        # system to a host we do not control, indefinitely retained).
        raise RuntimeError("SHOPPING_DEV_IMAGE_HOST must not be set when APP_ENV=production")
    return Settings(
        database_url=os.environ.get("DATABASE_URL", "postgresql://app1:app1@db:5432/app1"),
        photo_dir=os.environ.get("PHOTO_DIR", "/data/photos"),
        jwt_secret=jwt_secret,
        app_env=app_env,
        log_level=os.environ.get("LOG_LEVEL", "info"),
        openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
        apple_client_id=os.environ.get("APPLE_CLIENT_ID", ""),
        sentry_dsn=os.environ.get("SENTRY_DSN", ""),
        vision_backend=os.environ.get("VISION_BACKEND", "openai"),
        public_base_url=os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000"),
        file_url_secret=os.environ.get("FILE_URL_SECRET", "") or jwt_secret,
        queue_depth_degraded=int(os.environ.get("QUEUE_DEPTH_DEGRADED", "100")),
        signup_free_credits=int(os.environ.get("SIGNUP_FREE_CREDITS", "1")),
        worker_heartbeat_timeout_s=int(os.environ.get("WORKER_HEARTBEAT_TIMEOUT_S", "60")),
        searchapi_key=os.environ.get("SEARCHAPI_KEY", ""),
        shopping_backend=os.environ.get("SHOPPING_BACKEND", "openai_searchapi"),
        shopping_max_items=int(os.environ.get("SHOPPING_MAX_ITEMS", "7")),
        shopping_judge_model=os.environ.get("SHOPPING_JUDGE_MODEL", "gpt-4.1"),
        shopping_describe_model=os.environ.get("SHOPPING_DESCRIBE_MODEL", "gpt-4.1-mini"),
        shopping_dev_image_host=shopping_dev_image_host,
    )
