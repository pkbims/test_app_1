"""The PRD §17 "when things break" table, each row with a test (build step 14).

Rows covered elsewhere:
- image model errors → retry then fail + refund  → test_render_flow
- worker dies mid-job → requeue after lease      → test_worker::test_expired_lease_is_reclaimed
- queue depth → health degraded                  → test_health::test_check_queue_depth_*
"""

from __future__ import annotations

import io

import psycopg
import pytest
from PIL import Image

from .conftest import sign_in

pytestmark = pytest.mark.integration


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), (160, 150, 140)).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def api_no_vision(pg_url, tmp_path, monkeypatch):
    """Same app, but with no vision backend configured at all → DisabledVision."""
    monkeypatch.setenv("DATABASE_URL", pg_url)
    monkeypatch.setenv("PHOTO_DIR", str(tmp_path))
    monkeypatch.setenv("JWT_SECRET", "failure-tests-signing-secret-32byte")
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("APPLE_CLIENT_ID", "")
    monkeypatch.setenv("VISION_BACKEND", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        yield client


def test_vision_unavailable_refuses_never_falls_back(api_no_vision):
    import jwt

    token = jwt.encode({"sub": "nv.user"}, "failure-tests-signing-secret-32byte", algorithm="HS256")
    headers = {
        "Authorization": "Bearer "
        + api_no_vision.post("/v1/auth/apple", json={"identity_token": token}).json()[
            "access_token"
        ]
    }
    room_id = api_no_vision.post("/v1/rooms", json={}, headers=headers).json()["room_id"]
    api_no_vision.post(
        f"/v1/rooms/{room_id}/photos",
        files={"file": ("r.jpg", _jpeg(), "image/jpeg")},
        headers=headers,
    )

    inv = api_no_vision.post(f"/v1/rooms/{room_id}/inventory", headers=headers)
    assert inv.status_code == 500
    assert inv.json()["code"] == "inventory_failed"

    # and with no inventory, a render is refused — not generated unconstrained
    r = api_no_vision.post(
        f"/v1/rooms/{room_id}/renders",
        json={"style": "warm-minimal", "remove_ids": [], "idempotency_key": "k"},
        headers=headers,
    )
    assert r.status_code == 400
    assert r.json()["code"] == "no_inventory"


def test_database_down_is_503_everywhere_not_500(api):
    from app import runtime

    headers = sign_in(api)
    pool = runtime.get().pool

    def _down(*_a, **_k):
        raise psycopg.OperationalError("connection refused")

    original = pool.connection
    pool.connection = _down  # type: ignore[method-assign]
    try:
        me = api.get("/v1/me", headers=headers)
        assert me.status_code == 503
        assert me.headers.get("Retry-After") == "5"

        health = api.get("/health")
        assert health.status_code == 503
        assert health.json()["state"] == "down"
    finally:
        pool.connection = original  # type: ignore[method-assign]


def test_storage_failure_during_render_retries_then_refunds(api, run_worker, tmp_path):
    headers = sign_in(api)
    room_id = api.post("/v1/rooms", json={}, headers=headers).json()["room_id"]
    api.post(
        f"/v1/rooms/{room_id}/photos",
        files={"file": ("r.jpg", _jpeg(), "image/jpeg")},
        headers=headers,
    )
    api.post(f"/v1/rooms/{room_id}/inventory", headers=headers)
    render_id = api.post(
        f"/v1/rooms/{room_id}/renders",
        json={"style": "s", "remove_ids": [], "idempotency_key": "sf"},
        headers=headers,
    ).json()["render_id"]

    from app.storage import LocalDiskStorage

    class BrokenPut(LocalDiskStorage):
        def put(self, *a, **k):
            raise OSError("no space left on device")

    broken = BrokenPut(tmp_path)  # same photo dir as the api fixture and run_worker
    assert run_worker(storage=broken) == "retry"
    assert run_worker(storage=broken) == "retry"
    assert run_worker(storage=broken) == "failed"

    polled = api.get(f"/v1/renders/{render_id}", headers=headers).json()
    assert polled["status"] == "failed" and polled["error_code"] == "render_failed"
    assert api.get("/v1/me", headers=headers).json()["credits_left"] == 1
