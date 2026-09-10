"""Run one render: build the prompt, call the image model, score preservation.

Failure handling (PRD §17):
- image-model error → retry twice with backoff, then fail the render, refund the
  credit, set `error_code = render_failed`
- the preservation check failing does NOT fail the render — the image is fine, we
  just have no score for it
"""

from __future__ import annotations

import logging

from psycopg.types.json import Json

from app.imagegen import ImageEditError, ImageEditor
from app.render.prompt import build_prompt
from app.schemas import InventoryItem
from app.vision import Vision, VisionError

from .leasing import Lease, mark_done, mark_failed, reschedule

MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = {1: 5, 2: 15}

_log = logging.getLogger("worker.render")


def run(conn, storage, vision: Vision, editor: ImageEditor, lease: Lease) -> str:
    """Process the leased job. Returns one of: done, failed, retry, skipped."""
    render_id = lease.render_id
    log = logging.LoggerAdapter(
        _log, {"request_id": lease.request_id, "render_id": render_id, "attempt": lease.attempts}
    )
    outcome = _run(conn, storage, vision, editor, lease, log)
    log.info("render %s", outcome)
    return outcome


def _run(conn, storage, vision: Vision, editor: ImageEditor, lease: Lease, log) -> str:
    render_id = lease.render_id
    row = conn.execute(
        """
        SELECT r.status, r.style, r.prompt, r.remove_ids, r.before_key,
               ro.label, p.content_type, i.items
        FROM renders r
        JOIN rooms ro ON ro.id = r.room_id
        LEFT JOIN photos p ON p.room_id = r.room_id
        LEFT JOIN inventories i ON i.room_id = r.room_id
        WHERE r.id = %s
        """,
        (render_id,),
    ).fetchone()
    if row is None:
        mark_failed(conn, lease.job_id, "render row is gone")
        return "skipped"

    status, style, user_prompt, remove_ids, photo_key, label, content_type, items = row
    if status in ("done", "failed"):
        mark_done(conn, lease.job_id)  # a straggler for an already-finished render
        return "skipped"
    if photo_key is None or items is None:
        _fail_render(conn, render_id, lease.job_id, "photo or inventory missing")
        return "failed"

    with conn.transaction():
        conn.execute(
            "UPDATE renders SET status = 'running', updated_at = now() WHERE id = %s",
            (render_id,),
        )

    inventory = [InventoryItem(**it) for it in items]
    prompt = build_prompt(
        style=style,
        user_prompt=user_prompt,
        items=inventory,
        remove_ids=remove_ids or [],
        room_label=label,
    )
    image_bytes = storage.get(f"photos/{photo_key}")

    try:
        after = editor.edit(image_bytes, content_type, prompt)
    except ImageEditError as exc:
        if lease.attempts >= MAX_ATTEMPTS:
            log.error("image edit failed, giving up: %s", exc)
            _fail_render(conn, render_id, lease.job_id, str(exc))
            return "failed"
        log.warning("image edit failed, will retry: %s", exc)
        reschedule(conn, lease.job_id, _BACKOFF_SECONDS.get(lease.attempts, 30), str(exc))
        return "retry"

    after_key = f"{render_id}.png"
    storage.put(f"renders/{after_key}", after, "image/png")

    architecture = [(it.id, it.description) for it in inventory if it.kind == "architecture"]
    try:
        result = vision.preservation_check(after, architecture)
        rate, missing = result.preservation_rate, result.missing_ids
    except VisionError as exc:
        rate, missing = None, None  # the render succeeded; only the score is missing
        log.warning("preservation check failed: %s", exc)

    with conn.transaction():
        conn.execute(
            "UPDATE renders SET status = 'done', after_key = %s, preservation_rate = %s, "
            "missing_items = %s, updated_at = now() WHERE id = %s",
            (after_key, rate, Json(missing) if missing is not None else None, render_id),
        )
    mark_done(conn, lease.job_id)
    return "done"


def _fail_render(conn, render_id: str, job_id: int, error: str) -> None:
    with conn.transaction():
        row = conn.execute(
            "SELECT user_id, status FROM renders WHERE id = %s FOR UPDATE", (render_id,)
        ).fetchone()
        if row is not None and row[1] != "failed":
            conn.execute(
                "UPDATE renders SET status = 'failed', error_code = 'render_failed', "
                "updated_at = now() WHERE id = %s",
                (render_id,),
            )
            # Refund the spent credit — once. Nobody forgives being charged for our
            # outage (PRD §16).
            conn.execute(
                "INSERT INTO credit_ledger (user_id, delta, reason, render_id) "
                "SELECT %s, 1, 'render_refund', %s "
                "WHERE NOT EXISTS ("
                "  SELECT 1 FROM credit_ledger WHERE render_id = %s AND reason = 'render_refund'"
                ")",
                (row[0], render_id, render_id),
            )
        mark_failed(conn, job_id, error)
