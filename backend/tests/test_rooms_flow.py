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
