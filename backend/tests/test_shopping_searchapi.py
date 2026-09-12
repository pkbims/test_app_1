from __future__ import annotations

import logging

import httpx
import pytest

from app.shopping.searchapi import FakeSearchApi, RawMatch, RealSearchApi, SearchApiError, _crop_param, _parse


def test_crop_param_formats_as_semicolon_joined_three_decimals():
    assert _crop_param((0.1, 0.2, 0.55555, 1.0)) == "0.100;0.200;0.556;1.000"


def test_parse_combines_visual_matches_and_products():
    payload = {
        "visual_matches": [{"link": "https://a.example/x", "title": "A", "extracted_price": 10}],
        "products": [{"link": "https://b.example/y", "title": "B", "extracted_price": 20}],
    }
    result = _parse(payload)
    assert result.matches == [
        RawMatch("https://a.example/x", "A", 10.0, None),
        RawMatch("https://b.example/y", "B", 20.0, None),
    ]
    assert result.error is None


def test_parse_drops_matches_with_no_link():
    payload = {"visual_matches": [{"title": "no link", "extracted_price": 5}]}
    assert _parse(payload).matches == []


def test_parse_missing_price_is_none_not_an_error():
    payload = {"visual_matches": [{"link": "https://a.example/x", "title": "A"}]}
    result = _parse(payload)
    assert result.matches[0].price is None


def test_parse_bad_price_type_is_none():
    payload = {"visual_matches": [{"link": "https://a.example/x", "title": "A", "extracted_price": "n/a"}]}
    assert _parse(payload).matches[0].price is None


def test_parse_surfaces_an_error_body_with_no_matches():
    result = _parse({"error": "Invalid API key."})
    assert result.matches == []
    assert result.error == "Invalid API key."


def test_parse_empty_payload_is_empty_matches_no_error():
    result = _parse({})
    assert result.matches == []
    assert result.error is None


def test_thumbnail_passed_through():
    payload = {
        "visual_matches": [
            {"link": "https://a.example/x", "title": "A", "extracted_price": 1, "thumbnail": "https://t/1.jpg"}
        ]
    }
    assert _parse(payload).matches[0].thumbnail == "https://t/1.jpg"


def test_fake_search_api_returns_two_priced_matches_from_different_stores():
    result = FakeSearchApi().search("https://example/render.png", (0.0, 0.0, 1.0, 1.0))
    assert len(result.matches) == 2
    assert all(m.price is not None for m in result.matches)
    hosts = {m.link.split("/")[2] for m in result.matches}
    assert len(hosts) == 2


def test_fake_search_api_check_link_and_thumbnail_touch_no_network():
    fake = FakeSearchApi()
    assert fake.check_link("https://anything") is True
    assert fake.fetch_thumbnail("https://anything") is None


# ── the API key must never leak into a raised error's message (§4.2 logging rule) ──
def _mock_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_search_error_message_never_contains_the_api_key(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "api_key=super-secret-key" in str(request.url)  # sanity: it really was sent
        return httpx.Response(403, request=request)

    monkeypatch.setattr(httpx, "get", lambda url, params, timeout: _mock_client(handler).get(
        url, params=params, timeout=timeout
    ))

    with pytest.raises(SearchApiError) as exc_info:
        RealSearchApi("super-secret-key").search("https://example/render.png", (0.0, 0.0, 1.0, 1.0))
    assert "super-secret-key" not in str(exc_info.value)
    assert "403" in str(exc_info.value)


def test_search_network_error_message_never_contains_the_api_key(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    monkeypatch.setattr(httpx, "get", lambda url, params, timeout: _mock_client(handler).get(
        url, params=params, timeout=timeout
    ))

    with pytest.raises(SearchApiError) as exc_info:
        RealSearchApi("super-secret-key").search("https://example/render.png", (0.0, 0.0, 1.0, 1.0))
    assert "super-secret-key" not in str(exc_info.value)


# ── ORCH-QUESTIONS Q11 finding 2: httpx's OWN request log, not our error path ────
#
# Deliberately not `caplog` here: `app.logs.configure()` replaces the ROOT
# logger's handlers wholesale (`root.handlers[:] = [handler]`), which silently
# discards pytest's own caplog handler along with it — a test built on
# `caplog.at_level(...)` around a `configure()` call would pass no matter what,
# because caplog stops seeing *anything* logged afterwards, not because the fix
# works. A handler attached straight to the "httpx" logger survives that
# (`configure()` only changes its *level*, never its handlers), and checking
# for zero emitted records is a stronger claim than "no key substring" anyway.
class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record.getMessage())


@pytest.fixture
def httpx_probe():
    handler = _ListHandler()
    logger = logging.getLogger("httpx")
    previous_level = logger.level
    logger.addHandler(handler)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)


def _search_via_mock(handler_fn) -> None:
    real_get = httpx.get
    httpx.get = lambda url, params, timeout: _mock_client(handler_fn).get(
        url, params=params, timeout=timeout
    )
    try:
        RealSearchApi("super-secret-key").search("https://example/render.png", (0.0, 0.0, 1.0, 1.0))
    finally:
        httpx.get = real_get


def _ok_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"visual_matches": []}, request=request)


def test_httpx_logs_the_full_url_by_default_including_the_api_key(httpx_probe):
    """Baseline, so the fix below isn't vacuously true: prove httpx really does
    log the whole request line — url, query string and all — at INFO by
    default, through the exact RealSearchApi.search() code path."""
    logging.getLogger("httpx").setLevel(logging.INFO)  # the pre-fix default
    _search_via_mock(_ok_response)
    assert any("super-secret-key" in msg for msg in httpx_probe.records)


def test_logs_configure_silences_httpxs_own_request_log(httpx_probe):
    """The actual fix: app.logs.configure() (called by both the API and the
    worker at startup) raises httpx/httpcore's own loggers to WARNING, so their
    routine per-request INFO line — which embeds the full URL, api_key and
    all — is never emitted at all, regardless of our own log level."""
    from app import logs

    logs.configure("info")
    _search_via_mock(_ok_response)
    assert httpx_probe.records == []
