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

    # health thresholds (PRD §17)
    queue_depth_degraded: int = 100
    worker_heartbeat_timeout_s: int = 60


def load() -> Settings:
    jwt_secret = os.environ.get("JWT_SECRET", "dev-insecure")
    app_env = os.environ.get("APP_ENV", "dev")
    if app_env == "production" and len(jwt_secret) < 32:
        raise RuntimeError("JWT_SECRET must be at least 32 bytes in production")
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
        worker_heartbeat_timeout_s=int(os.environ.get("WORKER_HEARTBEAT_TIMEOUT_S", "60")),
    )
