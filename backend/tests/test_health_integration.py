"""The health check against a real Postgres and a real directory."""

from __future__ import annotations

import pytest

from app import health
from app.db import make_pool
from app.migrate import apply_all
from app.schemas import HealthState
from app.settings import Settings
from app.storage import LocalDiskStorage

pytestmark = pytest.mark.integration


@pytest.fixture
def pool(pg_url):
    p = make_pool(Settings(database_url=pg_url, photo_dir="/tmp", jwt_secret="x"))
    with p.connection() as conn:
        apply_all(conn)
    try:
        yield p
    finally:
        p.close()


def test_ok_when_everything_up(pool, tmp_path):
    with pool.connection() as conn:
        conn.execute("INSERT INTO worker_heartbeats (worker, last_seen) VALUES ('w1', now())")
        conn.commit()

    report = health.build_health(
        pool=pool,
        storage=LocalDiskStorage(tmp_path),
        queue_depth_threshold=100,
        heartbeat_timeout_s=60,
    )
    assert report.state is HealthState.ok
    assert {c.name for c in report.checks} == {
        "database",
        "photo_storage",
        "queue",
        "worker_heartbeat",
        "queue_depth",
    }


def test_degraded_without_a_worker(pool, tmp_path):
    report = health.build_health(
        pool=pool,
        storage=LocalDiskStorage(tmp_path),
        queue_depth_threshold=100,
        heartbeat_timeout_s=60,
    )
    assert report.state is HealthState.degraded
    hb = next(c for c in report.checks if c.name == "worker_heartbeat")
    assert hb.state is HealthState.degraded


def test_down_when_storage_unwritable(pool):
    class Broken:
        def healthcheck(self):
            raise OSError("read-only file system")

    report = health.build_health(
        pool=pool,
        storage=Broken(),
        queue_depth_threshold=100,
        heartbeat_timeout_s=60,
    )
    assert report.state is HealthState.down
    assert health.http_status_for(report.state) == 503
