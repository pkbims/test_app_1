"""The room inventory (build-order step 5).

A vision call lists the room's fixed architecture and its moveable objects. We
give each a letter (A, B, ... AA, AB) in the order returned, mark architecture
`removable=false` and objects `removable=true`, and store the list whole. `GET`
reads it back. One inventory per room; re-running replaces it.
"""

from __future__ import annotations

from psycopg.types.json import Json

from ..errors import ApiError
from ..ids import parse_uuid
from ..metrics import INVENTORY_ATTEMPTS, INVENTORY_FAILURES
from ..schemas import ErrorCode, Inventory, InventoryItem
from ..vision import Vision, VisionError

_ROOM_NOT_FOUND = "We couldn't find that room."
_VISION_FAILED = "We couldn't read your room just now. Please try again in a moment."
_ARCHITECTURE = "architecture"


def create_inventory(conn, storage, vision: Vision, room_id: str, user_id: str) -> Inventory:
    rid = parse_uuid(room_id, _ROOM_NOT_FOUND)
    row = conn.execute(
        "SELECT p.storage_key, p.content_type "
        "FROM rooms r LEFT JOIN photos p ON p.room_id = r.id "
        "WHERE r.id = %s AND r.user_id = %s",
        (rid, user_id),
    ).fetchone()
    if row is None:
        raise ApiError(ErrorCode.not_found, _ROOM_NOT_FOUND)
    storage_key, content_type = row
    if storage_key is None:
        raise ApiError(ErrorCode.no_photos, "Add a photo of this room first.")

    image_bytes = storage.get(f"photos/{storage_key}")
    INVENTORY_ATTEMPTS.inc()
    try:
        result = vision.inventory(image_bytes, content_type)
    except VisionError as exc:
        INVENTORY_FAILURES.inc()
        raise ApiError(ErrorCode.inventory_failed, _VISION_FAILED) from exc
    if not result.items:
        INVENTORY_FAILURES.inc()
        raise ApiError(ErrorCode.inventory_failed, _VISION_FAILED)

    items = [
        InventoryItem(
            id=_letter(i),
            kind=raw.kind,
            name=raw.name,
            description=raw.description,
            removable=raw.kind != _ARCHITECTURE,
        )
        for i, raw in enumerate(result.items)
    ]
    created_at = conn.execute(
        "INSERT INTO inventories (room_id, items, prompt, room_type) VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (room_id) DO UPDATE "
        "SET items = EXCLUDED.items, prompt = EXCLUDED.prompt, room_type = EXCLUDED.room_type, "
        "    created_at = now() "
        "RETURNING created_at",
        (rid, Json([it.model_dump() for it in items]), result.prompt, result.room_type),
    ).fetchone()[0]
    return Inventory(room_id=str(rid), items=items, created_at=created_at, room_type=result.room_type)


def get_inventory(conn, room_id: str, user_id: str) -> Inventory:
    rid = parse_uuid(room_id, _ROOM_NOT_FOUND)
    row = conn.execute(
        "SELECT i.items, i.created_at, i.room_type FROM inventories i "
        "JOIN rooms r ON r.id = i.room_id "
        "WHERE i.room_id = %s AND r.user_id = %s",
        (rid, user_id),
    ).fetchone()
    if row is None:
        raise ApiError(ErrorCode.not_found, "This room has no inventory yet.")
    items = [InventoryItem(**raw) for raw in row[0]]
    return Inventory(room_id=str(rid), items=items, created_at=row[1], room_type=row[2])


def _letter(index: int) -> str:
    """0->A ... 25->Z, 26->AA, 27->AB, ..."""
    if index < 26:
        return chr(ord("A") + index)
    return chr(ord("A") + index // 26 - 1) + chr(ord("A") + index % 26)
