"""Run one shopping job: lease bookkeeping around `app/shopping/pipeline.py`.

Same split as `render_job.py` vs. `app/render/prompt.py` — this file owns the
`jobs` row (retry, backoff, done/failed); the pipeline module owns the actual
work and the `shopping` row. Max 2 attempts (shorter than a render's 3): on
final failure the shopping row becomes `none` and the render itself is
untouched (shopping_proto/HANDOFF.md §4.2).
"""

from __future__ import annotations

import logging
import time

from app.shopping.judge import ShoppingModel
from app.shopping.pipeline import ShoppingConfig, generate, load_render_info, write_none, write_ready
from app.shopping.searchapi import SearchApi

from .leasing import Lease, mark_done, mark_failed, reschedule

MAX_ATTEMPTS = 2
_BACKOFF_SECONDS = {1: 5}

_log = logging.getLogger("worker.shopping")


def run(
    conn, storage, model: ShoppingModel | None, searchapi: SearchApi | None,
    config: ShoppingConfig, lease: Lease,
) -> str:
    """Process the leased shopping job. Returns one of: done, failed, retry, skipped."""
    log = logging.LoggerAdapter(
        _log,
        {"request_id": lease.request_id, "render_id": lease.render_id, "attempt": lease.attempts},
    )

    if model is None or searchapi is None:  # SHOPPING_BACKEND=off — calls nothing
        write_none(conn, lease.render_id, error=None)
        mark_done(conn, lease.job_id)
        return "done"

    info = load_render_info(conn, lease.render_id)
    if info is None:
        write_none(conn, lease.render_id, error="render row is gone")
        mark_failed(conn, lease.job_id, "render row is gone")
        return "skipped"

    try:
        t0 = time.monotonic()
        result = generate(storage, model, searchapi, lease.render_id, info, config, log)
        write_ready(conn, lease.render_id, result)
        mark_done(conn, lease.job_id)
        log.info(
            "shopping done",
            extra={
                "items_found": len(result.items),
                "option_count": sum(len(it["options"]) for it in result.items),
                "cost_cents": result.cost_cents,
                "searchapi_calls": result.searchapi_calls,
                "searchapi_errors": result.searchapi_errors,
                "duration_s": round(time.monotonic() - t0, 1),
            },
        )
        return "done"
    except Exception as exc:  # noqa: BLE001 — routed to retry / final-none below
        if lease.attempts >= MAX_ATTEMPTS:
            log.error("shopping failed after %d attempts: %s", lease.attempts, exc)
            write_none(conn, lease.render_id, error=str(exc))
            mark_failed(conn, lease.job_id, str(exc))
            return "failed"
        log.warning("shopping error, will retry: %s", exc)
        reschedule(conn, lease.job_id, _BACKOFF_SECONDS.get(lease.attempts, 15), str(exc))
        return "retry"
