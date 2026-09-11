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

ROOM_TYPES = (
    "living_room", "bedroom", "kitchen", "dining_room", "home_office", "kids_room",
    "nursery", "bathroom", "hallway", "studio", "workshop", "server_room",
)

# --- verbatim from spike/identify.py, except the room_type field (options round,
# options_review/HANDOFF.md §4.2) — the item-inventory wording itself is untouched.
_SCHEMA = (
    """Return JSON only:
{"items":[{"id":"A","kind":"architecture"|"object","name":"short name for a user",
"description":"precise visual description with position, for an image model"}],
"room_type":"""
    + "|".join(f'"{t}"' for t in ROOM_TYPES)
    + """|null}"""
)

_INVENTORY_PROMPT = (
    "Inventory this room photo. List every fixed architectural feature (walls, "
    "openings, fireplace, mantel, alcoves, ceiling features, flooring, switches) "
    "as kind=architecture, and every moveable object (furniture, decor, lamps, "
    "art, plants) as kind=object. Label them A, B, C in reading order. "
    "'description' must be precise enough that an image model could locate it "
    "without seeing labels. " + _SCHEMA
)
# ------------------------------------------------------------------------------


_PRESERVATION_PROMPT = (
    "This is a restyled photo of a room. The architectural features listed below "
    "were in the original and MUST still be present, in the same place and shape. "
    "For each id, decide whether it is still clearly there in this image. "
    'Return JSON only: {"present":["A"],"missing":["B"]}.\n'
)


@dataclass(frozen=True)
class RawItem:
    kind: str  # "architecture" | "object"
    name: str
    description: str


@dataclass(frozen=True)
class InventoryResult:
    items: list[RawItem]
    prompt: str  # exactly what was sent — stored so it can be reviewed later
    room_type: str | None = None  # one of ROOM_TYPES, or None if the model couldn't say


@dataclass(frozen=True)
class PreservationResult:
    preservation_rate: float  # 0..1, share of architecture items still present
    missing_ids: list[str]
    prompt: str  # exactly what was sent — "" when no call was made (no architecture)


class VisionError(Exception):
    """The vision call failed, or returned something we can't use."""


class Vision(Protocol):
    def inventory(self, image_bytes: bytes, content_type: str) -> InventoryResult: ...

    def preservation_check(
        self, after_bytes: bytes, architecture: list[tuple[str, str]]
    ) -> PreservationResult: ...


def _preservation_prompt(architecture: list[tuple[str, str]]) -> str:
    listing = "\n".join(f"{item_id}: {desc}" for item_id, desc in architecture)
    return _PRESERVATION_PROMPT + listing


class OpenAIVision:
    def __init__(self, api_key: str, *, model: str = INVENTORY_MODEL, timeout: float = 120.0):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, timeout=timeout, max_retries=1)
        self._model = model

    def inventory(self, image_bytes: bytes, content_type: str) -> InventoryResult:
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
            parsed = json.loads(content)
            items = parsed["items"]
        except (openai.OpenAIError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise VisionError(f"{type(exc).__name__}: {exc}") from exc
        return InventoryResult(
            items=[_coerce(item) for item in items],
            prompt=_INVENTORY_PROMPT,
            room_type=_coerce_room_type(parsed.get("room_type")),
        )

    def preservation_check(
        self, after_bytes: bytes, architecture: list[tuple[str, str]]
    ) -> PreservationResult:
        import openai

        if not architecture:
            return PreservationResult(1.0, [], prompt="")
        prompt = _preservation_prompt(architecture)
        data_uri = f"data:image/png;base64,{base64.b64encode(after_bytes).decode()}"
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": data_uri}},
                        ],
                    }
                ],
                response_format={"type": "json_object"},
            )
            parsed = json.loads(resp.choices[0].message.content or "")
            present = {str(x).upper() for x in parsed.get("present", [])}
        except (
            openai.OpenAIError,
            json.JSONDecodeError,
            AttributeError,
            IndexError,
            TypeError,
        ) as exc:
            raise VisionError(f"{type(exc).__name__}: {exc}") from exc
        ids = [item_id for item_id, _ in architecture]
        missing = [item_id for item_id in ids if item_id not in present]
        return PreservationResult((len(ids) - len(missing)) / len(ids), missing, prompt=prompt)


class FakeVision:
    """Deterministic stand-in for local `docker compose` and integration tests
    (`VISION_BACKEND=fake`). Not a real inventory — just a plausible one."""

    def inventory(self, image_bytes: bytes, content_type: str) -> InventoryResult:
        # Uses the real prompt constant even though no call is made, so the
        # "what did we send" record is the same text the real backend would send.
        items = [
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
        return InventoryResult(items=items, prompt=_INVENTORY_PROMPT, room_type="living_room")

    def preservation_check(
        self, after_bytes: bytes, architecture: list[tuple[str, str]]
    ) -> PreservationResult:
        prompt = _preservation_prompt(architecture) if architecture else ""
        return PreservationResult(1.0, [], prompt=prompt)


class DisabledVision:
    def inventory(self, image_bytes: bytes, content_type: str) -> InventoryResult:
        raise VisionError("vision not configured — set OPENAI_API_KEY or VISION_BACKEND=fake")

    def preservation_check(
        self, after_bytes: bytes, architecture: list[tuple[str, str]]
    ) -> PreservationResult:
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


def _coerce_room_type(value: object) -> str | None:
    """Never fails the whole inventory over this — a bad or missing guess just
    degrades to `None`, the same as the model saying it doesn't know."""
    text = str(value).strip().lower() if value is not None else ""
    return text if text in ROOM_TYPES else None
