from __future__ import annotations

import base64
import io

import pytest
from PIL import Image

from app import imagegen


def test_fake_editor_returns_a_1536x1024_png():
    out = imagegen.FakeImageEditor().edit(b"in", "image/jpeg", "prompt")
    with Image.open(io.BytesIO(out)) as im:
        assert im.format == "PNG"
        assert im.size == (1536, 1024)


def test_disabled_editor_raises():
    with pytest.raises(imagegen.ImageEditError):
        imagegen.DisabledImageEditor().edit(b"", "image/jpeg", "p")


class _FakeImages:
    def __init__(self, b64=None, exc=None):
        self._b64, self._exc = b64, exc

    def edit(self, **_kwargs):
        if self._exc:
            raise self._exc
        return type("R", (), {"data": [type("D", (), {"b64_json": self._b64})]})


def _editor(b64=None, exc=None):
    e = imagegen.OpenAIImageEditor.__new__(imagegen.OpenAIImageEditor)
    e._model = "gpt-image-2"
    e._client = type("C", (), {"images": _FakeImages(b64, exc)})()
    return e


def test_openai_editor_decodes_b64():
    png = imagegen.FakeImageEditor().edit(b"x", "image/png", "p")
    out = _editor(b64=base64.b64encode(png).decode()).edit(b"in", "image/png", "p")
    assert out == png


def test_openai_editor_wraps_api_error():
    import openai

    with pytest.raises(imagegen.ImageEditError):
        _editor(exc=openai.OpenAIError("down")).edit(b"in", "image/jpeg", "p")


def test_openai_editor_errors_on_empty_response():
    with pytest.raises(imagegen.ImageEditError):
        _editor(b64=None).edit(b"in", "image/jpeg", "p")
