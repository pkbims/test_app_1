"""Reads for `GET /v1/renders/{render_id}/shopping` (shopping_proto/HANDOFF.md
§4.1). The `shopping` table stores `crop_key`s, not signed URLs — this is where
they become the contract's `crop_url`, the same pattern as `Render.before_url`/
`after_url` being signed at read time from `before_key`/`after_key`.
"""

from __future__ import annotations

from ..errors import ApiError
from ..ids import parse_uuid
from ..render.service import RenderUrls
from ..schemas import ErrorCode, Shopping, ShoppingItem, ShoppingOption, ShoppingStatus

_NOT_FOUND = "We couldn't find that render."


def get_shopping(conn, render_id: str, user_id: str, *, urls: RenderUrls) -> Shopping:
    rid = parse_uuid(render_id, _NOT_FOUND)
    row = conn.execute(
        "SELECT s.status, s.items, s.total_from, s.prices_as_of "
        "FROM renders r LEFT JOIN shopping s ON s.render_id = r.id "
        "WHERE r.id = %s AND r.user_id = %s",
        (rid, user_id),
    ).fetchone()
    if row is None:
        raise ApiError(ErrorCode.not_found, _NOT_FOUND)

    status, raw_items, total_from, prices_as_of = row
    if status is None:  # no shopping row at all — predates the feature, or race
        return Shopping(render_id=str(rid), status=ShoppingStatus.none, items=[])

    items = [
        ShoppingItem(
            item_id=it["item_id"],
            name=it["name"],
            crop_url=urls.of("crops", it["crop_key"]),
            options=[ShoppingOption(**opt) for opt in it["options"]],
        )
        for it in (raw_items or [])
    ]
    return Shopping(
        render_id=str(rid),
        status=ShoppingStatus(status),
        prices_as_of=prices_as_of,
        total_from=float(total_from) if total_from is not None else None,
        items=items,
    )
