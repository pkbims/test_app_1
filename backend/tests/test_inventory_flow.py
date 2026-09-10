"""Inventory end to end (build-order step 5), with the fake vision backend."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from .conftest import sign_in

pytestmark = pytest.mark.integration


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (900, 700), (180, 170, 160)).save(buf, format="JPEG")
    return buf.getvalue()


def _room_with_photo(api, headers) -> str:
    room_id = api.post("/v1/rooms", json={"label": "Lounge"}, headers=headers).json()["room_id"]
    api.post(
        f"/v1/rooms/{room_id}/photos",
        files={"file": ("r.jpg", _jpeg(), "image/jpeg")},
        headers=headers,
    )
    return room_id


def test_create_and_read_inventory(api):
    headers = sign_in(api)
    room_id = _room_with_photo(api, headers)

    created = api.post(f"/v1/rooms/{room_id}/inventory", headers=headers)
    assert created.status_code == 200, created.text
    inv = created.json()
    assert inv["room_id"] == room_id
    assert [i["id"] for i in inv["items"]] == ["A", "B", "C", "D", "E", "F"]
    for item in inv["items"]:
        assert item["removable"] == (item["kind"] != "architecture")
    assert any(i["kind"] == "architecture" for i in inv["items"])

    read = api.get(f"/v1/rooms/{room_id}/inventory", headers=headers)
    assert read.status_code == 200
    assert read.json()["items"] == inv["items"]


def test_re_running_inventory_replaces_it(api):
    headers = sign_in(api)
    room_id = _room_with_photo(api, headers)
    api.post(f"/v1/rooms/{room_id}/inventory", headers=headers)
    again = api.post(f"/v1/rooms/{room_id}/inventory", headers=headers)
    assert again.status_code == 200


def test_inventory_without_a_photo_is_no_photos(api):
    headers = sign_in(api)
    room_id = api.post("/v1/rooms", json={}, headers=headers).json()["room_id"]
    r = api.post(f"/v1/rooms/{room_id}/inventory", headers=headers)
    assert r.status_code == 400
    assert r.json()["code"] == "no_photos"


def test_get_inventory_before_it_exists_is_404(api):
    headers = sign_in(api)
    room_id = _room_with_photo(api, headers)
    assert api.get(f"/v1/rooms/{room_id}/inventory", headers=headers).status_code == 404


def test_inventory_on_another_users_room_is_404(api):
    owner = sign_in(api, sub="owner")
    room_id = _room_with_photo(api, owner)
    intruder = sign_in(api, sub="intruder")
    assert api.post(f"/v1/rooms/{room_id}/inventory", headers=intruder).status_code == 404
    assert api.get(f"/v1/rooms/{room_id}/inventory", headers=intruder).status_code == 404


def test_inventory_on_unknown_room_is_404(api):
    headers = sign_in(api)
    assert api.post("/v1/rooms/not-a-uuid/inventory", headers=headers).status_code == 404
