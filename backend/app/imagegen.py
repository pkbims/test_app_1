"""The image edit call (`gpt-image-2`, `/v1/images/edits`).

No mask — masking was tested in the spike and does not preserve the masked region
(HANDOFF.md). Preservation comes from the prompt naming every architectural item
verbatim. Output is a fixed 1536x1024 and is never pixel-aligned with the input.
"""

from __future__ import annotations

import io
from typing import Protocol

EDIT_MODEL = "gpt-image-2"
EDIT_SIZE = "1536x1024"


class ImageEditError(Exception):
    """The edit call failed. Retryable unless we've run out of attempts."""


class ImageEditor(Protocol):
    def edit(self, image_bytes: bytes, content_type: str, prompt: str) -> bytes:
        """Return PNG bytes of the restyled room."""


class OpenAIImageEditor:
    def __init__(self, api_key: str, *, model: str = EDIT_MODEL, timeout: float = 180.0):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, timeout=timeout, max_retries=0)
        self._model = model

    def edit(self, image_bytes: bytes, content_type: str, prompt: str) -> bytes:
        import base64

        import openai

        ext = "png" if content_type == "image/png" else "jpg"
        try:
            resp = self._client.images.edit(
                model=self._model,
                image=(f"room.{ext}", io.BytesIO(image_bytes), content_type),
                prompt=prompt,
                size=EDIT_SIZE,
            )
            b64 = resp.data[0].b64_json if resp.data else None
            if not b64:
                raise ImageEditError("no image in response")
            return base64.b64decode(b64)
        except (openai.OpenAIError, ValueError) as exc:
            raise ImageEditError(f"{type(exc).__name__}: {exc}") from exc


class FakeImageEditor:
    """Deterministic 1536x1024 PNG for local compose and integration tests."""

    def edit(self, image_bytes: bytes, content_type: str, prompt: str) -> bytes:
        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (1536, 1024), (222, 216, 208)).save(buf, format="PNG")
        return buf.getvalue()


class DisabledImageEditor:
    def edit(self, image_bytes: bytes, content_type: str, prompt: str) -> bytes:
        raise ImageEditError(
            "image editing not configured — set OPENAI_API_KEY or VISION_BACKEND=fake"
        )
