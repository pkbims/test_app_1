"""Unit tests for the three-state health check. No database — fakes only."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import pytest

from app import health
from app.schemas import HealthCheck, HealthState


# ── fakes ────────────────────────────────────────────────────────────────────
class FakeCursor:
    def __init__(self, rows: list[tuple]) -> None:
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def __iter__(self):
        return iter(self._rows)


class FakeConn:
    def __init__(
        self, rows: list[tuple] | None = None, exc: Exception | None = None, delay: float = 0.0
    ) -> None:
        self._rows = rows or []
        self._exc = exc
        self._delay = delay
        self.queries: list[str] = []

    def execute(self, query: str, params: object = None):
        self.queries.append(query)
        if self._delay:
            time.sleep(self._delay)
        if self._exc:
            raise self._exc
        return FakeCursor(self._rows)


class FakeStorage:
    def __init__(self, exc: Exception | None = None) -> None:
        self._exc = exc

    def healthcheck(self) -> None:
        if self._exc:
            raise self._exc


def chk(state: HealthState) -> HealthCheck:
    return HealthCheck(name="x", state=state)


# ── aggregation ──────────────────────────────────────────────────────────────
def test_aggregate_all_ok_is_ok():
    assert health.aggregate([chk(HealthState.ok), chk(HealthState.ok)]) is HealthState.ok


def test_aggregate_one_degraded_is_degraded():
    checks = [chk(HealthState.ok), chk(HealthState.degraded)]
    assert health.aggregate(checks) is HealthState.degraded


def test_aggregate_down_beats_degraded():
    checks = [chk(HealthState.degraded), chk(HealthState.down), chk(HealthState.ok)]
    assert health.aggregate(checks) is HealthState.down


def test_aggregate_empty_is_ok():
    assert health.aggregate([]) is HealthState.ok


@pytest.mark.parametrize(
    "state,code",
    [(HealthState.ok, 200), (HealthState.degraded, 200), (HealthState.down, 503)],
)
def test_http_status_for(state, code):
    assert health.http_status_for(state) == code


# ── pure thresholds ──────────────────────────────────────────────────────────
def test_heartbeat_state():
    assert health.heartbeat_state(10, 60) is HealthState.ok
    assert health.heartbeat_state(61, 60) is HealthState.degraded
    assert health.heartbeat_state(None, 60) is HealthState.degraded


def test_queue_depth_state():
    assert health.queue_depth_state(100, 100) is HealthState.ok
    assert health.queue_depth_state(101, 100) is HealthState.degraded


# ── individual checks ────────────────────────────────────────────────────────
def test_check_database_ok():
    c = health.check_database(FakeConn())
    assert c.state is HealthState.ok and c.name == "database"


def test_check_database_error_is_down():
    c = health.check_database(FakeConn(exc=RuntimeError("connection refused")))
    assert c.state is HealthState.down
    assert "connection refused" in c.detail


def test_check_database_slow_is_down(monkeypatch):
    monkeypatch.setattr(health, "DB_BUDGET_S", 0.05)
    c = health.check_database(FakeConn(delay=0.12))
    assert c.state is HealthState.down
    assert "budget" in c.detail


def test_check_photo_storage_ok():
    assert health.check_photo_storage(FakeStorage()).state is HealthState.ok


def test_check_photo_storage_error_is_down():
    c = health.check_photo_storage(FakeStorage(exc=OSError("disk full")))
    assert c.state is HealthState.down and "disk full" in c.detail


def test_check_queue_ok():
    assert health.check_queue(FakeConn()).state is HealthState.ok


def test_check_queue_missing_table_is_down():
    c = health.check_queue(FakeConn(exc=RuntimeError('relation "jobs" does not exist')))
    assert c.state is HealthState.down


def test_check_worker_heartbeat_fresh_is_ok():
    now = datetime.now(UTC)
    conn = FakeConn(rows=[(now - timedelta(seconds=5),)])
    assert health.check_worker_heartbeat(conn, 60, now=now).state is HealthState.ok


def test_check_worker_heartbeat_stale_is_degraded():
    now = datetime.now(UTC)
    conn = FakeConn(rows=[(now - timedelta(seconds=120),)])
    c = health.check_worker_heartbeat(conn, 60, now=now)
    assert c.state is HealthState.degraded and "120s ago" in c.detail


def test_check_worker_heartbeat_never_is_degraded():
    c = health.check_worker_heartbeat(FakeConn(rows=[(None,)]), 60)
    assert c.state is HealthState.degraded
    assert "worker" in c.detail


def test_check_queue_depth_ok():
    assert health.check_queue_depth(FakeConn(rows=[(3,)]), 100).state is HealthState.ok


def test_check_queue_depth_over_threshold_is_degraded():
    c = health.check_queue_depth(FakeConn(rows=[(150,)]), 100)
    assert c.state is HealthState.degraded and "150 jobs queued" in c.detail
