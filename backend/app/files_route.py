"""Serves photo and render-image bytes for a signed URL.

Not part of the contract — `include_in_schema=False` keeps it out of
`openapi.json` (ORCH-QUESTIONS Q1). The client only ever loads a URL it was
handed in a `Photo` or `Render` response.
"""

from __future__ import annotations

from fastapi import APIRouter, Response

from . import files as files_mod
from . import runtime
from .errors import ApiError
from .schemas import ErrorCode

router = APIRouter(include_in_schema=False)

_MEDIA = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}
_NOT_FOUND = "That link has expired or is not valid."


@router.get("/files/{scope}/{key:path}")
def get_file(scope: str, key: str, exp: int = 0, sig: str = "") -> Response:
    rt = runtime.get()
    if not files_mod.verify(scope, key, exp, sig, rt.settings.file_url_secret):
        raise ApiError(ErrorCode.not_found, _NOT_FOUND)
    try:
        data = rt.storage.get(f"{scope}/{key}")
    except (FileNotFoundError, ValueError) as exc:
        raise ApiError(ErrorCode.not_found, _NOT_FOUND) from exc
    media_type = _MEDIA.get(key.rsplit(".", 1)[-1].lower(), "application/octet-stream")
    return Response(
        content=data,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=86400"},
    )
