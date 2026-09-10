"""The one real OpenAI call: inventory a genuine room photo end to end.

Skipped unless OPENAI_API_KEY is set and the sample photo is present, so CI stays
green without a key (build-order "done looks like ..." / AGENT.md).
"""

from __future__ import annotations

import os
import pathlib
import re

import jwt
import pytest

pytestmark = pytest.mark.integration

_SAMPLE = pathlib.Path("/inputs/room.jpg")


@pytest.fixture
def live_api(pg_url, tmp_path, monkeypatch):
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("no OPENAI_API_KEY")
    if not _SAMPLE.is_file():
        pytest.skip("sample photo /inputs/room.jpg not mounted")

    monkeypatch.setenv("DATABASE_URL", pg_url)
    monkeypatch.setenv("PHOTO_DIR", str(tmp_path))
    monkeypatch.setenv("JWT_SECRET", "e2e-signing-secret-at-least-32-byte")
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("APPLE_CLIENT_ID", "")
    monkeypatch.setenv("VISION_BACKEND", "openai")

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        yield client


def test_real_inventory_of_a_real_room(live_api):
    token = jwt.encode(
        {"sub": "e2e.user"}, "e2e-signing-secret-at-least-32-byte", algorithm="HS256"
    )
    headers = {
        "Authorization": "Bearer "
        + live_api.post("/v1/auth/apple", json={"identity_token": token}).json()["access_token"]
    }
    room_id = live_api.post("/v1/rooms", json={"label": "Real room"}, headers=headers).json()[
        "room_id"
    ]
    live_api.post(
        f"/v1/rooms/{room_id}/photos",
        files={"file": ("room.jpg", _SAMPLE.read_bytes(), "image/jpeg")},
        headers=headers,
    )

    r = live_api.post(f"/v1/rooms/{room_id}/inventory", headers=headers)
    assert r.status_code == 200, r.text
    items = r.json()["items"]

    assert len(items) >= 5
    assert any(i["kind"] == "architecture" and not i["removable"] for i in items)
    assert any(i["kind"] == "object" and i["removable"] for i in items)
    assert all(re.fullmatch(r"[A-Z]{1,2}", i["id"]) for i in items)
    assert [i["id"] for i in items] == [i["id"] for i in r.json()["items"]]
