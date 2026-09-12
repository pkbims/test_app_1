"""The three model calls in the shopping pipeline (shopping_proto/HANDOFF.md §5.1
steps 1, 2 and 5) — gpt-4.1-mini for describe/refine, gpt-4.1 for judge. Parallel
to `vision.py`: a `Protocol`, a real OpenAI implementation, a fake, a disabled.

The grid images these calls are given (12×8 for describe, 6×6 for refine) are
prepared by `pipeline.py`, which owns the image geometry; this file only ever
turns an already-prepared image plus some text into a parsed model answer.
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from typing import Protocol

DESCRIBE_MODEL = "gpt-4.1-mini"
JUDGE_MODEL = "gpt-4.1"

_CELL_RE = re.compile(r"^[A-Za-z]\d+$")


@dataclass(frozen=True)
class DescribedItem:
    name: str
    where: str
    visual: str
    query: str
    cells: list[str]


@dataclass(frozen=True)
class DescribeResult:
    items: list[DescribedItem]
    removed_items_visible: list[str]


@dataclass(frozen=True)
class JudgeCandidate:
    index: int
    store: str
    title: str
    price: float
    thumbnail_b64: str | None  # already fetched and encoded, or None if unavailable


class ShoppingModelError(Exception):
    """A model call failed outright, or its answer could not be used at all."""


class ShoppingModel(Protocol):
    def describe(
        self, grid_image: bytes, kept: list[tuple[str, str]], removed: list[str]
    ) -> DescribeResult: ...

    def refine(self, fine_grid_image: bytes, name: str, visual: str) -> list[str] | None: ...

    def judge(
        self, crop_image: bytes, name: str, visual: str, candidates: list[JudgeCandidate]
    ) -> dict[int, int]: ...


def _describe_prompt(kept: list[tuple[str, str]], removed: list[str]) -> str:
    kept_text = "\n".join(f"- {name}: {desc}" for name, desc in kept) or "- (none)"
    removed_text = "\n".join(f"- {name}" for name in removed) or "- (none)"
    return (
        "This is an AI-restyled photo of a room with a labelled grid drawn over it "
        "(rows A-H top to bottom, columns 1-12 left to right; each cell is labelled "
        "at its top-left corner).\n\n"
        "The customer KEPT these items (same objects, same places, maybe a new finish):\n"
        f"{kept_text}\n\n"
        "The customer REMOVED these items (they should be absent):\n"
        f"{removed_text}\n\n"
        "List every moveable object visible that is NOT a kept item — things the "
        "restyle added. Ignore architecture. For each: \"name\", \"where\", \"visual\" "
        "(one rich sentence: type, size, shape, material, colour, style), \"query\" "
        "(4-8 search words), \"cells\" (every grid cell any part of the object "
        "touches). Also list any removed item still visible.\n"
        'Return JSON only: {"new_items":[{"name":str,"where":str,"visual":str,'
        '"query":str,"cells":[str]}],"removed_items_visible":[str]}'
    )


def _refine_prompt(name: str, visual: str) -> str:
    return (
        "This crop from a room photo has a 6x6 labelled grid (rows A-F, columns "
        f"1-6). Which cells does THIS object occupy: {name} — {visual}? Include "
        "every cell any part of it touches, and nothing else.\n"
        'Return JSON only: {"cells":[str]}'
    )


_JUDGE_RULES = (
    "FIRST discard every candidate that is not the same TYPE of object as the "
    "target (score 1). Be strict: furniture the item sits on or in (a shelf, "
    "bookcase, TV stand, table, mantel) is NOT the item; a doormat or runner is "
    "not an area rug; a planter without a plant is fine for \"plant in a pot\"; a "
    "bookcase is never \"books\".\n"
    "THEN score each remaining candidate 1-5 for how much it looks like the "
    "target (5 = could be the same product, 3 = same kind of thing).\n"
    'Return JSON only: {"scores":[{"index":int,"score":int}]}'
)


def _judge_prompt(name: str, visual: str, candidates: list[JudgeCandidate]) -> str:
    listing = "\n".join(
        f"{c.index}. [{c.store}] {c.title[:80]} — CA${c.price:.2f}"
        + ("" if c.thumbnail_b64 else " (no image)")
        for c in candidates
    )
    return (
        f"The first image is a crop from an AI-restyled room photo showing: "
        f"{name} — {visual}\n"
        "The following images are candidate products, in the order listed (some "
        "have no image; judge those by title).\n"
        f"{listing}\n"
        f"{_JUDGE_RULES}"
    )


def _data_uri(image_bytes: bytes, content_type: str = "image/jpeg") -> str:
    return f"data:{content_type};base64,{base64.b64encode(image_bytes).decode()}"


def _valid_cells(value: object) -> list[str] | None:
    if not isinstance(value, list) or not value:
        return None
    cells = [str(c).upper() for c in value]
    if not all(_CELL_RE.match(c) for c in cells):
        return None
    return cells


class OpenAIShoppingModel:
    def __init__(
        self,
        api_key: str,
        *,
        describe_model: str = DESCRIBE_MODEL,
        judge_model: str = JUDGE_MODEL,
        timeout: float = 60.0,
    ) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, timeout=timeout, max_retries=1)
        self._describe_model = describe_model
        self._judge_model = judge_model

    def _ask(self, model: str, image_bytes: bytes, text: str) -> dict:
        import openai

        try:
            resp = self._client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": _data_uri(image_bytes)}},
                            {"type": "text", "text": text},
                        ],
                    }
                ],
                response_format={"type": "json_object"},
            )
            return json.loads(resp.choices[0].message.content or "{}")
        except (openai.OpenAIError, json.JSONDecodeError) as exc:
            raise ShoppingModelError(f"{type(exc).__name__}: {exc}") from exc

    def describe(
        self, grid_image: bytes, kept: list[tuple[str, str]], removed: list[str]
    ) -> DescribeResult:
        parsed = self._ask(self._describe_model, grid_image, _describe_prompt(kept, removed))
        items = []
        for raw in parsed.get("new_items", []):
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name") or "").strip()
            visual = str(raw.get("visual") or "").strip()
            cells = _valid_cells(raw.get("cells"))
            if not name or not visual or not cells:
                continue  # one noisy item shouldn't fail the whole render (§5.3)
            items.append(
                DescribedItem(
                    name=name,
                    where=str(raw.get("where") or "").strip(),
                    visual=visual,
                    query=str(raw.get("query") or "").strip(),
                    cells=cells,
                )
            )
        removed_visible = [str(x) for x in parsed.get("removed_items_visible", [])]
        return DescribeResult(items=items, removed_items_visible=removed_visible)

    def refine(self, fine_grid_image: bytes, name: str, visual: str) -> list[str] | None:
        try:
            parsed = self._ask(self._describe_model, fine_grid_image, _refine_prompt(name, visual))
        except ShoppingModelError:
            return None  # falls back to the coarse box — a soft failure, not fatal
        return _valid_cells(parsed.get("cells"))

    def judge(
        self, crop_image: bytes, name: str, visual: str, candidates: list[JudgeCandidate]
    ) -> dict[int, int]:
        import openai

        if not candidates:
            return {}
        content = [{"type": "image_url", "image_url": {"url": _data_uri(crop_image)}}]
        for c in candidates:
            if c.thumbnail_b64:
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{c.thumbnail_b64}"},
                    }
                )
        content.append({"type": "text", "text": _judge_prompt(name, visual, candidates)})
        try:
            resp = self._client.chat.completions.create(
                model=self._judge_model,
                messages=[{"role": "user", "content": content}],
                response_format={"type": "json_object"},
            )
            parsed = json.loads(resp.choices[0].message.content or "{}")
        except (openai.OpenAIError, json.JSONDecodeError) as exc:
            raise ShoppingModelError(f"{type(exc).__name__}: {exc}") from exc
        scores: dict[int, int] = {}
        for entry in parsed.get("scores", []):
            if not isinstance(entry, dict):
                continue
            try:
                scores[int(entry["index"])] = int(entry["score"])
            except (KeyError, TypeError, ValueError):
                continue
        return scores


class FakeShoppingModel:
    """Deterministic stand-in for local `docker compose` and integration tests
    (`SHOPPING_BACKEND=fake`). Always reports the same two new items, refine
    always succeeds with the same fine cells, and judge scores every candidate
    a clean pass — the pipeline logic around it (filter, pick, storage, the
    contract shape) is what these tests are actually exercising."""

    def describe(
        self, grid_image: bytes, kept: list[tuple[str, str]], removed: list[str]
    ) -> DescribeResult:
        return DescribeResult(
            items=[
                DescribedItem(
                    name="Olive tree in a woven basket",
                    where="to the left of the sofa",
                    visual="A tall potted olive tree in a woven seagrass basket.",
                    query="olive tree woven basket",
                    cells=["B2", "B3", "C2", "C3"],
                ),
                DescribedItem(
                    name="Stack of decorative books",
                    where="on the coffee table",
                    visual="A stack of three hardcover decorative books.",
                    query="decorative books stack",
                    cells=["E6"],
                ),
            ],
            removed_items_visible=[],
        )

    def refine(self, fine_grid_image: bytes, name: str, visual: str) -> list[str] | None:
        return ["B2", "B3", "C2", "C3"]

    def judge(
        self, crop_image: bytes, name: str, visual: str, candidates: list[JudgeCandidate]
    ) -> dict[int, int]:
        return {c.index: 5 for c in candidates}


class DisabledShoppingModel:
    def describe(self, grid_image: bytes, kept, removed) -> DescribeResult:
        raise ShoppingModelError("shopping model not configured — set SEARCHAPI_KEY/OPENAI_API_KEY "
                                  "or SHOPPING_BACKEND=fake")

    def refine(self, fine_grid_image: bytes, name: str, visual: str) -> list[str] | None:
        raise ShoppingModelError("shopping model not configured")

    def judge(self, crop_image: bytes, name: str, visual: str, candidates) -> dict[int, int]:
        raise ShoppingModelError("shopping model not configured")
