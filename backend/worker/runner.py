"""Lease and run a single job. The loop in `__main__` calls this; tests call it
directly."""

from __future__ import annotations

from app.imagegen import ImageEditor
from app.vision import Vision

from . import render_job
from .leasing import lease_one


def run_one(conn, storage, vision: Vision, editor: ImageEditor, worker: str) -> str | None:
    """Returns the outcome string, or None if there was no job to run."""
    lease = lease_one(conn, worker)
    if lease is None:
        return None
    return render_job.run(conn, storage, vision, editor, lease)
