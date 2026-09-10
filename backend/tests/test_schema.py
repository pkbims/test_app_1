"""The domain schema (build-order step 2 / PRD §15), checked against real Postgres.

These lean on database constraints on purpose — "one photo per room", "credits are
a ledger", "a render is deduped per idempotency key" are rules the schema itself
should enforce, not just the app.
"""

from __future__ import annotations

import uuid

import psycopg
import pytest

from app.migrate import apply_all

pytestmark = pytest.mark.integration


@pytest.fixture
def conn(pg_conn):
    apply_all(pg_conn)
    return pg_conn


def _tables(conn) -> set[str]:
    return {
        r[0]
        for r in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
        )
    }


def test_all_domain_tables_exist(conn):
    assert {
        "users",
        "rooms",
        "photos",
        "inventories",
        "renders",
        "credit_ledger",
        "jobs",
    } <= _tables(conn)


def _new_user(conn) -> uuid.UUID:
    return conn.execute(
        "INSERT INTO users (apple_sub) VALUES (%s) RETURNING id", (uuid.uuid4().hex,)
    ).fetchone()[0]


def _new_room(conn, user_id) -> uuid.UUID:
    return conn.execute(
        "INSERT INTO rooms (user_id, label) VALUES (%s, 'Living room') RETURNING id",
        (user_id,),
    ).fetchone()[0]


def test_one_photo_per_room(conn):
    room = _new_room(conn, _new_user(conn))
    ins = (
        "INSERT INTO photos (room_id, storage_key, content_type, width, height, byte_size) "
        "VALUES (%s, %s, 'image/jpeg', 100, 100, 1234)"
    )
    conn.execute(ins, (room, "a"))
    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute(ins, (room, "b"))


def test_inventory_is_one_row_per_room_and_upserts(conn):
    room = _new_room(conn, _new_user(conn))
    conn.execute(
        "INSERT INTO inventories (room_id, items) VALUES (%s, %s::jsonb)",
        (room, '[{"id": "A"}]'),
    )
    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute(
            "INSERT INTO inventories (room_id, items) VALUES (%s, %s::jsonb)",
            (room, "[]"),
        )


def test_render_is_deduped_per_user_idempotency_key(conn):
    user = _new_user(conn)
    room = _new_room(conn, user)
    ins = (
        "INSERT INTO renders (room_id, user_id, style, idempotency_key) "
        "VALUES (%s, %s, 'warm-minimal', 'key-1')"
    )
    conn.execute(ins, (room, user))
    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute(ins, (room, user))


def test_credit_ledger_sums_to_balance(conn):
    user = _new_user(conn)
    for delta, reason in [(1, "signup_grant"), (-1, "render_spend"), (1, "render_refund")]:
        conn.execute(
            "INSERT INTO credit_ledger (user_id, delta, reason) VALUES (%s, %s, %s)",
            (user, delta, reason),
        )
    balance = conn.execute(
        "SELECT coalesce(sum(delta), 0) FROM credit_ledger WHERE user_id = %s", (user,)
    ).fetchone()[0]
    assert balance == 1


def test_deleting_a_room_cascades_to_photos_and_renders(conn):
    user = _new_user(conn)
    room = _new_room(conn, user)
    conn.execute(
        "INSERT INTO photos (room_id, storage_key, content_type, width, height, byte_size) "
        "VALUES (%s, 'k', 'image/png', 10, 10, 9)",
        (room,),
    )
    conn.execute(
        "INSERT INTO renders (room_id, user_id, style, idempotency_key) VALUES (%s, %s, 's', 'k')",
        (room, user),
    )
    conn.execute("DELETE FROM rooms WHERE id = %s", (room,))
    assert conn.execute("SELECT count(*) FROM photos").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM renders").fetchone()[0] == 0


def test_jobs_render_id_references_renders(conn):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        conn.execute("INSERT INTO jobs (render_id) VALUES (%s)", (uuid.uuid4(),))
