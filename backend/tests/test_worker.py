"""Queue leasing mechanics (build-order step 6, PRD §17 crash recovery)."""

from __future__ import annotations

import pytest

from app.migrate import apply_all
from worker import leasing

pytestmark = pytest.mark.integration


@pytest.fixture
def conn(pg_conn):
    apply_all(pg_conn)
    pg_conn.autocommit = True
    return pg_conn


def _enqueue(conn, **cols) -> int:
    keys = ", ".join(cols)
    ph = ", ".join(["%s"] * len(cols))
    return conn.execute(
        f"INSERT INTO jobs ({keys}) VALUES ({ph}) RETURNING id"
        if cols
        else "INSERT INTO jobs DEFAULT VALUES RETURNING id",
        tuple(cols.values()),
    ).fetchone()[0]


def test_leases_a_queued_job_and_bumps_attempts(conn):
    job_id = _enqueue(conn)
    lease = leasing.lease_one(conn, "w1")
    assert lease is not None
    assert lease.job_id == job_id
    assert lease.attempts == 1

    row = conn.execute(
        "SELECT status, leased_by, lease_expires_at > now() FROM jobs WHERE id = %s", (job_id,)
    ).fetchone()
    assert row == ("running", "w1", True)


def test_nothing_to_lease_returns_none(conn):
    assert leasing.lease_one(conn, "w1") is None


def test_a_job_scheduled_for_later_is_not_leased(conn):
    conn.execute("INSERT INTO jobs (run_after) VALUES (now() + interval '1 hour')")
    assert leasing.lease_one(conn, "w1") is None


def test_expired_lease_is_reclaimed(conn):
    job_id = _enqueue(conn)
    conn.execute(
        "UPDATE jobs SET status='running', leased_by='dead', "
        "lease_expires_at = now() - interval '1 minute' WHERE id = %s",
        (job_id,),
    )
    lease = leasing.lease_one(conn, "w2")
    assert lease is not None and lease.job_id == job_id
    assert lease.attempts == 1  # attempts was 0 before; +1 now


def test_a_live_lease_is_not_stolen(conn):
    job_id = _enqueue(conn)
    leasing.lease_one(conn, "w1")
    assert leasing.lease_one(conn, "w2") is None
    conn.execute("SELECT 1 FROM jobs WHERE id = %s", (job_id,))  # keep job_id referenced


def test_reschedule_puts_it_back_in_the_future(conn):
    job_id = _enqueue(conn)
    leasing.lease_one(conn, "w1")
    leasing.reschedule(conn, job_id, 30, "transient error")
    row = conn.execute(
        "SELECT status, run_after > now(), last_error FROM jobs WHERE id = %s", (job_id,)
    ).fetchone()
    assert row == ("queued", True, "transient error")
    assert leasing.lease_one(conn, "w1") is None  # not due yet


def test_mark_done_and_failed(conn):
    a, b = _enqueue(conn), _enqueue(conn)
    leasing.mark_done(conn, a)
    leasing.mark_failed(conn, b, "gave up")
    states = dict(conn.execute("SELECT id, status FROM jobs").fetchall())
    assert states[a] == "done"
    assert states[b] == "failed"
