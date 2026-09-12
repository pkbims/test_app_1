from __future__ import annotations

import json

import pytest

from app.shopping import judge


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


def _model_with(content=None, exc=None):
    m = judge.OpenAIShoppingModel.__new__(judge.OpenAIShoppingModel)
    m._describe_model = "gpt-4.1-mini"
    m._judge_model = "gpt-4.1"
    m._client = type(
        "C", (), {"chat": type("Ch", (), {"completions": _FakeCompletions(content, exc)})()}
    )()
    return m


# ── _valid_cells ─────────────────────────────────────────────────────────────
def test_valid_cells_accepts_and_upcases():
    assert judge._valid_cells(["b2", "C3"]) == ["B2", "C3"]


@pytest.mark.parametrize("bad", [None, [], "B2", [1, 2], ["2B"], ["BB"], ["B"]])
def test_valid_cells_rejects_bad_shapes(bad):
    assert judge._valid_cells(bad) is None


# ── describe ─────────────────────────────────────────────────────────────────
def test_describe_parses_items():
    payload = json.dumps(
        {
            "new_items": [
                {"name": "Olive tree", "where": "left", "visual": "a tall tree", "query": "olive tree",
                 "cells": ["B2", "B3"]}
            ],
            "removed_items_visible": ["side table"],
        }
    )
    result = _model_with(content=payload).describe(b"img", [], [])
    assert result.items == [
        judge.DescribedItem("Olive tree", "left", "a tall tree", "olive tree", ["B2", "B3"])
    ]
    assert result.removed_items_visible == ["side table"]


def test_describe_skips_items_missing_required_fields_rather_than_failing():
    payload = json.dumps(
        {
            "new_items": [
                {"name": "", "visual": "x", "cells": ["B2"]},  # blank name
                {"name": "ok", "visual": "y", "cells": ["B2"]},  # valid
                {"name": "bad cells", "visual": "z", "cells": []},  # no cells
            ]
        }
    )
    result = _model_with(content=payload).describe(b"img", [], [])
    assert [i.name for i in result.items] == ["ok"]


def test_describe_wraps_api_errors():
    import openai

    with pytest.raises(judge.ShoppingModelError):
        _model_with(exc=openai.OpenAIError("down")).describe(b"img", [], [])


def test_describe_wraps_bad_json():
    with pytest.raises(judge.ShoppingModelError):
        _model_with(content="not json").describe(b"img", [], [])


def test_describe_kept_and_removed_are_in_the_prompt():
    prompt = judge._describe_prompt([("sofa", "a grey sofa")], ["side table"])
    assert "- sofa: a grey sofa" in prompt
    assert "- side table" in prompt


def test_describe_empty_kept_and_removed_render_as_none():
    prompt = judge._describe_prompt([], [])
    assert prompt.count("- (none)") == 2


# ── refine ───────────────────────────────────────────────────────────────────
def test_refine_returns_cells():
    payload = json.dumps({"cells": ["a1", "a2"]})
    assert _model_with(content=payload).refine(b"img", "olive tree", "a tall tree") == ["A1", "A2"]


def test_refine_returns_none_on_api_error_instead_of_raising():
    import openai

    result = _model_with(exc=openai.OpenAIError("down")).refine(b"img", "n", "v")
    assert result is None


def test_refine_returns_none_on_bad_json():
    assert _model_with(content="not json").refine(b"img", "n", "v") is None


def test_refine_returns_none_when_cells_are_malformed():
    assert _model_with(content=json.dumps({"cells": []})).refine(b"img", "n", "v") is None


# ── judge ────────────────────────────────────────────────────────────────────
def _cand(index, **kw):
    defaults = dict(store="walmart.ca", title="Some product", price=10.0, thumbnail_b64=None)
    defaults.update(kw)
    return judge.JudgeCandidate(index=index, **defaults)


def test_judge_parses_scores():
    payload = json.dumps({"scores": [{"index": 0, "score": 5}, {"index": 1, "score": 2}]})
    scores = _model_with(content=payload).judge(b"crop", "olive tree", "a tall tree", [_cand(0), _cand(1)])
    assert scores == {0: 5, 1: 2}


def test_judge_with_no_candidates_makes_no_call_and_returns_empty():
    m = _model_with(exc=RuntimeError("should not be called"))
    assert m.judge(b"crop", "n", "v", []) == {}


def test_judge_skips_malformed_score_entries():
    payload = json.dumps({"scores": [{"index": 0, "score": 5}, {"index": "oops"}, "not a dict"]})
    scores = _model_with(content=payload).judge(b"crop", "n", "v", [_cand(0)])
    assert scores == {0: 5}


def test_judge_wraps_api_errors():
    import openai

    with pytest.raises(judge.ShoppingModelError):
        _model_with(exc=openai.OpenAIError("down")).judge(b"crop", "n", "v", [_cand(0)])


def test_judge_prompt_marks_candidates_with_no_thumbnail():
    prompt = judge._judge_prompt("n", "v", [_cand(0, thumbnail_b64=None), _cand(1, thumbnail_b64="abc")])
    lines = prompt.splitlines()
    assert any(l.startswith("0.") and "(no image)" in l for l in lines)
    assert any(l.startswith("1.") and "(no image)" not in l for l in lines)


# ── FakeShoppingModel / DisabledShoppingModel ───────────────────────────────────
def test_fake_shopping_model_is_deterministic():
    fake = judge.FakeShoppingModel()
    a = fake.describe(b"", [], [])
    b = fake.describe(b"", [], [])
    assert a == b
    assert len(a.items) == 2
    assert fake.refine(b"", "x", "y") is not None
    assert fake.judge(b"", "x", "y", [_cand(0), _cand(1)]) == {0: 5, 1: 5}


def test_disabled_shopping_model_raises_on_everything():
    d = judge.DisabledShoppingModel()
    with pytest.raises(judge.ShoppingModelError):
        d.describe(b"", [], [])
    with pytest.raises(judge.ShoppingModelError):
        d.refine(b"", "x", "y")
    with pytest.raises(judge.ShoppingModelError):
        d.judge(b"", "x", "y", [_cand(0)])
