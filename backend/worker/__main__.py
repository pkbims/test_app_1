"""The render worker.

A single loop: check in a heartbeat, lease one job, run it, repeat. Job leasing
(with a 5-minute lease for crash recovery) lives in `leasing.py`; the render
pipeline in `render_job.py`.
"""

from __future__ import annotations

import os
import socket
import sys
import time

from app.db import make_pool
from app.migrate import apply_all
from app.runtime import make_image_editor, make_vision
from app.settings import load
from app.storage import LocalDiskStorage

from .heartbeat import record
from .runner import run_one

HEARTBEAT_INTERVAL_S = 10
IDLE_SLEEP_S = 2


def main() -> None:
    settings = load()
    pool = make_pool(settings)
    with pool.connection() as conn:
        apply_all(conn)

    storage = LocalDiskStorage(settings.photo_dir)
    vision = make_vision(settings)
    editor = make_image_editor(settings)
    worker = f"{socket.gethostname()}:{os.getpid()}"
    print(f"worker {worker} up ({settings.vision_backend})", flush=True)

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
            else:
                print(f"job -> {outcome}", flush=True)
        except Exception as exc:  # noqa: BLE001 — keep the loop alive
            print(f"worker loop error: {exc}", file=sys.stderr, flush=True)
            time.sleep(IDLE_SLEEP_S)


if __name__ == "__main__":
    main()
