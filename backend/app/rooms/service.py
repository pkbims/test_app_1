"""Rooms and their single photo (build-order step 4).

Ownership: every path id is resolved against the caller. An id that is malformed,
unknown, or owned by someone else all return the same 404 `not_found` — the API
never reveals that a room exists (ORCH-QUESTIONS Q2).
"""

from __future__ import annotations

import uuid

from ..errors import ApiError
from ..files import signed_url
from ..ids import parse_uuid
from ..images import UnsupportedImage, inspect
from ..schemas import ErrorCode, Photo, Room
from ..storage import Storage

_NOT_FOUND = "We couldn't find that room."


def create_room(conn, user_id: str, label: str | None) -> Room:
    row = conn.execute(
        "INSERT INTO rooms (user_id, label) VALUES (%s, %s) RETURNING id, label, created_at",
        (user_id, label),
    ).fetchone()
    return Room(
        room_id=str(row[0]),
        label=row[1],
        created_at=row[2],
        has_photo=False,
        has_inventory=False,
    )


def delete_room(conn, storage: Storage, room_id: str, user_id: str) -> None:
    rid = parse_uuid(room_id, _NOT_FOUND)
    with conn.transaction():
        photo = conn.execute("SELECT storage_key FROM photos WHERE room_id = %s", (rid,)).fetchone()
        deleted = conn.execute(
            "DELETE FROM rooms WHERE id = %s AND user_id = %s RETURNING id", (rid, user_id)
        ).fetchone()
        if deleted is None:
            raise ApiError(ErrorCode.not_found, _NOT_FOUND)
    # The photo *row* went with the cascade; remove the file too. Best effort — an
    # orphaned file is harmless and a later sweep can catch it.
    if photo is not None:
        storage.delete(f"photos/{photo[0]}")


def upload_photo(
    conn,
    storage: Storage,
    *,
    room_id: str,
    user_id: str,
    data: bytes,
    max_bytes: int,
    public_base_url: str,
    url_secret: str,
    url_ttl_s: int,
) -> Photo:
    rid = parse_uuid(room_id, _NOT_FOUND)
    if len(data) > max_bytes:
        raise ApiError(ErrorCode.photo_too_large, "That photo is over 12 MB. Try a smaller one.")
    try:
        info = inspect(data)
    except UnsupportedImage as exc:
        raise ApiError(ErrorCode.photo_unsupported, "Photos need to be a JPEG or PNG.") from exc

    photo_id = uuid.uuid4()
    key = f"{rid}/{photo_id}.{info.ext}"  # storage-relative; scope is "photos"

    with conn.transaction():
        owner = conn.execute("SELECT user_id FROM rooms WHERE id = %s", (rid,)).fetchone()
        if owner is None or str(owner[0]) != user_id:
            raise ApiError(ErrorCode.not_found, _NOT_FOUND)
        # One photo per room. A re-upload replaces the previous one (you retook the
        # shot); the old file is cleaned up after the row is gone.
        old = conn.execute(
            "DELETE FROM photos WHERE room_id = %s RETURNING storage_key", (rid,)
        ).fetchone()
        conn.execute(
            "INSERT INTO photos (id, room_id, storage_key, content_type, width, height, byte_size) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (photo_id, rid, key, info.content_type, info.width, info.height, len(data)),
        )
        storage.put(f"photos/{key}", data, info.content_type)

    if old is not None and old[0] != key:
        storage.delete(f"photos/{old[0]}")

    return Photo(
        photo_id=str(photo_id),
        room_id=str(rid),
        width=info.width,
        height=info.height,
        url=signed_url(public_base_url, "photos", key, url_secret, url_ttl_s),
    )
