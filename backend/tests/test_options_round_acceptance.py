"""The options round's render-level acceptance tests (options_review/HANDOFF.md
§4.9, §8 D10): one real render per option, on the known room, scored with
`preservation_check` — the tier a unit test on `build_prompt()` cannot cover,
same shape as `test_remove_bug_acceptance.py`.

Each test is independently attributable, per D10's recommendation ("so a
regression points at one line"), even though they share this file: a failure in
`test_palette_*` says something about the palette override clause specifically,
not about the options round in general.

Skipped unless OPENAI_API_KEY is set and the sample photo is mounted.
"""

from __future__ import annotations

import base64
import json
import os

import jwt
import psycopg
import pytest
from psycopg.types.json import Json

from .known_room import ITEMS, SAMPLE_PHOTO

pytestmark = pytest.mark.integration

_SECRET = "options-round-e2e-signing-secret-32by"
_MIN_PRESERVATION = 0.8  # 6 architecture items on the known room; allow one miss


@pytest.fixture
def live(pg_url, tmp_path, monkeypatch):
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("no OPENAI_API_KEY")
    if not SAMPLE_PHOTO.is_file():
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
            conn, LocalDiskStorage(tmp_path), OpenAIVision(key), OpenAIImageEditor(key),
            "options-round-e2e-worker",
        )


def _setup_room(client, pg_url, *, sub: str, room_type: str | None = "living_room") -> tuple[dict, str]:
    """Sign in, create a room with the known photo, and seed the known inventory
    directly (skips a second real vision call; deterministic)."""
    token = jwt.encode({"sub": sub}, _SECRET, algorithm="HS256")
    headers = {
        "Authorization": "Bearer "
        + client.post("/v1/auth/apple", json={"identity_token": token}).json()["access_token"]
    }
    room_id = client.post("/v1/rooms", json={"label": "Known room"}, headers=headers).json()["room_id"]
    client.post(
        f"/v1/rooms/{room_id}/photos",
        files={"file": ("room.jpg", SAMPLE_PHOTO.read_bytes(), "image/jpeg")},
        headers=headers,
    )
    with psycopg.connect(pg_url, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO inventories (room_id, items, room_type) VALUES (%s, %s, %s)",
            (room_id, Json(ITEMS), room_type),
        )
    return headers, room_id


def _vision_yes_no(image_bytes: bytes, question: str) -> bool:
    """A standalone real vision call for a one-off visual check — not
    `preservation_check`, which only ever asks about architecture."""
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=60.0, max_retries=1)
    data_uri = f"data:image/png;base64,{base64.b64encode(image_bytes).decode()}"
    resp = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": question + ' Return JSON only: {"answer": true|false}.'},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            }
        ],
        response_format={"type": "json_object"},
    )
    parsed = json.loads(resp.choices[0].message.content or "{}")
    return bool(parsed.get("answer"))


def _submit_and_run(client, pg_url, tmp_path, headers, room_id, key, **fields):
    body = {"style": "warm-minimal", "remove_ids": [], "idempotency_key": key, **fields}
    submit = client.post(f"/v1/rooms/{room_id}/renders", json=body, headers=headers)
    assert submit.status_code == 202, submit.text
    render_id = submit.json()["render_id"]
    assert _run_worker(pg_url, tmp_path) == "done"
    final = client.get(f"/v1/renders/{render_id}", headers=headers).json()
    assert final["status"] == "done"
    with psycopg.connect(pg_url) as conn:
        generation_prompt = conn.execute(
            "SELECT generation_prompt FROM renders WHERE id = %s", (render_id,)
        ).fetchone()[0]
    return final, generation_prompt


def test_room_type_appears_in_the_real_prompt_and_preserves(live):
    client, pg_url, tmp_path = live
    headers, room_id = _setup_room(client, pg_url, sub="opt.room_type")
    final, prompt = _submit_and_run(
        client, pg_url, tmp_path, headers, room_id, "opt-room-type-1",
    )
    assert "This is a living room." in prompt
    assert final["room_type"] == "living_room"
    assert final["preservation_rate"] >= _MIN_PRESERVATION


def test_walls_repaint_appears_in_the_real_prompt_and_preserves(live):
    client, pg_url, tmp_path = live
    headers, room_id = _setup_room(client, pg_url, sub="opt.walls")
    final, prompt = _submit_and_run(
        client, pg_url, tmp_path, headers, room_id, "opt-walls-1", walls="repaint",
    )
    assert "- You may change wall colour, textiles, rugs, and" in prompt
    assert final["walls"] == "repaint"
    assert final["preservation_rate"] >= _MIN_PRESERVATION


def test_furniture_add_appears_in_the_real_prompt_and_preserves(live):
    client, pg_url, tmp_path = live
    headers, room_id = _setup_room(client, pg_url, sub="opt.furniture")
    final, prompt = _submit_and_run(
        client, pg_url, tmp_path, headers, room_id, "opt-furniture-1",
        furniture="add", add_furniture=["side_table"],
    )
    assert "ADD TO THE ROOM" in prompt
    assert "- a side table" in prompt
    assert final["add_furniture"] == ["side_table"]
    assert final["preservation_rate"] >= _MIN_PRESERVATION


def test_decor_plenty_appears_in_the_real_prompt_and_preserves(live):
    client, pg_url, tmp_path = live
    headers, room_id = _setup_room(client, pg_url, sub="opt.decor")
    final, prompt = _submit_and_run(
        client, pg_url, tmp_path, headers, room_id, "opt-decor-1", decor="plenty",
    )
    assert "add decor generously" in prompt
    assert final["preservation_rate"] >= _MIN_PRESERVATION


def test_plants_appears_in_the_real_prompt_and_preserves(live):
    client, pg_url, tmp_path = live
    headers, room_id = _setup_room(client, pg_url, sub="opt.plants")
    final, prompt = _submit_and_run(
        client, pg_url, tmp_path, headers, room_id, "opt-plants-1", plants=True,
    )
    assert "- Add a few potted plants, placed where they would naturally sit." in prompt
    assert final["preservation_rate"] >= _MIN_PRESERVATION


def test_palette_override_moves_the_real_output_away_from_the_muted_style(live):
    """The spike HANDOFF §4.7 asks for: does the override clause actually change
    the visible output, or does the style guide's own (here, deliberately muted)
    palette win? `warm-minimal` explicitly avoids strong contrast and black
    (its own Avoid: line) — `bold` is the family furthest from that, so it is the
    best single real test of whether the override clause has any teeth."""
    client, pg_url, tmp_path = live
    headers, room_id = _setup_room(client, pg_url, sub="opt.palette")
    final, prompt = _submit_and_run(
        client, pg_url, tmp_path, headers, room_id, "opt-palette-1", palette="bold",
    )
    assert "Override the palette above: use strong, saturated colour" in prompt
    assert final["preservation_rate"] >= _MIN_PRESERVATION

    after_bytes = client.get(final["after_url"]).content
    assert _vision_yes_no(
        after_bytes,
        "Does this room contain strong, saturated / bold colour (not a muted, "
        "neutral or pastel palette)?",
    ), "the palette override did not visibly move the output — see ORCH-QUESTIONS Q8.3"
