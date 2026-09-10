"""The three-state health check (PRD §17).

`down` blocks a deploy, `degraded` pages someone, `ok` does nothing. A check that
only says yes/no makes every wobble look like an outage and people stop trusting
it — hence the middle state for "still serving, but someone should look".

Every check function is pure given its inputs (a connection, a storage handle),
so the logic is unit-tested with fakes; the real SQL is covered by an integration
test against Postgres.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Protocol

from .schemas import Health, HealthCheck, HealthState

# The database check's own budget. Slower than this and we call it `down` even if
# the query eventually returns — a 3-second `SELECT 1` is an outage in progress.
DB_BUDGET_S = 1.0

_RANK = {HealthState.ok: 0, HealthState.degraded: 1, HealthState.down: 2}


class _Conn(Protocol):
    def execute(self, query: str, params: object = ..., /) -> object: ...


class _Storage(Protocol):
    def healthcheck(self) -> None: ...


# ── aggregation ──────────────────────────────────────────────────────────────
def aggregate(checks: list[HealthCheck]) -> HealthState:
    worst = HealthState.ok
    for c in checks:
        if _RANK[c.state] > _RANK[worst]:
            worst = c.state
    return worst


def http_status_for(state: HealthState) -> int:
    """`down` → 503 so load balancers and deploy gates react. Otherwise 200."""
    return 503 if state is HealthState.down else 200


# ── pure threshold helpers ───────────────────────────────────────────────────
def heartbeat_state(age_seconds: float | None, timeout_s: float) -> HealthState:
    if age_seconds is None or age_seconds > timeout_s:
        return HealthState.degraded
    return HealthState.ok


def queue_depth_state(depth: int, threshold: int) -> HealthState:
    return HealthState.degraded if depth > threshold else HealthState.ok


# ── individual checks ────────────────────────────────────────────────────────
def check_database(conn: _Conn) -> HealthCheck:
    start = time.perf_counter()
    try:
        conn.execute("SELECT 1")
    except Exception as exc:  # noqa: BLE001 — any failure is `down`
        return HealthCheck(name="database", state=HealthState.down, detail=_msg(exc))
    elapsed = time.perf_counter() - start
    if elapsed > DB_BUDGET_S:
        return HealthCheck(
            name="database",
            state=HealthState.down,
            detail=f"SELECT 1 took {elapsed:.2f}s (budget {DB_BUDGET_S:.0f}s)",
        )
    return HealthCheck(name="database", state=HealthState.ok)


def check_photo_storage(storage: _Storage) -> HealthCheck:
    try:
        storage.healthcheck()
    except Exception as exc:  # noqa: BLE001
        return HealthCheck(name="photo_storage", state=HealthState.down, detail=_msg(exc))
    return HealthCheck(name="photo_storage", state=HealthState.ok)


def check_queue(conn: _Conn) -> HealthCheck:
    try:
        conn.execute("SELECT 1 FROM jobs LIMIT 1")
    except Exception as exc:  # noqa: BLE001
        return HealthCheck(name="queue", state=HealthState.down, detail=_msg(exc))
    return HealthCheck(name="queue", state=HealthState.ok)


def check_worker_heartbeat(
    conn: _Conn, timeout_s: float, now: datetime | None = None
) -> HealthCheck:
    now = now or datetime.now(UTC)
    try:
        row = conn.execute("SELECT max(last_seen) FROM worker_heartbeats").fetchone()  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        return HealthCheck(name="worker_heartbeat", state=HealthState.down, detail=_msg(exc))
    last = row[0] if row else None
    age = None if last is None else (now - last).total_seconds()
    state = heartbeat_state(age, timeout_s)
    if age is None:
        detail = "no worker has ever checked in"
    elif state is HealthState.degraded:
        detail = f"last worker heartbeat {age:.0f}s ago (timeout {timeout_s:.0f}s)"
    else:
        detail = None
    return HealthCheck(name="worker_heartbeat", state=state, detail=detail)


def check_queue_depth(conn: _Conn, threshold: int) -> HealthCheck:
    try:
        row = conn.execute("SELECT count(*) FROM jobs WHERE status = 'queued'").fetchone()  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        return HealthCheck(name="queue_depth", state=HealthState.down, detail=_msg(exc))
    depth = int(row[0])
    state = queue_depth_state(depth, threshold)
    detail = f"{depth} jobs queued" if state is HealthState.degraded else None
    return HealthCheck(name="queue_depth", state=state, detail=detail)


# ── orchestration ────────────────────────────────────────────────────────────
def build_health(
    *,
    pool,
    storage: _Storage,
    queue_depth_threshold: int,
    heartbeat_timeout_s: float,
) -> Health:
    checks: list[HealthCheck] = [check_photo_storage(storage)]
    try:
        with pool.connection() as conn:
            checks.append(check_database(conn))
            checks.append(check_queue(conn))
            checks.append(check_worker_heartbeat(conn, heartbeat_timeout_s))
            checks.append(check_queue_depth(conn, queue_depth_threshold))
    except Exception as exc:  # noqa: BLE001 — no connection at all
        checks.append(HealthCheck(name="database", state=HealthState.down, detail=_msg(exc)))
        checks.append(HealthCheck(name="queue", state=HealthState.down, detail="no connection"))
    return Health(state=aggregate(checks), checks=checks)


def _msg(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"[:200]
