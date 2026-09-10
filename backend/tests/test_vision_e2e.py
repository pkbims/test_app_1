"""The one real-OpenAI run: a full render of a genuine room photo, end to end.

Sign in → room → photo → inventory (gpt-4.1) → render (gpt-image-2) → worker →
preservation check (gpt-4.1) → poll to done with a real preservation_rate.

Skipped unless OPENAI_API_KEY is set and the sample photo is mounted, so CI stays
green without a key (AGENT.md "Done looks like").
"""

from __future__ import annotations

import os
import pathlib
import re

import jwt
import psycopg
import pytest

pytestmark = pytest.mark.integration

_SAMPLE = pathlib.Path("/inputs/room.jpg")
_SECRET = "e2e-signing-secret-at-least-32-byte"


@pytest.fixture
def live(pg_url, tmp_path, monkeypatch):
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("no OPENAI_API_KEY")
    if not _SAMPLE.is_file():
        pytest.skip("sample photo /inputs/room.jpg not mounted")

    monkeypatch.setenv("DATABASE_URL", pg_url)
    monkeypatch.setenv("PHOTO_DIR", str(tmp_path))
    monkeypatch.setenv("JWT_SECRET", _SECRET)
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("APPLE_CLIENT_ID", "")
    monkeypatch.setenv("VISION_BACKEND", "openai")
    monkeypatch.setenv("SIGNUP_FREE_CREDITS", "1")

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        yield client, pg_url, tmp_path


def _run_worker(pg_url, tmp_path) -> str | None:
    from app.imagegen import OpenAIImageEditor
    from app.storage import LocalDiskStorage
    from app.vision import OpenAIVision
    from worker.runner import run_one

    key = os.environ["OPENAI_API_KEY"]
    with psycopg.connect(pg_url, autocommit=True) as conn:
        return run_one(
            conn,
            LocalDiskStorage(tmp_path),
            OpenAIVision(key),
            OpenAIImageEditor(key),
            "e2e-worker",
        )


def test_full_render_against_real_openai(live):
    client, pg_url, tmp_path = live
    token = jwt.encode({"sub": "e2e.user"}, _SECRET, algorithm="HS256")
    headers = {
        "Authorization": "Bearer "
        + client.post("/v1/auth/apple", json={"identity_token": token}).json()["access_token"]
    }

    room_id = client.post("/v1/rooms", json={"label": "Real room"}, headers=headers).json()[
        "room_id"
    ]
    client.post(
        f"/v1/rooms/{room_id}/photos",
        files={"file": ("room.jpg", _SAMPLE.read_bytes(), "image/jpeg")},
        headers=headers,
    )

    inv = client.post(f"/v1/rooms/{room_id}/inventory", headers=headers).json()
    assert len(inv["items"]) >= 5
    assert any(i["kind"] == "architecture" and not i["removable"] for i in inv["items"])
    assert all(re.fullmatch(r"[A-Z]{1,2}", i["id"]) for i in inv["items"])
    removable = [i["id"] for i in inv["items"] if i["removable"]]

    submit = client.post(
        f"/v1/rooms/{room_id}/renders",
        json={
            "style": "warm-minimal",
            "remove_ids": removable[:1],
            "idempotency_key": "e2e-1",
        },
        headers=headers,
    )
    assert submit.status_code == 202
    render_id = submit.json()["render_id"]

    assert _run_worker(pg_url, tmp_path) == "done"

    final = client.get(f"/v1/renders/{render_id}", headers=headers).json()
    assert final["status"] == "done"
    assert final["after_url"] and client.get(final["after_url"]).status_code == 200
    assert final["preservation_rate"] is not None
    assert 0.0 <= final["preservation_rate"] <= 1.0
