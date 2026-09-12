"""The real-model shopping pipeline acceptance test (shopping_proto/HANDOFF.md
§6.4, third tier — same shape as `test_vision_e2e.py`).

Runs the real describe -> refine -> search -> filter -> judge -> pick pipeline
against `prompt_review/empty_A.png` — the actual Scandi empty-room render the
handoff's own research proved the mechanism on (§5.2's "final run on the
approved render": 7 items, 13 cards, cheapest-sum CA$609). It's an empty-room
render of the known room (`edae7f0b-...`, `tests/known_room.py`) with every
object removed, so every item the pipeline finds should be "new".

SearchApi must fetch the render from a real public URL (HANDOFF §7.3) — a bare
`docker compose up` cannot satisfy that, so this needs OPENAI_API_KEY,
SEARCHAPI_KEY, *and* a PUBLIC_BASE_URL that is actually reachable from the
internet (a tunnel; see backend/README.md's "Shopping backend" section).
Skipped without all three. Not in the default CI lane.
"""

from __future__ import annotations

import logging
import os
import pathlib

import httpx
import pytest

from .known_room import ITEMS

pytestmark = pytest.mark.integration

_SAMPLE = pathlib.Path("/prompt_review/empty_A.png")
_LOCAL_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0", "testserver")


@pytest.fixture
def deps():
    openai_key = os.environ.get("OPENAI_API_KEY")
    searchapi_key = os.environ.get("SEARCHAPI_KEY")
    public_base_url = os.environ.get("PUBLIC_BASE_URL", "")
    if not openai_key or not searchapi_key:
        pytest.skip("no OPENAI_API_KEY/SEARCHAPI_KEY")
    if not _SAMPLE.is_file():
        pytest.skip("sample render prompt_review/empty_A.png not mounted")
    if not public_base_url or any(h in public_base_url for h in _LOCAL_HOSTS):
        pytest.skip(
            "PUBLIC_BASE_URL must be a real, internet-reachable tunnel — SearchApi "
            "has to fetch the render itself (backend/README.md, 'Shopping backend')"
        )
    return openai_key, searchapi_key, public_base_url


def test_real_pipeline_finds_priced_verified_options(deps, tmp_path):
    from app.shopping.judge import OpenAIShoppingModel
    from app.shopping.pipeline import RenderInfo, ShoppingConfig, generate
    from app.shopping.searchapi import RealSearchApi
    from app.storage import LocalDiskStorage

    openai_key, searchapi_key, public_base_url = deps
    storage = LocalDiskStorage(tmp_path)
    after_key = "shopping-e2e.png"
    storage.put(f"renders/{after_key}", _SAMPLE.read_bytes(), "image/png")

    # This render has every object removed (an empty-room restyle) — architecture
    # is what's kept; every object on the known room's inventory was removed.
    kept = [(it["name"], it["description"]) for it in ITEMS if it["kind"] == "architecture"]
    removed_names = [it["name"] for it in ITEMS if it["kind"] != "architecture"]
    info = RenderInfo(after_key=after_key, kept=kept, removed_names=removed_names)
    config = ShoppingConfig(
        max_items=7, search_url_ttl_s=900,
        public_base_url=public_base_url, file_url_secret="shopping-e2e-secret",
    )

    result = generate(
        storage,
        OpenAIShoppingModel(openai_key),
        RealSearchApi(searchapi_key),
        "shopping-e2e-render",
        info,
        config,
        logging.getLogger("test.shopping.e2e"),
    )

    assert len(result.items) >= 4, f"only {len(result.items)} items found: {result.items}"

    verified_urls = []
    for item in result.items:
        for opt in item["options"]:
            assert opt["store"], item
            assert opt["title"], item
            assert opt["price"] > 0, item
            assert opt["url"], item
            if opt["verified"]:
                verified_urls.append(opt["url"])

    assert verified_urls, "no verified options at all across any item"
    for url in verified_urls:
        resp = httpx.get(url, follow_redirects=True, timeout=15)
        assert resp.status_code == 200, f"{url} -> {resp.status_code}"

    assert result.cost_cents < 20.0, result.cost_cents
