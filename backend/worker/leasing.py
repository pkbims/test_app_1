"""Leasing jobs off the Postgres queue.

A worker claims a job by setting a 5-minute lease. If the worker dies mid-job the
lease expires and the row becomes claimable again (PRD §17) — that is the whole
crash-recovery story, no separate reaper. `FOR UPDATE SKIP LOCKED` lets several
workers pull from the same queue without stepping on each other.
"""

from __future__ import annotations

from dataclasses import dataclass

LEASE_SECONDS = 300


@dataclass(frozen=True)
class Lease:
    job_id: int
    render_id: str
    attempts: int  # including this one
    request_id: str | None  # the API request that enqueued this job
    kind: str  # 'render' | 'shopping' — the worker dispatches on this


def lease_one(conn, worker: str, *, lease_seconds: int = LEASE_SECONDS) -> Lease | None:
    row = conn.execute(
        """
        UPDATE jobs SET
            status = 'running',
            leased_by = %s,
            lease_expires_at = now() + make_interval(secs => %s),
            attempts = attempts + 1,
            updated_at = now()
        WHERE id = (
            SELECT id FROM jobs
            WHERE run_after <= now()
              AND (status = 'queued'
                   OR (status = 'running' AND lease_expires_at < now()))
            ORDER BY run_after
            FOR UPDATE SKIP LOCKED
            LIMIT 1
        )
        RETURNING id, render_id, attempts, request_id, kind
        """,
        (worker, lease_seconds),
    ).fetchone()
    if row is None:
        return None
    return Lease(job_id=row[0], render_id=str(row[1]), attempts=row[2], request_id=row[3], kind=row[4])


def mark_done(conn, job_id: int) -> None:
    conn.execute("UPDATE jobs SET status = 'done', updated_at = now() WHERE id = %s", (job_id,))


def mark_failed(conn, job_id: int, error: str) -> None:
    conn.execute(
        "UPDATE jobs SET status = 'failed', last_error = %s, updated_at = now() WHERE id = %s",
        (error[:500], job_id),
    )


def reschedule(conn, job_id: int, delay_seconds: int, error: str) -> None:
    conn.execute(
        """
        UPDATE jobs SET
            status = 'queued',
            leased_by = NULL,
            lease_expires_at = NULL,
            last_error = %s,
            run_after = now() + make_interval(secs => %s),
            updated_at = now()
        WHERE id = %s
        """,
        (error[:500], delay_seconds, job_id),
    )
