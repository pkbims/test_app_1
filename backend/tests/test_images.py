from __future__ import annotations

import io

import pytest
from PIL import Image

from app.images import UnsupportedImage, inspect


def _encode(fmt: str, size=(640, 480)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (120, 90, 60)).save(buf, format=fmt)
    return buf.getvalue()


def test_reads_jpeg():
    info = inspect(_encode("JPEG", (800, 600)))
    assert info.content_type == "image/jpeg"
    assert info.ext == "jpg"
    assert (info.width, info.height) == (800, 600)


def test_reads_png():
    info = inspect(_encode("PNG", (321, 123)))
    assert info.content_type == "image/png"
    assert (info.width, info.height) == (321, 123)


def test_rejects_heic_magic():
    heic = b"\x00\x00\x00\x18ftypheic" + b"\x00" * 64
    with pytest.raises(UnsupportedImage):
        inspect(heic)


def test_rejects_gif():
    with pytest.raises(UnsupportedImage):
        inspect(_encode("GIF"))


def test_rejects_plain_text():
    with pytest.raises(UnsupportedImage):
        inspect(b"this is not an image at all")


def test_rejects_truncated_jpeg():
    data = _encode("JPEG")
    with pytest.raises(UnsupportedImage):
        inspect(data[:64])
