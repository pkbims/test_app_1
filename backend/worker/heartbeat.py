"""Worker liveness. `/health` goes `degraded` when no heartbeat has landed inside
the timeout window (PRD §17), which is how a dead worker becomes visible."""

from __future__ import annotations


def record(conn, worker: str) -> None:
    conn.execute(
        """
        INSERT INTO worker_heartbeats (worker, last_seen)
        VALUES (%s, now())
        ON CONFLICT (worker) DO UPDATE SET last_seen = now()
        """,
        (worker,),
    )
