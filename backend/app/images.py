"""Validate an uploaded photo: JPEG or PNG only, and read its dimensions.

HEIC is what iPhones shoot by default and the image API rejects it, so the client
converts to JPEG before upload; anything that is not JPEG or PNG is refused here
with `photo_unsupported`. We sniff the magic bytes *and* decode with Pillow — a
file that is named right but is not actually an image is still rejected.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image

_MAGIC: tuple[tuple[bytes, str, str], ...] = (
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
)


@dataclass(frozen=True)
class ImageInfo:
    content_type: str
    width: int
    height: int
    ext: str


class UnsupportedImage(Exception):
    """Not a JPEG or PNG, or not a readable image at all."""


def inspect(data: bytes) -> ImageInfo:
    match = next(((ct, ext) for magic, ct, ext in _MAGIC if data.startswith(magic)), None)
    if match is None:
        raise UnsupportedImage("not a JPEG or PNG")
    content_type, ext = match

    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()  # catches truncation / corruption; consumes the object
        with Image.open(io.BytesIO(data)) as im:
            width, height = im.size
            fmt = (im.format or "").lower()
    except Exception as exc:  # noqa: BLE001 — Pillow raises a zoo of types
        raise UnsupportedImage(f"unreadable image: {exc}") from exc

    if fmt not in ("jpeg", "png"):
        raise UnsupportedImage(f"decoded as {fmt or 'unknown'}, not jpeg/png")
    return ImageInfo(content_type=content_type, width=width, height=height, ext=ext)
