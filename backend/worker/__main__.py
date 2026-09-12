"""The worker.

A single loop: check in a heartbeat, lease one job, run it, repeat. Job leasing
(with a 5-minute lease for crash recovery) lives in `leasing.py`; the render
pipeline in `render_job.py`; the shopping pipeline in `app/shopping/` +
`shopping_job.py`. `runner.run_one` dispatches on the leased job's `kind`.
"""

from __future__ import annotations

import logging
import os
import socket
import time

from app.db import make_pool
from app.logs import configure
from app.migrate import apply_all
from app.runtime import (
    make_image_editor,
    make_shopping_config,
    make_shopping_model,
    make_shopping_searchapi,
    make_vision,
)
from app.settings import load
from app.storage import LocalDiskStorage
from app.tracking import capture
from app.tracking import configure as configure_tracking

from .heartbeat import record
from .runner import run_one

HEARTBEAT_INTERVAL_S = 10
IDLE_SLEEP_S = 2

_log = logging.getLogger("worker")


def main() -> None:
    settings = load()
    configure(settings.log_level)
    configure_tracking(settings.sentry_dsn, settings.app_env)
    pool = make_pool(settings)
    with pool.connection() as conn:
        apply_all(conn)

    storage = LocalDiskStorage(settings.photo_dir)
    vision = make_vision(settings)
    editor = make_image_editor(settings)
    shopping_model = make_shopping_model(settings)
    shopping_searchapi = make_shopping_searchapi(settings)
    shopping_config = make_shopping_config(settings)
    worker = f"{socket.gethostname()}:{os.getpid()}"
    _log.info(
        "worker up",
        extra={
            "worker": worker,
            "vision_backend": settings.vision_backend,
            "shopping_backend": settings.shopping_backend,
        },
    )

    last_beat = 0.0
    while True:
        try:
            with pool.connection() as conn:
                conn.autocommit = True
                now = time.monotonic()
                if now - last_beat >= HEARTBEAT_INTERVAL_S:
                    record(conn, worker)
                    last_beat = now
                outcome = run_one(
                    conn, storage, vision, editor, worker,
                    shopping_model=shopping_model,
                    shopping_searchapi=shopping_searchapi,
                    shopping_config=shopping_config,
                )
            if outcome is None:
                time.sleep(IDLE_SLEEP_S)
        except Exception as exc:  # noqa: BLE001 — keep the loop alive
            _log.exception("worker loop error")
            capture(exc)
            time.sleep(IDLE_SLEEP_S)


if __name__ == "__main__":
    main()
