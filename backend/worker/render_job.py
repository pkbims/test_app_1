"""Run one render: build the prompt, call the image model, score preservation.

Failure handling (PRD §17):
- any error generating or storing the image → retry twice with backoff, then fail
  the render, refund the credit, set `error_code = render_failed`
- the preservation check failing does NOT fail the render — the image is fine, we
  just have no score for it
- the structure/vision model being unavailable is handled upstream at
  `POST /inventory` (it returns `inventory_failed`); a render without an inventory
  is refused, never generated unconstrained
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from psycopg.types.json import Json

from app.imagegen import ImageEditor
from app.render.prompt import build_prompt
from app.schemas import InventoryItem
from app.tracking import capture
from app.vision import Vision, VisionError

from .leasing import Lease, mark_done, mark_failed, reschedule

MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = {1: 5, 2: 15}

_log = logging.getLogger("worker.render")


@dataclass
class _Job:
    status: str
    style: str
    user_prompt: str | None
    remove_ids: list[str]
    room_label: str | None
    before_key: str | None
    content_type: str | None
    items: list[dict] | None


def run(conn, storage, vision: Vision, editor: ImageEditor, lease: Lease) -> str:
    """Process the leased job. Returns one of: done, failed, retry, skipped."""
    log = logging.LoggerAdapter(
        _log,
        {"request_id": lease.request_id, "render_id": lease.render_id, "attempt": lease.attempts},
    )
    job = _load(conn, lease.render_id)
    if job is None:
        mark_failed(conn, lease.job_id, "render row is gone")
        return "skipped"
    if job.status in ("done", "failed"):
        mark_done(conn, lease.job_id)  # a straggler for an already-finished render
        return "skipped"
    if job.content_type is None or job.items is None:
        log.error("render is missing its photo or inventory")
        _fail_render(conn, lease.render_id, lease.job_id, "photo or inventory missing")
        return "failed"

    try:
        _set_running(conn, lease.render_id)
        after_key, rate, missing = _generate(storage, vision, editor, lease.render_id, job, log)
        _finish(conn, lease.render_id, after_key, rate, missing)
        mark_done(conn, lease.job_id)
        log.info("render done", extra={"preservation_rate": rate})
        return "done"
    except Exception as exc:  # noqa: BLE001 — routed to retry / fail-and-refund
        return _on_error(conn, lease, exc, log)


def _generate(storage, vision, editor, render_id, job: _Job, log):
    inventory = [InventoryItem(**it) for it in (job.items or [])]
    prompt = build_prompt(
        style=job.style,
        user_prompt=job.user_prompt,
        items=inventory,
        remove_ids=job.remove_ids,
        room_label=job.room_label,
    )
    image_bytes = storage.get(f"photos/{job.before_key}")
    after = editor.edit(image_bytes, job.content_type or "image/jpeg", prompt)

    after_key = f"{render_id}.png"
    storage.put(f"renders/{after_key}", after, "image/png")

    architecture = [(it.id, it.description) for it in inventory if it.kind == "architecture"]
    try:
        result = vision.preservation_check(after, architecture)
        return after_key, result.preservation_rate, result.missing_ids
    except VisionError as exc:
        log.warning("preservation check failed: %s", exc)
        return after_key, None, None


def _on_error(conn, lease: Lease, exc: Exception, log) -> str:
    if lease.attempts >= MAX_ATTEMPTS:
        log.error("render failed after %d attempts: %s", lease.attempts, exc)
        capture(exc)
        _fail_render(conn, lease.render_id, lease.job_id, str(exc))
        return "failed"
    log.warning("render error, will retry: %s", exc)
    reschedule(conn, lease.job_id, _BACKOFF_SECONDS.get(lease.attempts, 30), str(exc))
    return "retry"


def _load(conn, render_id: str) -> _Job | None:
    row = conn.execute(
        """
        SELECT r.status, r.style, r.prompt, r.remove_ids, ro.label,
               r.before_key, p.content_type, i.items
        FROM renders r
        JOIN rooms ro ON ro.id = r.room_id
        LEFT JOIN photos p ON p.room_id = r.room_id
        LEFT JOIN inventories i ON i.room_id = r.room_id
        WHERE r.id = %s
        """,
        (render_id,),
    ).fetchone()
    if row is None:
        return None
    return _Job(
        status=row[0],
        style=row[1],
        user_prompt=row[2],
        remove_ids=row[3] or [],
        room_label=row[4],
        before_key=row[5],
        content_type=row[6],
        items=row[7],
    )


def _set_running(conn, render_id: str) -> None:
    with conn.transaction():
        conn.execute(
            "UPDATE renders SET status = 'running', updated_at = now() WHERE id = %s",
            (render_id,),
        )


def _finish(conn, render_id: str, after_key: str, rate, missing) -> None:
    with conn.transaction():
        conn.execute(
            "UPDATE renders SET status = 'done', after_key = %s, preservation_rate = %s, "
            "missing_items = %s, updated_at = now() WHERE id = %s",
            (after_key, rate, Json(missing) if missing is not None else None, render_id),
        )


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
