"""The render-level acceptance test for the REMOVE bug fix (HANDOFF §4.3(b)).

A unit test on `build_prompt()` cannot see a TV. This renders a real photo with
gpt-image-2 and asks a real gpt-4.1 vision call whether the removed object is
actually gone from the output — the only thing that proves the fix worked.

Reuses the exact photo and inventory from the known-bad case in the handoff
(room `edae7f0b-d22e-4657-b683-7a647e884122`, which failed this four times before
the fix): `/inputs/room.jpg` (same file, verified by hash) and its recorded
inventory, inserted directly so this test does not spend a second vision call
re-deriving it and stays deterministic. Only the render + removal check are real
calls.

Skipped unless OPENAI_API_KEY is set and the sample photo is mounted, same as
`test_vision_e2e.py`. Not in the default CI lane.
"""

from __future__ import annotations

import base64
import json
import os
import pathlib

import jwt
import psycopg
import pytest
from psycopg.types.json import Json

pytestmark = pytest.mark.integration

_SAMPLE = pathlib.Path("/inputs/room.jpg")
_SECRET = "remove-bug-e2e-signing-secret-32byte"

# Recorded verbatim from the known-bad case's own inventory (HANDOFF §4.3(b)).
# Item L, "TV and stand", is the large unambiguous object marked for removal.
_KNOWN_BAD_ITEMS = [
    {"id": "A", "kind": "architecture", "name": "fireplace", "removable": False,
     "description": "Rectangular wooden mantel with grey tile inlay on the left side of the room, "
                     "partially in view."},
    {"id": "B", "kind": "architecture", "name": "mantel", "removable": False,
     "description": "Light wood shelf resting on top of the fireplace, extending horizontally "
                     "under decorative objects."},
    {"id": "C", "kind": "architecture", "name": "alcove", "removable": False,
     "description": "Recessed inset in wall to the left of center, above the mantel and fireplace, "
                     "providing a shallow nook."},
    {"id": "D", "kind": "architecture", "name": "wall with bulkhead", "removable": False,
     "description": "Main wall with a prominent horizontal bulkhead running across upper portion, "
                     "central to the image and surrounding television."},
    {"id": "E", "kind": "architecture", "name": "flooring", "removable": False,
     "description": "Wide plank, wood-look flooring covering the entire visible lower area of the "
                     "room."},
    {"id": "F", "kind": "architecture", "name": "light switches", "removable": False,
     "description": "Two white rectangular light switches, one below the bulkhead near the floor "
                     "lamp and another partially visible on the far right wall."},
    {"id": "G", "kind": "object", "name": "large wall clock", "removable": True,
     "description": "Round white clock with gold hands and tick marks, leaning on the mantel at "
                     "the left side of the alcove."},
    {"id": "H", "kind": "object", "name": "framed wedding photo", "removable": True,
     "description": "Square framed photo of a couple in ceremonial attire, resting against the "
                     "wall on the mantel to the right of the clock."},
    {"id": "I", "kind": "object", "name": "wooden plaque", "removable": True,
     "description": "Rectangular wooden plaque with engraved accents, placed on the mantel at the "
                     "far left."},
    {"id": "J", "kind": "object", "name": "decorative small box", "removable": True,
     "description": "Small square box with a shiny lid, on the mantel between the plaque and the "
                     "clock."},
    {"id": "K", "kind": "object", "name": "floor lamp", "removable": True,
     "description": "Tall tripod lamp with woven shade, turned on, standing to the right of the "
                     "alcove between the TV stand and the fireplace."},
    {"id": "L", "kind": "object", "name": "TV and stand", "removable": True,
     "description": "Large flat-screen TV on light wood stand with rattan-front cabinets, centered "
                     "along the main wall."},
    {"id": "M", "kind": "object", "name": "candles on TV stand", "removable": True,
     "description": "Multiple small candles in glass holders, grouped on top of the TV stand, "
                     "mostly to the left of the TV base."},
    {"id": "N", "kind": "object", "name": "framed photos on TV stand", "removable": True,
     "description": "Three small framed photographs in a row, placed in front of the central open "
                     "shelf of the TV stand."},
    {"id": "O", "kind": "object", "name": "assorted decor under TV stand", "removable": True,
     "description": "Assorted small decorative items including stones and keepsakes, placed on the "
                     "lower central shelf of the TV stand."},
    {"id": "P", "kind": "object", "name": "laundry basket", "removable": True,
     "description": "Tall cylindrical white woven laundry basket with light contents, on the floor "
                     "to the right of the TV stand near wall."},
]

_REMOVE_ID = "L"  # "TV and stand"


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
            "remove-bug-e2e-worker",
        )


def _is_object_present(image_bytes: bytes, name: str) -> bool:
    """A standalone real vision call — not `preservation_check`, which only ever
    asks about architecture. Asks plainly whether a named object is visible."""
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=60.0, max_retries=1)
    data_uri = f"data:image/png;base64,{base64.b64encode(image_bytes).decode()}"
    resp = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Is a {name!r} visible anywhere in this photo of a room? "
                            'Return JSON only: {"present": true} or {"present": false}.'
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            }
        ],
        response_format={"type": "json_object"},
    )
    parsed = json.loads(resp.choices[0].message.content or "{}")
    return bool(parsed.get("present"))


def test_a_removed_object_is_actually_gone_from_the_render(live):
    """HANDOFF §4.3(b): the one test that actually proves the REMOVE fix works.

    If this fails, the removal redesign (§4.2) has not worked — report it rather
    than shipping, per the handoff's explicit instruction.
    """
    client, pg_url, tmp_path = live
    token = jwt.encode({"sub": "remove-bug.e2e.user"}, _SECRET, algorithm="HS256")
    headers = {
        "Authorization": "Bearer "
        + client.post("/v1/auth/apple", json={"identity_token": token}).json()["access_token"]
    }

    room_id = client.post(
        "/v1/rooms", json={"label": "Known-bad removal case"}, headers=headers
    ).json()["room_id"]
    client.post(
        f"/v1/rooms/{room_id}/photos",
        files={"file": ("room.jpg", _SAMPLE.read_bytes(), "image/jpeg")},
        headers=headers,
    )

    # Reuse the known-bad case's own recorded inventory instead of a second real
    # vision call — deterministic, and it's the exact case that failed 4/4 times.
    with psycopg.connect(pg_url, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO inventories (room_id, items) VALUES (%s, %s)",
            (room_id, Json(_KNOWN_BAD_ITEMS)),
        )

    submit = client.post(
        f"/v1/rooms/{room_id}/renders",
        json={
            "style": "warm-minimal",
            "remove_ids": [_REMOVE_ID],
            "idempotency_key": "remove-bug-e2e-1",
        },
        headers=headers,
    )
    assert submit.status_code == 202, submit.text
    render_id = submit.json()["render_id"]

    assert _run_worker(pg_url, tmp_path) == "done"

    final = client.get(f"/v1/renders/{render_id}", headers=headers).json()
    assert final["status"] == "done"
    assert final["after_url"]
    after_bytes = client.get(final["after_url"]).content

    assert not _is_object_present(after_bytes, "TV and stand"), (
        "the TV and stand survived the render — the REMOVE fix (HANDOFF §4.2) did "
        "not work on the known-bad case; do not ship, treat §4.2 as a first "
        "hypothesis and try the levers in §4.3"
    )
