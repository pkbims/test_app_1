from __future__ import annotations

import pytest

from app.migrate import apply_all

pytestmark = pytest.mark.integration


def test_applies_all_migrations_once(pg_conn):
    applied = apply_all(pg_conn)
    assert "001_init.sql" in applied

    # Tables the health check needs now exist.
    tables = {
        r[0]
        for r in pg_conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
        )
    }
    assert {"schema_migrations", "worker_heartbeats", "jobs"} <= tables


def test_is_idempotent(pg_conn):
    apply_all(pg_conn)
    assert apply_all(pg_conn) == []


def test_records_versions(pg_conn):
    apply_all(pg_conn)
    versions = {r[0] for r in pg_conn.execute("SELECT version FROM schema_migrations")}
    assert "001_init.sql" in versions
