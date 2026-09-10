from __future__ import annotations

import os

import pytest


@pytest.fixture
def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set — integration test needs a real Postgres")
    return url


@pytest.fixture
def pg_url(database_url: str):
    """A freshly created scratch database, dropped afterwards.

    Integration tests get their own database so migrations and fixtures never
    collide with the dev data in `app1`.
    """
    import psycopg

    admin = psycopg.connect(database_url, autocommit=True)
    scratch = f"app1_test_{os.getpid()}"
    admin.execute(f'DROP DATABASE IF EXISTS "{scratch}"')
    admin.execute(f'CREATE DATABASE "{scratch}"')
    try:
        yield _swap_db(database_url, scratch)
    finally:
        admin.execute(f'DROP DATABASE IF EXISTS "{scratch}"')
        admin.close()


@pytest.fixture
def pg_conn(pg_url: str):
    import psycopg

    conn = psycopg.connect(pg_url)
    try:
        yield conn
    finally:
        conn.close()


def _swap_db(url: str, name: str) -> str:
    head, _, _tail = url.rpartition("/")
    return f"{head}/{name}"
