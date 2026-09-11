from __future__ import annotations

import json

import pytest

from app import vision
from app.inventory.service import _letter


class _Msg:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})


class _Resp:
    def __init__(self, content):
        self.choices = [_Msg(content)]


class _FakeCompletions:
    def __init__(self, content=None, exc=None):
        self._content = content
        self._exc = exc

    def create(self, **_kwargs):
        if self._exc:
            raise self._exc
        return _Resp(self._content)


def _client_with(content=None, exc=None):
    v = vision.OpenAIVision.__new__(vision.OpenAIVision)
    v._model = "gpt-4.1"
    v._client = type(
        "C", (), {"chat": type("Ch", (), {"completions": _FakeCompletions(content, exc)})()}
    )()
    return v


# ── _letter ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "index,letter",
    [(0, "A"), (1, "B"), (25, "Z"), (26, "AA"), (27, "AB"), (51, "AZ"), (52, "BA")],
)
def test_letter(index, letter):
    assert _letter(index) == letter


# ── _coerce ──────────────────────────────────────────────────────────────────
def test_coerce_accepts_a_good_item():
    item = vision._coerce(
        {"id": "A", "kind": "Architecture", "name": "wall", "description": "the back wall"}
    )
    assert item == vision.RawItem("architecture", "wall", "the back wall")


@pytest.mark.parametrize(
    "bad",
    [
        {"kind": "furniture", "name": "x", "description": "y"},
        {"kind": "object", "name": "", "description": "y"},
        {"kind": "object", "name": "x", "description": ""},
        "not a dict",
    ],
)
def test_coerce_rejects_bad_items(bad):
    with pytest.raises(vision.VisionError):
        vision._coerce(bad)


# ── OpenAIVision ─────────────────────────────────────────────────────────────
def test_openai_vision_parses_items():
    payload = json.dumps(
        {"items": [{"kind": "architecture", "name": "wall", "description": "back wall"}]}
    )
    result = _client_with(content=payload).inventory(b"bytes", "image/jpeg")
    assert result.items == [vision.RawItem("architecture", "wall", "back wall")]


def test_openai_vision_returns_the_exact_prompt_sent():
    payload = json.dumps({"items": []})
    result = _client_with(content=payload).inventory(b"bytes", "image/jpeg")
    assert result.prompt == vision._INVENTORY_PROMPT
    assert "Inventory this room photo" in result.prompt


def test_openai_vision_wraps_api_errors():
    import openai

    with pytest.raises(vision.VisionError):
        _client_with(exc=openai.OpenAIError("upstream is down")).inventory(b"b", "image/jpeg")


def test_openai_vision_wraps_bad_json():
    with pytest.raises(vision.VisionError):
        _client_with(content="not json").inventory(b"b", "image/jpeg")


def test_openai_vision_wraps_missing_items_key():
    with pytest.raises(vision.VisionError):
        _client_with(content='{"nope": []}').inventory(b"b", "image/jpeg")


# ── room_type detection (options round, options_review/HANDOFF.md §4.2) ──────
def test_schema_lists_every_room_type_as_an_alternative():
    for room_type in vision.ROOM_TYPES:
        assert f'"{room_type}"' in vision._SCHEMA
    assert "|null}" in vision._SCHEMA


def test_item_inventory_wording_is_unchanged():
    # The instructional prose (not the schema shape) is proven and must not move.
    assert vision._INVENTORY_PROMPT.startswith(
        "Inventory this room photo. List every fixed architectural feature "
        "(walls, openings, fireplace, mantel, alcoves, ceiling features, "
        "flooring, switches) as kind=architecture, and every moveable object "
        "(furniture, decor, lamps, art, plants) as kind=object. Label them A, "
        "B, C in reading order. 'description' must be precise enough that an "
        "image model could locate it without seeing labels. "
    )


@pytest.mark.parametrize("room_type", vision.ROOM_TYPES)
def test_coerce_room_type_accepts_every_known_id(room_type):
    assert vision._coerce_room_type(room_type) == room_type


def test_coerce_room_type_is_case_insensitive():
    assert vision._coerce_room_type("Living_Room") == "living_room"


@pytest.mark.parametrize("bad", [None, "", "garage", "LIVING ROOM", 42])
def test_coerce_room_type_degrades_to_none_rather_than_erroring(bad):
    assert vision._coerce_room_type(bad) is None


def test_openai_vision_parses_room_type():
    payload = json.dumps({"items": [], "room_type": "bedroom"})
    result = _client_with(content=payload).inventory(b"bytes", "image/jpeg")
    assert result.room_type == "bedroom"


def test_openai_vision_room_type_absent_is_none_not_an_error():
    payload = json.dumps({"items": []})
    result = _client_with(content=payload).inventory(b"bytes", "image/jpeg")
    assert result.room_type is None


def test_openai_vision_unknown_room_type_degrades_to_none():
    payload = json.dumps({"items": [], "room_type": "garage"})
    result = _client_with(content=payload).inventory(b"bytes", "image/jpeg")
    assert result.room_type is None


# ── FakeVision ───────────────────────────────────────────────────────────────
def test_fake_vision_has_architecture_and_objects():
    result = vision.FakeVision().inventory(b"", "image/jpeg")
    kinds = {i.kind for i in result.items}
    assert kinds == {"architecture", "object"}


def test_fake_vision_returns_a_room_type():
    result = vision.FakeVision().inventory(b"", "image/jpeg")
    assert result.room_type in vision.ROOM_TYPES


def test_fake_vision_returns_the_real_inventory_prompt():
    # No call is actually made, but the stored text should be what a real call
    # would send, so it's meaningful to review later.
    result = vision.FakeVision().inventory(b"", "image/jpeg")
    assert result.prompt == vision._INVENTORY_PROMPT


def test_disabled_vision_raises():
    with pytest.raises(vision.VisionError):
        vision.DisabledVision().inventory(b"", "image/jpeg")


# ── preservation_check prompts ────────────────────────────────────────────────
def test_preservation_prompt_names_every_architecture_item():
    architecture = [("A", "the back wall"), ("B", "the flooring")]
    result = vision.FakeVision().preservation_check(b"", architecture)
    assert "A: the back wall" in result.prompt
    assert "B: the flooring" in result.prompt


def test_preservation_prompt_is_empty_when_nothing_architectural():
    result = vision.FakeVision().preservation_check(b"", [])
    assert result.prompt == ""


def test_openai_preservation_check_returns_the_exact_prompt_sent():
    payload = json.dumps({"present": ["A"]})
    architecture = [("A", "the back wall")]
    result = _client_with(content=payload).preservation_check(b"after-bytes", architecture)
    assert result.prompt == vision._preservation_prompt(architecture)
    assert "A: the back wall" in result.prompt
