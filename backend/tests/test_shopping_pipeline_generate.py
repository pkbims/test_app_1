"""`generate()` end to end against the fake model/searchapi and a real
LocalDiskStorage — no DB. Covers: crops are stored, items come out in the right
shape, cost/searchapi-call bookkeeping, and the "retry once on empty" rule.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.shopping.judge import FakeShoppingModel
from app.shopping.pipeline import RenderInfo, ShoppingConfig, generate
from app.shopping.searchapi import FakeSearchApi, RawMatch, SearchResult
from app.storage import LocalDiskStorage

import logging

_LOG = logging.getLogger("test")


def _render_jpeg(size=(1200, 900)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (180, 170, 160)).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def storage(tmp_path):
    s = LocalDiskStorage(tmp_path)
    s.put("renders/r1.png", _render_jpeg(), "image/jpeg")
    return s


@pytest.fixture
def config():
    return ShoppingConfig(
        max_items=7, search_url_ttl_s=900,
        public_base_url="http://localhost:8000", file_url_secret="secret",
    )


@pytest.fixture
def info():
    return RenderInfo(after_key="r1.png", kept=[("sofa", "a grey sofa")], removed_names=[])


def test_generate_produces_the_fake_models_two_items(storage, config, info):
    result = generate(storage, FakeShoppingModel(), FakeSearchApi(), "render-1", info, config, _LOG)
    assert [it["name"] for it in result.items] == [
        "Olive tree in a woven basket", "Stack of decorative books",
    ]


def test_generate_stores_a_crop_per_item(storage, config, info):
    result = generate(storage, FakeShoppingModel(), FakeSearchApi(), "render-1", info, config, _LOG)
    for item in result.items:
        assert storage.exists(f"crops/{item['crop_key']}")
        assert item["crop_key"].startswith("render-1/")


def test_generate_item_ids_are_slugs(storage, config, info):
    result = generate(storage, FakeShoppingModel(), FakeSearchApi(), "render-1", info, config, _LOG)
    assert [it["item_id"] for it in result.items] == ["olive_tree_in_a_woven_basket", "stack_of_decorative_books"]


def test_generate_options_from_fake_searchapi_are_priced_and_verified(storage, config, info):
    result = generate(storage, FakeShoppingModel(), FakeSearchApi(), "render-1", info, config, _LOG)
    for item in result.items:
        assert len(item["options"]) == 2
        for opt in item["options"]:
            assert opt["price"] > 0
            assert opt["verified"] is True


def test_generate_total_from_matches_pipeline_total_from(storage, config, info):
    from app.shopping.pipeline import total_from

    result = generate(storage, FakeShoppingModel(), FakeSearchApi(), "render-1", info, config, _LOG)
    assert result.total_from == total_from(result.items)
    assert result.total_from == pytest.approx(140.0)  # cheapest option (70) x two items


def test_generate_respects_max_items(storage, config, info):
    small_config = ShoppingConfig(
        max_items=1, search_url_ttl_s=900,
        public_base_url="http://localhost:8000", file_url_secret="secret",
    )
    result = generate(storage, FakeShoppingModel(), FakeSearchApi(), "render-1", info, small_config, _LOG)
    assert len(result.items) == 1


def test_generate_counts_searchapi_calls_one_per_item_when_first_try_succeeds(storage, config, info):
    result = generate(storage, FakeShoppingModel(), FakeSearchApi(), "render-1", info, config, _LOG)
    assert result.searchapi_calls == 2  # one per fake item, FakeSearchApi never returns empty


def test_generate_retries_once_when_search_returns_empty_then_succeeds(storage, config, info):
    class _RetryOnce:
        def __init__(self):
            self.calls = 0

        def search(self, render_url, crop):
            self.calls += 1
            if self.calls % 2 == 1:
                return SearchResult(matches=[])
            return SearchResult(matches=[RawMatch("https://walmart.ca/x", "t", 10.0, None)])

        def check_link(self, url):
            return True

        def fetch_thumbnail(self, url):
            return None

    searchapi = _RetryOnce()
    result = generate(storage, FakeShoppingModel(), searchapi, "render-1", info, config, _LOG)
    assert searchapi.calls == 4  # 2 items x (empty, then a real hit)
    assert all(len(it["options"]) == 1 for it in result.items)


def test_generate_item_with_no_matches_after_retry_has_no_options(storage, config, info):
    class _AlwaysEmpty:
        def search(self, render_url, crop):
            return SearchResult(matches=[])

        def check_link(self, url):
            return True

        def fetch_thumbnail(self, url):
            return None

    result = generate(storage, FakeShoppingModel(), _AlwaysEmpty(), "render-1", info, config, _LOG)
    assert all(it["options"] == [] for it in result.items)
    assert result.total_from is None


def test_generate_unverifiable_store_is_kept_but_marked_unverified(storage, config, info):
    class _BlockedStore:
        def search(self, render_url, crop):
            return SearchResult(matches=[RawMatch("https://www.wayfair.ca/x", "t", 50.0, None)])

        def check_link(self, url):
            raise AssertionError("must not be called for an unverifiable store")

        def fetch_thumbnail(self, url):
            return None

    result = generate(storage, FakeShoppingModel(), _BlockedStore(), "render-1", info, config, _LOG)
    options = result.items[0]["options"]
    assert options and options[0]["store"] == "wayfair.ca"
    assert options[0]["verified"] is False


def test_generate_dead_link_is_dropped(storage, config, info):
    class _DeadLink:
        def search(self, render_url, crop):
            return SearchResult(matches=[RawMatch("https://walmart.ca/x", "t", 50.0, None)])

        def check_link(self, url):
            return False

        def fetch_thumbnail(self, url):
            return None

    result = generate(storage, FakeShoppingModel(), _DeadLink(), "render-1", info, config, _LOG)
    assert all(it["options"] == [] for it in result.items)


def test_generate_cost_cents_scales_with_calls(storage, config, info):
    result = generate(storage, FakeShoppingModel(), FakeSearchApi(), "render-1", info, config, _LOG)
    assert result.cost_cents > 0


# ── TEMPORARY dev-only uguu.se path (ORCH-QUESTIONS Q11, HANDOFF §7.3,
# shopping_proto/DEV-IMAGE-HOST.md) ─────────────────────────────────────────
class _RecordingSearchApi(FakeSearchApi):
    def __init__(self):
        self.urls_seen: list[str] = []

    def search(self, render_url, crop):
        self.urls_seen.append(render_url)
        return super().search(render_url, crop)


def _uguu_config(**overrides):
    kwargs = dict(
        max_items=7, search_url_ttl_s=900,
        public_base_url="http://localhost:8000", file_url_secret="secret",
        dev_public_image_host="uguu",
    )
    kwargs.update(overrides)
    return ShoppingConfig(**kwargs)


def test_generate_default_config_never_touches_uguu(storage, config, info, monkeypatch):
    def blow_up(*a, **kw):
        raise AssertionError("httpx.post must not be called when dev_public_image_host is unset")

    monkeypatch.setattr("httpx.post", blow_up)
    assert config.dev_public_image_host == ""
    generate(storage, FakeShoppingModel(), FakeSearchApi(), "render-1", info, config, _LOG)


def test_generate_uguu_uploads_once_and_every_item_searches_that_url(storage, info, monkeypatch, caplog):
    import httpx

    calls = []

    def fake_post(url, *, files, timeout):
        calls.append((url, files.get("files[]")))
        return httpx.Response(
            200,
            json={"success": True, "files": [{"url": "https://n.uguu.se/dhTswTOV.png"}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("httpx.post", fake_post)
    searchapi = _RecordingSearchApi()

    with caplog.at_level(logging.WARNING):
        generate(storage, FakeShoppingModel(), searchapi, "render-1", info, _uguu_config(), _LOG)

    assert len(calls) == 1  # once per job, not once per item — FakeShoppingModel gives 2 items
    assert calls[0][0] == "https://uguu.se/upload"
    assert calls[0][1][0] == "render.png"  # (filename, bytes, content_type)
    assert searchapi.urls_seen == ["https://n.uguu.se/dhTswTOV.png"] * 2
    assert any("uguu" in r.message and "production" in r.message for r in caplog.records)


@pytest.mark.parametrize(
    "response_kwargs",
    [
        {"status_code": 500, "text": "server error"},  # non-200
        {"status_code": 200, "json": {"success": False}},  # success: false
        {"status_code": 200, "json": {"success": True, "files": []}},  # missing url
        {"status_code": 200, "json": {"success": True, "files": [{"name": "x"}]}},  # url absent
        {"status_code": 200, "text": ""},  # empty body, not even JSON
    ],
)
def test_generate_uguu_upload_failure_raises_searchapi_error(storage, info, monkeypatch, response_kwargs):
    import httpx

    from app.shopping.searchapi import SearchApiError

    def fake_post(url, *, files, timeout):
        kwargs = {k: v for k, v in response_kwargs.items() if k != "status_code"}
        return httpx.Response(
            response_kwargs["status_code"], request=httpx.Request("POST", url), **kwargs
        )

    monkeypatch.setattr("httpx.post", fake_post)
    with pytest.raises(SearchApiError):
        generate(storage, FakeShoppingModel(), FakeSearchApi(), "render-1", info, _uguu_config(), _LOG)
