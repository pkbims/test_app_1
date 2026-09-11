"""The options round's plumbing (options_review/HANDOFF.md §3): the seven new
`RenderCreate` fields are stored, echoed on `Render`, validated, and the room
type resolution chain (request -> detected -> null) works. Prompt-text effects
of each option are covered in test_render_prompt.py; this file is about the
contract-facing behaviour around them.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from .conftest import sign_in

pytestmark = pytest.mark.integration


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1024, 768), (190, 175, 165)).save(buf, format="JPEG")
    return buf.getvalue()


def _ready_room(api, headers) -> str:
    room_id = api.post("/v1/rooms", json={"label": "Lounge"}, headers=headers).json()["room_id"]
    api.post(
        f"/v1/rooms/{room_id}/photos",
        files={"file": ("r.jpg", _jpeg(), "image/jpeg")},
        headers=headers,
    )
    api.post(f"/v1/rooms/{room_id}/inventory", headers=headers)
    return room_id


def _submit(api, headers, room_id, **overrides):
    body = {"style": "warm-minimal", "remove_ids": [], "idempotency_key": "opt-1"}
    body.update(overrides)
    return api.post(f"/v1/rooms/{room_id}/renders", json=body, headers=headers)


def test_defaults_match_the_contract_when_the_client_sends_nothing(api):
    headers = sign_in(api)
    room_id = _ready_room(api, headers)
    r = _submit(api, headers, room_id)
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["room_type"] == "living_room"  # FakeVision's fixed detection
    assert body["walls"] == "leave"
    assert body["furniture"] == "keep_only"
    assert body["add_furniture"] == []
    assert body["decor"] == "as_style"
    assert body["plants"] is False
    assert body["palette"] == "as_style"


def test_request_room_type_overrides_the_detected_one(api):
    headers = sign_in(api)
    room_id = _ready_room(api, headers)
    r = _submit(api, headers, room_id, room_type="bedroom")
    assert r.json()["room_type"] == "bedroom"


def test_all_options_round_trip(api):
    headers = sign_in(api)
    room_id = _ready_room(api, headers)
    r = _submit(
        api,
        headers,
        room_id,
        walls="repaint",
        furniture="add",
        add_furniture=["sofa", "coffee_table"],  # valid for the detected living_room
        decor="plenty",
        plants=True,
        palette="warm",
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["walls"] == "repaint"
    assert body["furniture"] == "add"
    assert body["add_furniture"] == ["sofa", "coffee_table"]
    assert body["decor"] == "plenty"
    assert body["plants"] is True
    assert body["palette"] == "warm"


def test_room_type_falls_back_to_null_when_nothing_is_known(api, pg_conn):
    headers = sign_in(api)
    room_id = _ready_room(api, headers)
    pg_conn.execute("UPDATE inventories SET room_type = NULL WHERE room_id = %s", (room_id,))
    pg_conn.commit()
    r = _submit(api, headers, room_id)
    assert r.json()["room_type"] is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("walls", "sideways"),
        ("furniture", "summon"),
        ("decor", "extravagant"),
        ("palette", "rainbow"),
        ("room_type", "garage"),
    ],
)
def test_out_of_set_values_are_422(api, field, value):
    headers = sign_in(api)
    room_id = _ready_room(api, headers)
    r = _submit(api, headers, room_id, **{field: value})
    assert r.status_code == 422, r.text


def test_add_furniture_rejects_an_id_not_in_any_list(api):
    headers = sign_in(api)
    room_id = _ready_room(api, headers)
    r = _submit(api, headers, room_id, furniture="add", add_furniture=["banana"])
    assert r.status_code == 422


def test_add_furniture_rejects_an_id_from_a_different_room_types_list(api):
    headers = sign_in(api)
    room_id = _ready_room(api, headers)  # detected as living_room
    r = _submit(api, headers, room_id, furniture="add", add_furniture=["cot"])  # nursery-only
    assert r.status_code == 422


def test_add_furniture_is_validated_even_when_furniture_is_keep_only(api):
    headers = sign_in(api)
    room_id = _ready_room(api, headers)
    r = _submit(api, headers, room_id, furniture="keep_only", add_furniture=["banana"])
    assert r.status_code == 422


def test_add_furniture_valid_for_the_room_type_is_accepted(api):
    headers = sign_in(api)
    room_id = _ready_room(api, headers)  # living_room
    r = _submit(api, headers, room_id, furniture="add", add_furniture=["sofa", "armchair"])
    assert r.status_code == 202, r.text


def test_add_furniture_rejected_when_room_type_cannot_be_resolved(api, pg_conn):
    headers = sign_in(api)
    room_id = _ready_room(api, headers)
    pg_conn.execute("UPDATE inventories SET room_type = NULL WHERE room_id = %s", (room_id,))
    pg_conn.commit()
    r = _submit(api, headers, room_id, furniture="add", add_furniture=["sofa"])
    assert r.status_code == 422


def test_add_furniture_over_eight_is_422(api):
    headers = sign_in(api)
    room_id = _ready_room(api, headers)
    r = _submit(api, headers, room_id, furniture="add", add_furniture=["sofa"] * 9)
    assert r.status_code == 422
