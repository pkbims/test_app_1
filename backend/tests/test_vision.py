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


# ── FakeVision ───────────────────────────────────────────────────────────────
def test_fake_vision_has_architecture_and_objects():
    result = vision.FakeVision().inventory(b"", "image/jpeg")
    kinds = {i.kind for i in result.items}
    assert kinds == {"architecture", "object"}


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
