"""Renders end to end (build-order steps 6-7): submit, worker, poll, refund."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.imagegen import ImageEditError

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


def _submit(api, headers, room_id, key="idem-1", remove_ids=None):
    return api.post(
        f"/v1/rooms/{room_id}/renders",
        json={
            "style": "warm-minimal",
            "prompt": "keep it cosy",
            "remove_ids": remove_ids or [],
            "idempotency_key": key,
        },
        headers=headers,
    )


class BoomEditor:
    def edit(self, *_a):
        raise ImageEditError("image model exploded")


def test_submit_then_worker_completes_the_render(api, run_worker):
    headers = sign_in(api)
    room_id = _ready_room(api, headers)

    r = _submit(api, headers, room_id)
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "queued"
    assert body["credits_left"] == 0
    render_id = body["render_id"]

    assert run_worker() == "done"

    polled = api.get(f"/v1/renders/{render_id}", headers=headers).json()
    assert polled["status"] == "done"
    assert polled["preservation_rate"] == 1.0
    assert polled["missing_items"] == []
    assert polled["before_url"] and polled["after_url"]
    assert api.get(polled["after_url"]).status_code == 200
    assert api.get(polled["before_url"]).status_code == 200


def test_render_requires_an_inventory(api):
    headers = sign_in(api)
    room_id = api.post("/v1/rooms", json={}, headers=headers).json()["room_id"]
    api.post(
        f"/v1/rooms/{room_id}/photos",
        files={"file": ("r.jpg", _jpeg(), "image/jpeg")},
        headers=headers,
    )
    r = _submit(api, headers, room_id)
    assert r.status_code == 400
    assert r.json()["code"] == "no_inventory"


def test_second_render_is_out_of_credits(api, run_worker):
    headers = sign_in(api)
    room_id = _ready_room(api, headers)
    _submit(api, headers, room_id, key="a")
    run_worker()
    r = _submit(api, headers, room_id, key="b")
    assert r.status_code == 402
    assert r.json()["code"] == "no_credits"


def test_idempotent_replay_returns_the_same_render_and_does_not_recharge(api):
    headers = sign_in(api)
    room_id = _ready_room(api, headers)
    first = _submit(api, headers, room_id, key="same").json()
    second = _submit(api, headers, room_id, key="same").json()
    assert first["render_id"] == second["render_id"]
    assert api.get("/v1/me", headers=headers).json()["credits_left"] == 0


def test_failed_render_refunds_the_credit(api, run_worker):
    headers = sign_in(api)
    room_id = _ready_room(api, headers)
    render_id = _submit(api, headers, room_id).json()["render_id"]

    assert run_worker(editor=BoomEditor()) == "retry"
    assert run_worker(editor=BoomEditor()) == "retry"
    assert run_worker(editor=BoomEditor()) == "failed"

    polled = api.get(f"/v1/renders/{render_id}", headers=headers).json()
    assert polled["status"] == "failed"
    assert polled["error_code"] == "render_failed"
    assert api.get("/v1/me", headers=headers).json()["credits_left"] == 1


def test_architecture_ids_in_remove_ids_are_ignored(api):
    headers = sign_in(api)
    room_id = _ready_room(api, headers)
    # FakeVision inventory: A/B/C are architecture, D/E/F are objects
    r = _submit(api, headers, room_id, remove_ids=["A", "D"])
    assert r.json()["remove_ids"] == ["D"]


def test_list_renders_newest_first_and_scoped_to_owner(api, run_worker):
    owner = sign_in(api, sub="owner")
    room_id = _ready_room(api, owner)
    _submit(api, owner, room_id, key="one")

    listed = api.get(f"/v1/rooms/{room_id}/renders", headers=owner)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    intruder = sign_in(api, sub="intruder")
    assert api.get(f"/v1/rooms/{room_id}/renders", headers=intruder).status_code == 404
    assert (
        api.get(f"/v1/renders/{listed.json()[0]['render_id']}", headers=intruder).status_code == 404
    )
