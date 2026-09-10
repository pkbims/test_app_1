"""Submitting and reading renders (build-order steps 6-7).

Submit is where money moves, so it is one transaction under a row lock on the
user: check the idempotency key, require an inventory, check credits, spend one
credit (a `credit_ledger` row), and enqueue a job — all or nothing. A retry with
the same `idempotency_key` returns the existing render and never charges twice.
"""

from __future__ import annotations

import uuid

from psycopg.types.json import Json

from ..errors import ApiError
from ..files import signed_url
from ..ids import parse_uuid
from ..schemas import ErrorCode, Render, RenderCreate, RenderStatus

_ROOM_NOT_FOUND = "We couldn't find that room."
_RENDER_NOT_FOUND = "We couldn't find that render."

_COLS = (
    "id",
    "room_id",
    "status",
    "style",
    "remove_ids",
    "before_key",
    "after_key",
    "preservation_rate",
    "missing_items",
    "error_code",
    "created_at",
)
_SELECT = f"SELECT {', '.join(_COLS)} FROM renders "


class RenderUrls:
    def __init__(self, base_url: str, secret: str, ttl_s: int) -> None:
        self.base_url, self.secret, self.ttl_s = base_url, secret, ttl_s

    def of(self, scope: str, key: str | None) -> str | None:
        if not key:
            return None
        return signed_url(self.base_url, scope, key, self.secret, self.ttl_s)


def create_render(
    conn, *, room_id: str, user_id: str, body: RenderCreate, urls: RenderUrls
) -> Render:
    rid = parse_uuid(room_id, _ROOM_NOT_FOUND)
    with conn.transaction():
        conn.execute("SELECT id FROM users WHERE id = %s FOR UPDATE", (user_id,))
        room = conn.execute(
            "SELECT p.storage_key, i.items "
            "FROM rooms r "
            "LEFT JOIN photos p ON p.room_id = r.id "
            "LEFT JOIN inventories i ON i.room_id = r.id "
            "WHERE r.id = %s AND r.user_id = %s",
            (rid, user_id),
        ).fetchone()
        if room is None:
            raise ApiError(ErrorCode.not_found, _ROOM_NOT_FOUND)
        photo_key, inventory_items = room

        existing = conn.execute(
            _SELECT + "WHERE user_id = %s AND idempotency_key = %s",
            (user_id, body.idempotency_key),
        ).fetchone()
        if existing is not None:
            return _to_render(existing, credits_left=_balance(conn, user_id), urls=urls)

        if inventory_items is None:
            raise ApiError(ErrorCode.no_inventory, "Run the inventory for this room first.")
        if photo_key is None:
            raise ApiError(ErrorCode.no_photos, "Add a photo of this room first.")

        balance = _balance(conn, user_id)
        if balance < 1:
            raise ApiError(ErrorCode.no_credits, "You've used your free room.")

        removable = {it["id"] for it in inventory_items if it.get("removable")}
        remove_ids = [rid_ for rid_ in body.remove_ids if rid_ in removable]

        render_id = uuid.uuid4()
        conn.execute(
            "INSERT INTO renders (id, room_id, user_id, status, style, prompt, "
            "remove_ids, idempotency_key, before_key) "
            "VALUES (%s, %s, %s, 'queued', %s, %s, %s, %s, %s)",
            (
                render_id,
                rid,
                user_id,
                body.style,
                body.prompt,
                Json(remove_ids),
                body.idempotency_key,
                photo_key,
            ),
        )
        conn.execute(
            "INSERT INTO credit_ledger (user_id, delta, reason, render_id) "
            "VALUES (%s, -1, 'render_spend', %s)",
            (user_id, render_id),
        )
        conn.execute("INSERT INTO jobs (render_id, status) VALUES (%s, 'queued')", (render_id,))
        row = conn.execute(_SELECT + "WHERE id = %s", (render_id,)).fetchone()

    return _to_render(row, credits_left=balance - 1, urls=urls)


def get_render(conn, render_id: str, user_id: str, *, urls: RenderUrls) -> Render:
    rid = parse_uuid(render_id, _RENDER_NOT_FOUND)
    row = conn.execute(_SELECT + "WHERE id = %s AND user_id = %s", (rid, user_id)).fetchone()
    if row is None:
        raise ApiError(ErrorCode.not_found, _RENDER_NOT_FOUND)
    return _to_render(row, credits_left=_balance(conn, user_id), urls=urls)


def list_renders(conn, room_id: str, user_id: str, *, urls: RenderUrls) -> list[Render]:
    rid = parse_uuid(room_id, _ROOM_NOT_FOUND)
    if (
        conn.execute(
            "SELECT 1 FROM rooms WHERE id = %s AND user_id = %s", (rid, user_id)
        ).fetchone()
        is None
    ):
        raise ApiError(ErrorCode.not_found, _ROOM_NOT_FOUND)
    rows = conn.execute(_SELECT + "WHERE room_id = %s ORDER BY created_at DESC", (rid,)).fetchall()
    balance = _balance(conn, user_id)
    return [_to_render(r, credits_left=balance, urls=urls) for r in rows]


def _balance(conn, user_id: str) -> int:
    return int(
        conn.execute(
            "SELECT coalesce(sum(delta), 0) FROM credit_ledger WHERE user_id = %s",
            (user_id,),
        ).fetchone()[0]
    )


def _to_render(row, *, credits_left: int, urls: RenderUrls) -> Render:
    (
        rid,
        room_id,
        status,
        style,
        remove_ids,
        before_key,
        after_key,
        preservation_rate,
        missing_items,
        error_code,
        created_at,
    ) = row
    return Render(
        render_id=str(rid),
        room_id=str(room_id),
        status=RenderStatus(status),
        style=style,
        remove_ids=list(remove_ids or []),
        before_url=urls.of("photos", before_key),
        after_url=urls.of("renders", after_key),
        preservation_rate=preservation_rate,
        missing_items=list(missing_items) if missing_items is not None else None,
        error_code=error_code,
        created_at=created_at,
        credits_left=credits_left,
    )
