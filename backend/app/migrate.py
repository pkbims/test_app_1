"""Forward-only SQL migrations, run on startup.

**Why plain SQL files, not Alembic.** Alembic buys autogeneration and downgrades.
We want neither: the schema is small, every change is reviewed by hand anyway, and
"downgrade in production" is a fantasy — you roll forward with a fix. What is left
after removing those is a numbered list of `.sql` files and a table recording which
have run, which is what this is. The cost: no autogenerate (you write the DDL), and
ordering is your responsibility (hence the numeric prefix).

All pending migrations run inside a single transaction under a Postgres advisory
lock, so several processes booting at once (api + worker) is safe, and a failure
half-way leaves the schema untouched.
"""

from __future__ import annotations

import pathlib

from psycopg import Connection

_MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent.parent / "migrations"
_LOCK_KEY = 917_110_001  # arbitrary, stable — identifies "the app_1 migration lock"


def apply_all(conn: Connection, migrations_dir: pathlib.Path | None = None) -> list[str]:
    """Apply every migration not yet recorded. Returns the versions applied."""
    directory = migrations_dir or _MIGRATIONS_DIR
    conn.autocommit = True
    applied: list[str] = []

    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (_LOCK_KEY,))
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version    text PRIMARY KEY,
                applied_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        done = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
        for path in sorted(directory.glob("*.sql")):
            if path.name in done:
                continue
            conn.execute(path.read_text())
            conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.name,))
            applied.append(path.name)

    return applied
