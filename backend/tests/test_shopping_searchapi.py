from __future__ import annotations

from app.shopping.searchapi import FakeSearchApi, RawMatch, _crop_param, _parse


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
