"""The exact prompt text sent to each OpenAI call is persisted for review.

DB-only — not part of the contract, not returned by any route. Checked by
querying Postgres directly, the same way you'd inspect it by hand.
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
    Image.new("RGB", (900, 700), (180, 170, 160)).save(buf, format="JPEG")
    return buf.getvalue()


def test_inventory_prompt_is_stored(api, pg_url):
    headers = sign_in(api)
    room_id = api.post("/v1/rooms", json={}, headers=headers).json()["room_id"]
    api.post(
        f"/v1/rooms/{room_id}/photos",
        files={"file": ("r.jpg", _jpeg(), "image/jpeg")},
        headers=headers,
    )
    api.post(f"/v1/rooms/{room_id}/inventory", headers=headers)

    with psycopg.connect(pg_url) as conn:
        prompt = conn.execute(
            "SELECT prompt FROM inventories WHERE room_id = %s", (room_id,)
        ).fetchone()[0]

    assert prompt is not None
    assert "Inventory this room photo" in prompt
    assert "Label them A, B, C in reading order" in prompt


def test_render_prompts_are_stored(api, run_worker, pg_url):
    headers = sign_in(api)
    room_id = api.post("/v1/rooms", json={}, headers=headers).json()["room_id"]
    api.post(
        f"/v1/rooms/{room_id}/photos",
        files={"file": ("r.jpg", _jpeg(), "image/jpeg")},
        headers=headers,
    )
    inv = api.post(f"/v1/rooms/{room_id}/inventory", headers=headers).json()
    removable = [i["id"] for i in inv["items"] if i["removable"]]

    render_id = api.post(
        f"/v1/rooms/{room_id}/renders",
        json={
            "style": "warm-minimal",
            "prompt": "keep it cosy",
            "remove_ids": removable[:1],
            "idempotency_key": "prompt-storage-1",
        },
        headers=headers,
    ).json()["render_id"]
    assert run_worker() == "done"

    with psycopg.connect(pg_url) as conn:
        generation_prompt, preservation_prompt = conn.execute(
            "SELECT generation_prompt, preservation_prompt FROM renders WHERE id = %s",
            (render_id,),
        ).fetchone()

    # the exact text sent to gpt-image-2
    assert "THE STYLE THE CUSTOMER CHOSE — Warm minimal:" in generation_prompt
    assert "The customer also asked for: keep it cosy" in generation_prompt
    assert "MUST REMAIN EXACTLY WHERE THEY ARE" in generation_prompt
    assert "NOT IN THE ROOM" in generation_prompt

    # the exact text sent to the preservation check
    architecture_ids = [i["id"] for i in inv["items"] if i["kind"] == "architecture"]
    assert preservation_prompt is not None
    for item_id in architecture_ids:
        assert f"{item_id}:" in preservation_prompt


def test_deleting_a_room_deletes_the_stored_prompts_too(api, run_worker, pg_url):
    headers = sign_in(api)
    room_id = api.post("/v1/rooms", json={}, headers=headers).json()["room_id"]
    api.post(
        f"/v1/rooms/{room_id}/photos",
        files={"file": ("r.jpg", _jpeg(), "image/jpeg")},
        headers=headers,
    )
    api.post(f"/v1/rooms/{room_id}/inventory", headers=headers)
    api.post(
        f"/v1/rooms/{room_id}/renders",
        json={"style": "s", "remove_ids": [], "idempotency_key": "prompt-storage-2"},
        headers=headers,
    )
    run_worker()

    assert api.delete(f"/v1/rooms/{room_id}", headers=headers).status_code == 204

    with psycopg.connect(pg_url) as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM inventories WHERE room_id = %s", (room_id,)
            ).fetchone()[0]
            == 0
        )
        assert (
            conn.execute("SELECT count(*) FROM renders WHERE room_id = %s", (room_id,)).fetchone()[
                0
            ]
            == 0
        )
