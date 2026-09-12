"""Settings.load() — just the pieces worth a direct test: env wiring and the
production safety guards (ORCH-QUESTIONS Q11's dev-only catbox escape hatch)."""

from __future__ import annotations

import pytest

from app.settings import load


def _base_env(monkeypatch, **overrides):
    env = {
        "DATABASE_URL": "postgresql://x/y",
        "PHOTO_DIR": "/tmp",
        "JWT_SECRET": "dev-insecure",
        "APP_ENV": "dev",
    }
    env.update(overrides)
    for key, value in env.items():
        monkeypatch.setenv(key, value)


def test_shopping_dev_image_host_defaults_to_empty(monkeypatch):
    _base_env(monkeypatch)
    monkeypatch.delenv("SHOPPING_DEV_IMAGE_HOST", raising=False)
    assert load().shopping_dev_image_host == ""


def test_shopping_dev_image_host_reads_from_env(monkeypatch):
    _base_env(monkeypatch)
    monkeypatch.setenv("SHOPPING_DEV_IMAGE_HOST", "catbox")
    assert load().shopping_dev_image_host == "catbox"


def test_shopping_dev_image_host_is_refused_in_production(monkeypatch):
    _base_env(
        monkeypatch,
        APP_ENV="production",
        JWT_SECRET="x" * 32,
        SHOPPING_DEV_IMAGE_HOST="catbox",
    )
    with pytest.raises(RuntimeError, match="SHOPPING_DEV_IMAGE_HOST"):
        load()


def test_production_without_the_dev_image_host_set_is_fine(monkeypatch):
    _base_env(monkeypatch, APP_ENV="production", JWT_SECRET="x" * 32)
    monkeypatch.delenv("SHOPPING_DEV_IMAGE_HOST", raising=False)
    assert load().shopping_dev_image_host == ""
