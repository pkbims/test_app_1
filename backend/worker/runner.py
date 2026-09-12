"""Lease and run a single job. The loop in `__main__` calls this; tests call it
directly. Dispatches on `lease.kind` — `render_job` or `shopping_job`."""

from __future__ import annotations

from app.imagegen import ImageEditor
from app.shopping.judge import ShoppingModel
from app.shopping.pipeline import ShoppingConfig
from app.shopping.searchapi import SearchApi
from app.vision import Vision

from . import render_job, shopping_job
from .leasing import lease_one


def run_one(
    conn, storage, vision: Vision, editor: ImageEditor, worker: str,
    *,
    shopping_model: ShoppingModel | None = None,
    shopping_searchapi: SearchApi | None = None,
    shopping_config: ShoppingConfig | None = None,
) -> str | None:
    """Returns the outcome string, or None if there was no job to run."""
    lease = lease_one(conn, worker)
    if lease is None:
        return None
    if lease.kind == "shopping":
        return shopping_job.run(conn, storage, shopping_model, shopping_searchapi, shopping_config, lease)
    return render_job.run(conn, storage, vision, editor, lease)
