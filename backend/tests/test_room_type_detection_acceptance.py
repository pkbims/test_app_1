"""Room type detection, proven against a real vision call (options round,
options_review/HANDOFF.md §4.2, §4.9 "render-level" tier applied to detection).

`/inputs/room.jpg` (the known room used throughout the render-level suite) is a
living room — a fireplace, TV and stand, mantel decor. This is the one test that
proves gpt-4.1 actually returns a usable `room_type`, not just that the code
shape parses one. Skipped unless OPENAI_API_KEY is set and the sample photo is
mounted, same as the other opt-in tests.
"""

from __future__ import annotations

import os
import pathlib

import pytest

pytestmark = pytest.mark.integration

_SAMPLE = pathlib.Path("/inputs/room.jpg")


@pytest.fixture
def api_key():
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        pytest.skip("no OPENAI_API_KEY")
    if not _SAMPLE.is_file():
        pytest.skip("sample photo /inputs/room.jpg not mounted")
    return key


def test_real_vision_call_detects_the_room_type(api_key):
    from app.vision import OpenAIVision

    result = OpenAIVision(api_key).inventory(_SAMPLE.read_bytes(), "image/jpeg")
    assert result.room_type == "living_room"
