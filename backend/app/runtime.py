"""Process-wide handles (pool, storage, settings), set up once at startup.

The frozen route signatures in `main.py` take no dependency parameters, so the
route bodies reach shared resources through this module rather than through
FastAPI's `Depends`. Keeping it in one place means tests can swap it out.
"""

from __future__ import annotations

from dataclasses import dataclass

from psycopg_pool import ConnectionPool

from .db import make_pool
from .migrate import apply_all
from .settings import Settings, load
from .storage import LocalDiskStorage, Storage


@dataclass
class Runtime:
    settings: Settings
    pool: ConnectionPool
    storage: Storage


_rt: Runtime | None = None


def get() -> Runtime:
    if _rt is None:
        raise RuntimeError("runtime not started")
    return _rt


def start(settings: Settings | None = None) -> Runtime:
    global _rt
    settings = settings or load()
    pool = make_pool(settings)
    with pool.connection() as conn:
        apply_all(conn)
    _rt = Runtime(
        settings=settings,
        pool=pool,
        storage=LocalDiskStorage(settings.photo_dir),
    )
    return _rt


def stop() -> None:
    global _rt
    if _rt is not None:
        _rt.pool.close()
        _rt = None
