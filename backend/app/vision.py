"""The vision calls (`gpt-4.1`): the room inventory, and later the preservation
check. This is the mechanism the product depends on (HANDOFF.md).

The inventory prompt and JSON schema are reused **verbatim** from
`spike/identify.py` — that exact wording was proven on a real room. We re-letter
the items ourselves afterwards so the ids are always A, B, ... AA, AB and never
skip or collide, whatever the model returns.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Protocol

INVENTORY_MODEL = "gpt-4.1"

# --- verbatim from spike/identify.py ---------------------------------------------
_SCHEMA = """Return JSON only:
{"items":[{"id":"A","kind":"architecture"|"object","name":"short name for a user",
"description":"precise visual description with position, for an image model"}]}"""

_INVENTORY_PROMPT = (
    "Inventory this room photo. List every fixed architectural feature (walls, "
    "openings, fireplace, mantel, alcoves, ceiling features, flooring, switches) "
    "as kind=architecture, and every moveable object (furniture, decor, lamps, "
    "art, plants) as kind=object. Label them A, B, C in reading order. "
    "'description' must be precise enough that an image model could locate it "
    "without seeing labels. " + _SCHEMA
)
# ------------------------------------------------------------------------------


@dataclass(frozen=True)
class RawItem:
    kind: str  # "architecture" | "object"
    name: str
    description: str


class VisionError(Exception):
    """The vision call failed, or returned something we can't use."""


class Vision(Protocol):
    def inventory(self, image_bytes: bytes, content_type: str) -> list[RawItem]: ...


class OpenAIVision:
    def __init__(self, api_key: str, *, model: str = INVENTORY_MODEL, timeout: float = 120.0):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, timeout=timeout, max_retries=1)
        self._model = model

    def inventory(self, image_bytes: bytes, content_type: str) -> list[RawItem]:
        import openai

        data_uri = f"data:{content_type};base64,{base64.b64encode(image_bytes).decode()}"
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": _INVENTORY_PROMPT},
                            {"type": "image_url", "image_url": {"url": data_uri}},
                        ],
                    }
                ],
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content or ""
            items = json.loads(content)["items"]
        except (openai.OpenAIError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise VisionError(f"{type(exc).__name__}: {exc}") from exc
        return [_coerce(item) for item in items]


class FakeVision:
    """Deterministic stand-in for local `docker compose` and integration tests
    (`VISION_BACKEND=fake`). Not a real inventory — just a plausible one."""

    def inventory(self, image_bytes: bytes, content_type: str) -> list[RawItem]:
        return [
            RawItem(
                "architecture", "back wall", "White painted back wall spanning the whole frame."
            ),
            RawItem(
                "architecture", "flooring", "Mid-tone wood-plank flooring across the visible floor."
            ),
            RawItem(
                "architecture", "window", "Tall window on the left wall, to the left of centre."
            ),
            RawItem("object", "sofa", "Grey three-seat sofa against the back wall, centred."),
            RawItem(
                "object",
                "coffee table",
                "Low rectangular wooden coffee table in front of the sofa.",
            ),
            RawItem("object", "floor lamp", "Slim black floor lamp in the right-hand corner."),
        ]


class DisabledVision:
    def inventory(self, image_bytes: bytes, content_type: str) -> list[RawItem]:
        raise VisionError("vision not configured — set OPENAI_API_KEY or VISION_BACKEND=fake")


def _coerce(item: object) -> RawItem:
    if not isinstance(item, dict):
        raise VisionError("item is not an object")
    kind = str(item.get("kind", "")).lower()
    if kind not in ("architecture", "object"):
        raise VisionError(f"unexpected kind {kind!r}")
    name = str(item.get("name", "")).strip()
    description = str(item.get("description", "")).strip()
    if not name or not description:
        raise VisionError("item missing name or description")
    return RawItem(kind=kind, name=name, description=description)
