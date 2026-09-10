"""One connection pool for the process.

Postgres is the database *and* the job queue (PRD §16, T9) — one fewer service to
run, and fine at 10k users. The pool is small: the API is I/O-bound on Postgres and
OpenAI, not CPU-bound, so a handful of connections per replica is plenty.
"""

from __future__ import annotations

from psycopg_pool import ConnectionPool

from .settings import Settings

# A statement that hangs past this is a failure, not a slow success. The /health
# database check uses a tighter budget still (1s) and measures elapsed time.
_STATEMENT_TIMEOUT_MS = 5_000


def make_pool(settings: Settings) -> ConnectionPool:
    return ConnectionPool(
        conninfo=settings.database_url,
        min_size=1,
        max_size=10,
        kwargs={
            "connect_timeout": 5,
            "options": f"-c statement_timeout={_STATEMENT_TIMEOUT_MS}",
        },
        open=True,
    )
