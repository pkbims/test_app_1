"""The render worker.

A single loop: check in a heartbeat, lease one job, run it, repeat. Job leasing
(with a 5-minute lease for crash recovery) lives in `leasing.py`; the render
pipeline in `render_job.py`.
"""

from __future__ import annotations

import logging
import os
import socket
import time

from app.db import make_pool
from app.logs import configure
from app.migrate import apply_all
from app.runtime import make_image_editor, make_vision
from app.settings import load
from app.storage import LocalDiskStorage

from .heartbeat import record
from .runner import run_one

HEARTBEAT_INTERVAL_S = 10
IDLE_SLEEP_S = 2

_log = logging.getLogger("worker")


def main() -> None:
    settings = load()
    configure(settings.log_level)
    pool = make_pool(settings)
    with pool.connection() as conn:
        apply_all(conn)

    storage = LocalDiskStorage(settings.photo_dir)
    vision = make_vision(settings)
    editor = make_image_editor(settings)
    worker = f"{socket.gethostname()}:{os.getpid()}"
    _log.info("worker up", extra={"worker": worker, "vision_backend": settings.vision_backend})

    last_beat = 0.0
    while True:
        try:
            with pool.connection() as conn:
                conn.autocommit = True
                now = time.monotonic()
                if now - last_beat >= HEARTBEAT_INTERVAL_S:
                    record(conn, worker)
                    last_beat = now
                outcome = run_one(conn, storage, vision, editor, worker)
            if outcome is None:
                time.sleep(IDLE_SLEEP_S)
        except Exception:  # noqa: BLE001 — keep the loop alive
            _log.exception("worker loop error")
            time.sleep(IDLE_SLEEP_S)


if __name__ == "__main__":
    main()
