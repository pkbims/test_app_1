"""Path-id parsing shared by rooms, inventory and renders.

A malformed id is treated exactly like an unknown one — a 404 `not_found`, no
existence leak (ORCH-QUESTIONS Q2). Parsing in Python also keeps a bad string from
reaching Postgres and aborting the transaction.
"""

from __future__ import annotations

import uuid

from .errors import ApiError
from .schemas import ErrorCode


def parse_uuid(raw: str, not_found_message: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise ApiError(ErrorCode.not_found, not_found_message) from exc
