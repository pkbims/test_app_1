"""Rooms and photos end to end (build-order step 4)."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from .conftest import sign_in

pytestmark = pytest.mark.integration


def _jpeg(size=(1024, 768)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 180, 160)).save(buf, format="JPEG")
    return buf.getvalue()


def _create_room(api, headers) -> str:
    r = api.post("/v1/rooms", json={"label": "Living room"}, headers=headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["has_photo"] is False and body["has_inventory"] is False
    return body["room_id"]


def test_create_room_then_upload_and_fetch_photo(api):
    headers = sign_in(api)
    room_id = _create_room(api, headers)

    img = _jpeg((1200, 900))
    up = api.post(
        f"/v1/rooms/{room_id}/photos",
        files={"file": ("room.jpg", img, "image/jpeg")},
        headers=headers,
    )
    assert up.status_code == 200, up.text
    photo = up.json()
    assert photo["room_id"] == room_id
    assert (photo["width"], photo["height"]) == (1200, 900)

    # The signed URL is fetchable and returns the bytes, no auth header.
    got = api.get(photo["url"])
    assert got.status_code == 200
    assert got.content == img
    assert got.headers["content-type"] == "image/jpeg"


def test_photo_url_signature_is_enforced(api):
    headers = sign_in(api)
    room_id = _create_room(api, headers)
    url = api.post(
        f"/v1/rooms/{room_id}/photos",
        files={"file": ("r.jpg", _jpeg(), "image/jpeg")},
        headers=headers,
    ).json()["url"]

    assert api.get(url.split("?")[0]).status_code == 404  # no signature
    assert api.get(url + "tampered").status_code == 404


def test_reject_oversize_photo(api):
    headers = sign_in(api)
    room_id = _create_room(api, headers)
    big = b"\xff\xd8\xff" + b"\x00" * (12 * 1024 * 1024 + 1)
    r = api.post(
        f"/v1/rooms/{room_id}/photos",
        files={"file": ("big.jpg", big, "image/jpeg")},
        headers=headers,
    )
    assert r.status_code == 413
    assert r.json()["code"] == "photo_too_large"


def test_reject_non_image(api):
    headers = sign_in(api)
    room_id = _create_room(api, headers)
    r = api.post(
        f"/v1/rooms/{room_id}/photos",
        files={"file": ("notes.txt", b"just some text", "text/plain")},
        headers=headers,
    )
    assert r.status_code == 400
    assert r.json()["code"] == "photo_unsupported"


def test_reupload_replaces_the_previous_photo(api):
    headers = sign_in(api)
    room_id = _create_room(api, headers)
    first = api.post(
        f"/v1/rooms/{room_id}/photos",
        files={"file": ("a.jpg", _jpeg((640, 480)), "image/jpeg")},
        headers=headers,
    ).json()
    second = api.post(
        f"/v1/rooms/{room_id}/photos",
        files={"file": ("b.png", _png((500, 500)), "image/png")},
        headers=headers,
    ).json()

    assert api.get(first["url"]).status_code == 404  # old file gone
    assert api.get(second["url"]).status_code == 200


def test_delete_room_removes_photo_and_is_idempotent_as_404(api):
    headers = sign_in(api)
    room_id = _create_room(api, headers)
    url = api.post(
        f"/v1/rooms/{room_id}/photos",
        files={"file": ("r.jpg", _jpeg(), "image/jpeg")},
        headers=headers,
    ).json()["url"]

    assert api.delete(f"/v1/rooms/{room_id}", headers=headers).status_code == 204
    assert api.get(url).status_code == 404
    assert api.delete(f"/v1/rooms/{room_id}", headers=headers).status_code == 404


def test_another_users_room_is_404_not_403(api):
    owner = sign_in(api, sub="owner.person")
    room_id = _create_room(api, owner)

    intruder = sign_in(api, sub="intruder.person")
    assert (
        api.post(
            f"/v1/rooms/{room_id}/photos",
            files={"file": ("r.jpg", _jpeg(), "image/jpeg")},
            headers=intruder,
        ).status_code
        == 404
    )
    assert api.delete(f"/v1/rooms/{room_id}", headers=intruder).status_code == 404


def test_unknown_and_malformed_room_ids_are_404(api):
    headers = sign_in(api)
    assert api.delete("/v1/rooms/not-a-uuid", headers=headers).status_code == 404
    assert (
        api.delete("/v1/rooms/00000000-0000-0000-0000-000000000000", headers=headers).status_code
        == 404
    )


def _png(size=(400, 400)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


# ── GET /v1/rooms — list ─────────────────────────────────────────────────────
def test_list_rooms_is_empty_for_a_fresh_user(api):
    headers = sign_in(api)
    r = api.get("/v1/rooms", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


def test_list_rooms_is_newest_first(api):
    headers = sign_in(api)
    first = api.post("/v1/rooms", json={"label": "First"}, headers=headers).json()["room_id"]
    second = api.post("/v1/rooms", json={"label": "Second"}, headers=headers).json()["room_id"]

    ids = [r["room_id"] for r in api.get("/v1/rooms", headers=headers).json()]
    assert ids == [second, first]


def test_list_rooms_reflects_photo_and_inventory_state(api):
    headers = sign_in(api)
    bare_room = api.post("/v1/rooms", json={}, headers=headers).json()["room_id"]
    ready_room = _create_room(api, headers)
    api.post(
        f"/v1/rooms/{ready_room}/photos",
        files={"file": ("r.jpg", _jpeg(), "image/jpeg")},
        headers=headers,
    )
    api.post(f"/v1/rooms/{ready_room}/inventory", headers=headers)

    by_id = {r["room_id"]: r for r in api.get("/v1/rooms", headers=headers).json()}
    assert by_id[bare_room]["has_photo"] is False
    assert by_id[bare_room]["has_inventory"] is False
    assert by_id[ready_room]["has_photo"] is True
    assert by_id[ready_room]["has_inventory"] is True


def _submit_render(api, headers, room_id, key="idem-thumb", remove_ids=None):
    return api.post(
        f"/v1/rooms/{room_id}/renders",
        json={
            "style": "warm-minimal",
            "remove_ids": remove_ids or [],
            "idempotency_key": key,
        },
        headers=headers,
    )


def _room(rooms, room_id):
    return next(r for r in rooms if r["room_id"] == room_id)


def test_create_room_thumbnail_is_null(api):
    headers = sign_in(api)
    body = api.post("/v1/rooms", json={}, headers=headers).json()
    assert body["thumbnail_url"] is None


def test_list_rooms_thumbnail_is_null_with_no_photo(api):
    headers = sign_in(api)
    room_id = api.post("/v1/rooms", json={}, headers=headers).json()["room_id"]
    listed = api.get("/v1/rooms", headers=headers).json()
    assert _room(listed, room_id)["thumbnail_url"] is None


def test_list_rooms_thumbnail_is_the_photo_before_any_render(api):
    headers = sign_in(api)
    room_id = _create_room(api, headers)
    photo_url = api.post(
        f"/v1/rooms/{room_id}/photos",
        files={"file": ("r.jpg", _jpeg(), "image/jpeg")},
        headers=headers,
    ).json()["url"]

    listed = api.get("/v1/rooms", headers=headers).json()
    thumb = _room(listed, room_id)["thumbnail_url"]
    assert thumb.split("?")[0] == photo_url.split("?")[0]
    assert api.get(thumb).status_code == 200


def test_list_rooms_thumbnail_is_the_latest_done_renders_after_image(api, run_worker):
    headers = sign_in(api)
    room_id = _create_room(api, headers)
    api.post(
        f"/v1/rooms/{room_id}/photos",
        files={"file": ("r.jpg", _jpeg(), "image/jpeg")},
        headers=headers,
    )
    api.post(f"/v1/rooms/{room_id}/inventory", headers=headers)

    render = _submit_render(api, headers, room_id).json()
    assert run_worker() == "done"
    after_url = api.get(f"/v1/renders/{render['render_id']}", headers=headers).json()["after_url"]

    listed = api.get("/v1/rooms", headers=headers).json()
    thumb = _room(listed, room_id)["thumbnail_url"]
    assert thumb.split("?")[0] == after_url.split("?")[0]
    assert api.get(thumb).status_code == 200


def test_list_rooms_thumbnail_falls_back_to_photo_when_render_failed(api, run_worker):
    from app.imagegen import ImageEditError

    class BoomEditor:
        def edit(self, *_a):
            raise ImageEditError("image model exploded")

    headers = sign_in(api)
    room_id = _create_room(api, headers)
    photo_url = api.post(
        f"/v1/rooms/{room_id}/photos",
        files={"file": ("r.jpg", _jpeg(), "image/jpeg")},
        headers=headers,
    ).json()["url"]
    api.post(f"/v1/rooms/{room_id}/inventory", headers=headers)
    _submit_render(api, headers, room_id)

    assert run_worker(editor=BoomEditor()) == "retry"
    assert run_worker(editor=BoomEditor()) == "retry"
    assert run_worker(editor=BoomEditor()) == "failed"

    listed = api.get("/v1/rooms", headers=headers).json()
    thumb = _room(listed, room_id)["thumbnail_url"]
    assert thumb.split("?")[0] == photo_url.split("?")[0]


def test_list_rooms_is_scoped_to_the_caller(api):
    owner = sign_in(api, sub="rooms.owner")
    _create_room(api, owner)
    intruder = sign_in(api, sub="rooms.intruder")
    assert api.get("/v1/rooms", headers=intruder).json() == []


def test_list_rooms_requires_a_token(api):
    assert api.get("/v1/rooms").status_code == 401
