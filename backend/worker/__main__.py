"""The render worker.

For build-order step 1 it only checks in a heartbeat every few seconds, so
`/health` can tell whether a worker is alive. Job leasing and the render pipeline
(inventory prompt → gpt-image-2 → preservation check) arrive in step 6.
"""

from __future__ import annotations

import os
import socket
import sys
import time

from app.db import make_pool
from app.migrate import apply_all
from app.settings import load

from .heartbeat import record

HEARTBEAT_INTERVAL_S = 10


def main() -> None:
    settings = load()
    pool = make_pool(settings)
    with pool.connection() as conn:
        apply_all(conn)

    worker = f"{socket.gethostname()}:{os.getpid()}"
    print(f"worker {worker} up", flush=True)

    while True:
        try:
            with pool.connection() as conn:
                record(conn, worker)
        except Exception as exc:  # noqa: BLE001 — log and keep trying
            print(f"heartbeat failed: {exc}", file=sys.stderr, flush=True)
        time.sleep(HEARTBEAT_INTERVAL_S)


if __name__ == "__main__":
    main()
