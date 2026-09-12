from __future__ import annotations

import pytest

from app.shopping.pipeline import (
    Candidate,
    cells_to_box,
    compose_box,
    filter_matches,
    host_of,
    is_known_store,
    is_unverifiable_store,
    make_item_ids,
    pad_box,
    pick_options,
    total_from,
)
from app.shopping.searchapi import RawMatch


# ── geometry ─────────────────────────────────────────────────────────────────
def test_cells_to_box_single_cell():
    assert cells_to_box(["A1"], 12, 8) == (0.0, 0.0, 1 / 12, 1 / 8)


def test_cells_to_box_spans_multiple_cells():
    # B2..C3 -> cols 1..2 (0-indexed), rows 1..2
    box = cells_to_box(["B2", "B3", "C2", "C3"], 12, 8)
    assert box == (1 / 12, 1 / 8, 3 / 12, 3 / 8)


def test_cells_to_box_none_when_empty():
    assert cells_to_box([], 12, 8) is None
    assert cells_to_box(None, 12, 8) is None


def test_cells_to_box_none_when_malformed():
    assert cells_to_box(["Z"], 12, 8) is None
    assert cells_to_box(["1A"], 12, 8) is None


def test_pad_box_clips_to_zero_one():
    assert pad_box((0.0, 0.0, 0.1, 0.1), 0.5, 0.5) == (0.0, 0.0, 0.6, 0.6)
    assert pad_box((0.9, 0.9, 1.0, 1.0), 0.5, 0.5) == (0.4, 0.4, 1.0, 1.0)


def test_pad_box_normal_case():
    assert pad_box((0.2, 0.3, 0.4, 0.5), 0.1, 0.1) == (
        pytest.approx(0.1), pytest.approx(0.2), pytest.approx(0.5), pytest.approx(0.6)
    )


def test_compose_box_maps_inner_fraction_into_outer_space():
    # region is the right half of the image; inner is the left half of THAT
    # region -> should land at the first quarter of the outer image.
    region = (0.5, 0.0, 1.0, 1.0)
    inner = (0.0, 0.0, 0.5, 1.0)
    assert compose_box(region, inner) == (0.5, 0.0, 0.75, 1.0)


def test_compose_box_identity_when_inner_is_the_whole_region():
    region = (0.2, 0.3, 0.8, 0.9)
    assert compose_box(region, (0.0, 0.0, 1.0, 1.0)) == pytest.approx(region)


# ── item ids ─────────────────────────────────────────────────────────────────
def test_make_item_ids_slugifies():
    assert make_item_ids(["Olive Tree", "Stack of Books!"]) == ["olive_tree", "stack_of_books"]


def test_make_item_ids_disambiguates_collisions():
    assert make_item_ids(["Lamp", "Lamp", "Lamp"]) == ["lamp", "lamp_2", "lamp_3"]


def test_make_item_ids_never_empty():
    assert make_item_ids(["!!!"]) == ["item"]


# ── filter (§5.1 step 4) ─────────────────────────────────────────────────────
def test_host_of_strips_www_and_lowercases():
    assert host_of("https://WWW.Walmart.CA/en/ip/x") == "walmart.ca"
    assert host_of("https://amazon.ca/dp/x") == "amazon.ca"


def test_is_known_store_matches_the_allowlist():
    assert is_known_store("walmart.ca")
    assert is_known_store("shop.walmart.ca")  # subdomain of a listed store


def test_is_known_store_matches_any_dot_ca_not_excluded():
    assert is_known_store("some-small-canadian-shop.ca")


def test_is_known_store_rejects_excluded_platforms_even_on_ca():
    assert not is_known_store("kijiji.ca")
    assert not is_known_store("facebook.ca")


def test_is_known_store_rejects_unrelated_dot_com():
    assert not is_known_store("randomblog.com")


def test_is_known_store_does_not_false_positive_on_substring():
    # "notwalmart.ca" must not match "walmart.ca" (fixes a latent bug in the
    # research spike's plain .endswith(s) check)
    assert is_known_store("notwalmart.ca")  # still true! it's its own .ca store
    assert not is_known_store("walmart.ca.evil.com")


def test_is_unverifiable_store_matches_the_d3_list():
    assert is_unverifiable_store("wayfair.ca")
    assert is_unverifiable_store("shop.wayfair.ca")
    assert not is_unverifiable_store("walmart.ca")


def _match(link, price=10.0, title="t"):
    return RawMatch(link=link, title=title, price=price, thumbnail=None)


def test_filter_matches_requires_a_price():
    matches = [_match("https://walmart.ca/x", price=None)]
    assert filter_matches(matches) == []


def test_filter_matches_drops_unknown_hosts():
    matches = [_match("https://pinterest.com/pin/1")]
    assert filter_matches(matches) == []


def test_filter_matches_dedupes_by_url():
    matches = [_match("https://walmart.ca/x"), _match("https://walmart.ca/x")]
    assert len(filter_matches(matches)) == 1


def test_filter_matches_caps_at_twelve():
    matches = [_match(f"https://walmart.ca/{i}") for i in range(20)]
    assert len(filter_matches(matches)) == 12


def test_filter_matches_keeps_valid_matches_in_order():
    matches = [_match("https://walmart.ca/a"), _match("https://amazon.ca/b")]
    out = filter_matches(matches)
    assert [m.link for m in out] == ["https://walmart.ca/a", "https://amazon.ca/b"]


# ── pick (§5.1 step 6) ───────────────────────────────────────────────────────
def _cand(store, price, url=None):
    return Candidate(store=store, title="t", price=price, url=url or f"https://{store}/x",
                      thumbnail=None, verified=True)


def test_pick_options_keeps_only_scores_at_or_above_threshold():
    scored = [(_cand("walmart.ca", 10), 2), (_cand("amazon.ca", 12), 3)]
    chosen = pick_options(scored)
    assert [c.store for c in chosen] == ["amazon.ca"]


def test_pick_options_cheapest_two_from_different_stores():
    scored = [
        (_cand("walmart.ca", 20), 5),
        (_cand("amazon.ca", 10), 5),
        (_cand("vevor.ca", 15), 5),
    ]
    chosen = pick_options(scored)
    assert [c.store for c in chosen] == ["amazon.ca", "vevor.ca"]


def test_pick_options_never_two_from_the_same_store_base():
    scored = [(_cand("walmart.ca", 10), 5), (_cand("walmart.com", 12), 5)]
    chosen = pick_options(scored)
    assert len(chosen) == 1
    assert chosen[0].price == 10


def test_pick_options_never_more_than_two():
    scored = [(_cand(f"store{i}.ca", i), 5) for i in range(5)]
    assert len(pick_options(scored)) == 2


def test_pick_options_empty_when_nothing_passes():
    assert pick_options([(_cand("walmart.ca", 10), 1)]) == []


# ── total_from ───────────────────────────────────────────────────────────────
def test_total_from_sums_cheapest_option_per_item():
    items = [
        {"options": [{"price": 70.0}, {"price": 74.0}]},
        {"options": [{"price": 20.0}]},
    ]
    assert total_from(items) == 90.0


def test_total_from_ignores_items_with_no_options():
    items = [{"options": [{"price": 70.0}]}, {"options": []}]
    assert total_from(items) == 70.0


def test_total_from_none_when_no_item_has_an_option():
    assert total_from([{"options": []}, {"options": []}]) is None


def test_total_from_empty_items_is_none():
    assert total_from([]) is None


def test_total_from_rounds_to_cents():
    items = [{"options": [{"price": 10.005}]}, {"options": [{"price": 10.001}]}]
    assert total_from(items) == 20.01
