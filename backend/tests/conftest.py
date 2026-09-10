from __future__ import annotations

import os

import pytest

TEST_JWT_SECRET = "integration-test-signing-secret-32b"


@pytest.fixture
def api(pg_url, tmp_path, monkeypatch):
    """The real ASGI app wired to a scratch database and a temp photo dir.

    APPLE_CLIENT_ID is unset, so the dev token path stands in for Apple.
    """
    monkeypatch.setenv("DATABASE_URL", pg_url)
    monkeypatch.setenv("PHOTO_DIR", str(tmp_path))
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("APPLE_CLIENT_ID", "")
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://testserver")
    monkeypatch.setenv("VISION_BACKEND", "fake")
    # Pin explicitly — a dev .env may set SIGNUP_FREE_CREDITS for local manual
    # testing; the test suite must not inherit that.
    monkeypatch.setenv("SIGNUP_FREE_CREDITS", "1")

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def run_worker(pg_url, tmp_path):
    """Run one worker tick against the same scratch DB and photo dir as `api`.

    `catch_up=True` first makes any backed-off job due, so tests don't wait out
    the real retry backoff.
    """
    import psycopg

    from app.imagegen import FakeImageEditor
    from app.storage import LocalDiskStorage
    from app.vision import FakeVision
    from worker.runner import run_one

    def _tick(*, editor=None, vision=None, storage=None, catch_up=True, worker="test-worker"):
        with psycopg.connect(pg_url, autocommit=True) as conn:
            if catch_up:
                conn.execute("UPDATE jobs SET run_after = now() WHERE status = 'queued'")
            return run_one(
                conn,
                storage or LocalDiskStorage(tmp_path),
                vision or FakeVision(),
                editor or FakeImageEditor(),
                worker,
            )

    return _tick


def sign_in(client, sub: str = "000111.aaa.222") -> dict[str, str]:
    """Sign in via the dev token path; return an Authorization header dict."""
    import jwt

    token = jwt.encode({"sub": sub}, TEST_JWT_SECRET, algorithm="HS256")
    resp = client.post("/v1/auth/apple", json={"identity_token": token})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set — integration test needs a real Postgres")
    return url


@pytest.fixture
def pg_url(database_url: str):
    """A freshly created scratch database, dropped afterwards.

    Integration tests get their own database so migrations and fixtures never
    collide with the dev data in `app1`.
    """
    import psycopg

    admin = psycopg.connect(database_url, autocommit=True)
    scratch = f"app1_test_{os.getpid()}"
    admin.execute(f'DROP DATABASE IF EXISTS "{scratch}"')
    admin.execute(f'CREATE DATABASE "{scratch}"')
    try:
        yield _swap_db(database_url, scratch)
    finally:
        admin.execute(f'DROP DATABASE IF EXISTS "{scratch}"')
        admin.close()


@pytest.fixture
def pg_conn(pg_url: str):
    import psycopg

    conn = psycopg.connect(pg_url)
    try:
        yield conn
    finally:
        conn.close()


def _swap_db(url: str, name: str) -> str:
    head, _, _tail = url.rpartition("/")
    return f"{head}/{name}"
