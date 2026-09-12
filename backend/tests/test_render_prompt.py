from __future__ import annotations

import pytest

from app.render.prompt import (
    _PALETTE_FAMILIES,
    FURNITURE_BY_ROOM_TYPE,
    ROOM_TYPES,
    STYLES,
    build_prompt,
)
from app.schemas import InventoryItem


def _item(id_, kind, desc, removable, name=None):
    return InventoryItem(
        id=id_, kind=kind, name=name or id_.lower(), description=desc, removable=removable
    )


ITEMS = [
    _item("A", "architecture", "White back wall spanning the frame.", False),
    _item("B", "architecture", "Wood-plank flooring across the floor.", False),
    _item("C", "object", "Grey sofa against the back wall.", True),
    _item(
        "D",
        "object",
        "Large flat-screen TV on light wood stand with rattan-front cabinets, "
        "centered along the main wall.",
        True,
        name="TV and stand",
    ),
]


def test_preamble_opens_the_prompt():
    p = build_prompt(style="scandi", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None)
    assert p.startswith("You are an expert interior designer")


def test_known_style_uses_the_guide_table():
    p = build_prompt(style="scandi", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None)
    assert "THE STYLE THE CUSTOMER CHOSE — Scandinavian: bright, warm and uncluttered" in p
    assert "- Palette: white and chalky off-white walls" in p
    assert "- Avoid: ornate carving" in p


def test_unknown_style_falls_back_without_erroring():
    p = build_prompt(style="not-a-real-style", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None)
    assert "THE STYLE THE CUSTOMER CHOSE — not a real style." in p
    # no guide lines leaked in from another style
    assert "Palette:" not in p
    assert "Materials:" not in p
    # falls back to the small-decor rule, same as any unlisted style
    assert "add small decor" in p


# ── STYLES table completeness (18 original + 44 DecorAI-parity batch) ──────────
_ORIGINAL_18_IDS = [
    "warm-minimal", "scandi", "japandi", "modern-coastal", "mid-century", "industrial",
    "traditional", "art-deco", "dark-academia", "maximalism", "moroccan", "cottagecore",
    "rustic-farmhouse", "mediterranean", "cyberpunk", "memphis", "christmas", "valentines",
]

_DECORAI_44_NAMES = [
    "Minimalistic", "Modern", "Transitional", "Contemporary", "Japanese", "Eclectic",
    "Rustic", "Bohemian", "Farmhouse", "Vintage", "Victorian", "Retro", "Zen",
    "Biophilic", "Solarpunk", "Tropical", "Parisian", "Brutalist", "Vaporwave",
    "Hollywood Regency", "Art Nouveau", "Korean Hanok", "Southwestern",
    "Nordic Hygge", "Baroque", "Bauhaus", "Futuristic", "Colonial", "Tudor",
    "Shaker", "Rococo", "Deconstructivism", "Wabi-Sabi", "Organic Modern",
    "Quiet Luxury", "French Country", "English Country", "Neoclassical",
    "Alpine Chalet", "Hacienda", "Chinoiserie", "Shabby Chic", "Gothic",
    "Steampunk",
]


def test_all_62_styles_are_in_the_table():
    assert len(STYLES) == 18 + 44 == 62


def test_original_18_ids_are_all_still_present_unrenamed():
    # render history references ids directly — these must never move.
    for style_id in _ORIGINAL_18_IDS:
        assert style_id in STYLES, style_id


def test_the_two_cosmetic_renames_landed_on_the_right_ids():
    assert STYLES["scandi"].name == "Scandinavian"
    assert STYLES["mid-century"].name == "Mid-Century Modern"


def test_warm_minimal_and_rustic_farmhouse_keep_their_original_names():
    # not DecorAI names; kept as extras, explicitly not touched by the rename.
    assert STYLES["warm-minimal"].name == "Warm minimal"
    assert STYLES["rustic-farmhouse"].name == "Rustic Farmhouse"


def test_every_decorai_name_is_present_exactly():
    names_present = {s.name for s in STYLES.values()}
    for name in _DECORAI_44_NAMES:
        assert name in names_present, name


def test_no_duplicate_display_names():
    names = [s.name for s in STYLES.values()]
    assert len(names) == len(set(names))


def test_every_style_guide_has_exactly_four_labelled_bullets():
    expected_prefixes = ("- Palette:", "- Materials:", "- Forms and pieces:", "- Avoid:")
    for style_id, style in STYLES.items():
        bullets = style.guide.splitlines()
        assert len(bullets) == 4, style_id
        for bullet, prefix in zip(bullets, expected_prefixes):
            assert bullet.startswith(prefix), (style_id, bullet[:40])


def test_every_style_has_a_valid_decor_scale():
    for style_id, style in STYLES.items():
        assert style.decor_scale in ("small", "large"), style_id


def test_every_style_summary_is_a_non_empty_sentence():
    for style_id, style in STYLES.items():
        assert style.summary.strip(), style_id
        assert style.summary.strip().endswith("."), style_id


def test_rustic_and_farmhouse_and_rustic_farmhouse_are_three_distinct_entries():
    # DecorAI treats these as separate styles — explicitly not merged or deduped.
    assert STYLES["rustic"].name == "Rustic"
    assert STYLES["farmhouse"].name == "Farmhouse"
    assert STYLES["rustic-farmhouse"].name == "Rustic Farmhouse"
    guides = {STYLES["rustic"].guide, STYLES["farmhouse"].guide, STYLES["rustic-farmhouse"].guide}
    assert len(guides) == 3


def test_decor_scale_small_renders_small_decor_rule():
    p = build_prompt(style="scandi", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None)
    assert "add small decor" in p


def test_decor_scale_large_renders_large_decor_rule():
    p = build_prompt(style="christmas", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None)
    assert "add decorations of any size, including large freestanding ones" in p
    assert "add small decor" not in p


def test_sections_are_in_order():
    p = build_prompt(
        style="warm-minimal", user_prompt=None, items=ITEMS, remove_ids=["D"], room_label="Living Room"
    )
    assert (
        p.index("MUST REMAIN")
        < p.index("KEEP these items")
        < p.index("NOT IN THE ROOM")
        < p.index("HOW TO DO THE WORK")
    )


def test_room_label_appears_only_in_the_inventory_header():
    p = build_prompt(
        style="warm-minimal", user_prompt=None, items=ITEMS, remove_ids=[], room_label="Living Room"
    )
    assert "This is a living room." in p
    assert not p.split("WHAT IS IN THE PHOTOGRAPH")[0].lower().count("living room")


# ── room type (options round §3.4, §4.2) ────────────────────────────────────────
def test_room_type_wins_over_room_label():
    p = build_prompt(
        style="s", user_prompt=None, items=ITEMS, remove_ids=[],
        room_label="Living Room", room_type="home_office",
    )
    assert "This is a home office." in p
    assert "This is a living room." not in p


def test_room_label_used_when_room_type_is_absent():
    p = build_prompt(
        style="s", user_prompt=None, items=ITEMS, remove_ids=[],
        room_label="Kids Den", room_type=None,
    )
    assert "This is a kids den." in p


def test_falls_back_to_room_when_neither_is_known():
    p = build_prompt(
        style="s", user_prompt=None, items=ITEMS, remove_ids=[],
        room_label=None, room_type=None,
    )
    assert "This is a room." in p


def test_unknown_room_type_id_falls_back_to_room_label():
    p = build_prompt(
        style="s", user_prompt=None, items=ITEMS, remove_ids=[],
        room_label="Den", room_type="garage",  # not one of the 12 ids
    )
    assert "This is a den." in p


def test_every_room_type_id_has_a_display_name_and_a_furniture_list():
    assert len(ROOM_TYPES) == 12
    assert set(ROOM_TYPES) == set(FURNITURE_BY_ROOM_TYPE)


def test_kids_room_display_name_has_the_apostrophe():
    assert ROOM_TYPES["kids_room"] == "Kids' room"


def test_architecture_verbatim_under_must_remain():
    p = build_prompt(style="s", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None)
    assert "- White back wall spanning the frame." in p.split("MUST REMAIN")[1].split("KEEP")[0]


def test_kept_object_verbatim_under_keep():
    p = build_prompt(style="s", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None)
    assert "- Grey sofa against the back wall." in p.split("KEEP these items")[1]


def test_refinish_line_present_when_objects_kept():
    p = build_prompt(style="s", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None)
    assert "Restyle the kept items by changing only their material, colour and finish." in p


def test_empty_room_line_when_nothing_is_kept():
    p = build_prompt(style="s", user_prompt=None, items=ITEMS, remove_ids=["C", "D"], room_label=None)
    assert "furnish it fully" in p
    assert "Restyle the kept items" not in p


def test_remove_section_omitted_when_nothing_removed():
    p = build_prompt(style="s", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None)
    assert "NOT IN THE ROOM" not in p


def test_architecture_never_appears_as_removable():
    # even if an architecture id is passed in remove_ids, it stays under MUST REMAIN
    p = build_prompt(style="s", user_prompt=None, items=ITEMS, remove_ids=["A"], room_label=None)
    assert "- White back wall spanning the frame." in p.split("MUST REMAIN")[1].split("KEEP")[0]
    assert "NOT IN THE ROOM" not in p


# ── the REMOVE bug fix (HANDOFF §4) ─────────────────────────────────────────────
def test_removed_item_is_named_not_described():
    p = build_prompt(style="s", user_prompt=None, items=ITEMS, remove_ids=["D"], room_label=None)
    gone = p.split("NOT IN THE ROOM")[1]
    assert "TV and stand" in gone
    assert "Large flat-screen TV on light wood stand" not in p


def test_removed_item_description_never_appears_anywhere():
    p = build_prompt(style="s", user_prompt=None, items=ITEMS, remove_ids=["D"], room_label=None)
    assert "rattan-front cabinets" not in p


def test_removed_item_appears_only_under_gone_never_under_keep_or_architecture():
    p = build_prompt(style="s", user_prompt=None, items=ITEMS, remove_ids=["D"], room_label=None)
    before_gone = p.split("NOT IN THE ROOM")[0]
    assert "TV and stand" not in before_gone


def test_removed_item_states_the_end_state():
    p = build_prompt(style="s", user_prompt=None, items=ITEMS, remove_ids=["D"], room_label=None)
    assert "- TV and stand — gone; the space it occupied is empty" in p


def test_not_in_the_room_rule_present_when_removal_section_present():
    p = build_prompt(style="s", user_prompt=None, items=ITEMS, remove_ids=["D"], room_label=None)
    assert "Anything listed as not in the room is gone" in p


# ── walls (options round §4.3, D3) ──────────────────────────────────────────────
def test_walls_leave_is_the_default():
    p = build_prompt(style="s", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None)
    assert "- The wall colour stays exactly as it is." in p
    assert "You may change wall colour" not in p
    assert "- You may change textiles, rugs, and" in p


def test_walls_repaint_allows_wall_colour():
    p = build_prompt(
        style="s", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None, walls="repaint"
    )
    assert "- You may change wall colour, textiles, rugs, and" in p
    assert "The wall colour stays exactly as it is." not in p


@pytest.mark.parametrize("walls", ["leave", "repaint"])
def test_skirting_line_always_present(walls):
    p = build_prompt(
        style="s", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None, walls=walls
    )
    assert (
        "- Skirting boards, door frames and window frames match the walls: repaint "
        "them to suit if the walls are repainted, otherwise leave them. The ceiling "
        "and the floor stay exactly as they are."
    ) in p


# ── furniture / add_furniture (options round §4.4) ──────────────────────────────
def test_furniture_keep_only_forbids_new_furniture():
    p = build_prompt(style="s", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None)
    assert "- Do not add any furniture." in p
    assert "ADD TO THE ROOM" not in p


def test_furniture_add_with_items_produces_the_block():
    p = build_prompt(
        style="s", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None,
        furniture="add", add_furniture=["sofa", "armchair"], room_type="living_room",
    )
    assert "ADD TO THE ROOM — the customer wants these pieces, which are not in the photograph:" in p
    block = p.split("ADD TO THE ROOM")[1]
    assert "- a sofa" in block
    assert "- an armchair" in block
    assert (
        "Place them where such pieces would naturally go, at a realistic scale for "
        "the room,\nin the chosen style, without moving anything that is kept."
    ) in p
    assert "- Add only the pieces listed under ADD TO THE ROOM. Do not add any other furniture." in p
    assert "- Do not add any furniture." not in p


def test_furniture_add_with_empty_list_behaves_as_keep_only():
    p = build_prompt(
        style="s", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None,
        furniture="add", add_furniture=[], room_type="living_room",
    )
    assert "ADD TO THE ROOM" not in p
    assert "- Do not add any furniture." in p


def test_add_furniture_is_ignored_when_furniture_is_keep_only():
    p = build_prompt(
        style="s", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None,
        furniture="keep_only", add_furniture=["sofa"], room_type="living_room",
    )
    assert "ADD TO THE ROOM" not in p
    assert "a sofa" not in p


@pytest.mark.parametrize(
    "furniture_id,expected",
    [
        ("armchair", "- an armchair"),
        ("office_chair", "- an office chair"),
        ("island", "- an island"),
        ("open_shelving", "- an open shelving"),
        ("sideboard", "- a sideboard"),
        ("coffee_table", "- a coffee table"),
    ],
)
def test_add_furniture_article_is_grammatical(furniture_id, expected):
    room_type = next(rt for rt, items in FURNITURE_BY_ROOM_TYPE.items() if furniture_id in items)
    p = build_prompt(
        style="s", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None,
        furniture="add", add_furniture=[furniture_id], room_type=room_type,
    )
    assert expected in p


def test_add_furniture_unknown_room_type_falls_back_to_the_raw_id():
    p = build_prompt(
        style="s", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None,
        furniture="add", add_furniture=["mystery_id"], room_type=None,
    )
    assert "- a mystery id" in p


def test_add_furniture_block_sits_after_gone_and_before_rules():
    p = build_prompt(
        style="s", user_prompt=None, items=ITEMS, remove_ids=["D"], room_label=None,
        furniture="add", add_furniture=["sofa"], room_type="living_room",
    )
    assert p.index("NOT IN THE ROOM") < p.index("ADD TO THE ROOM") < p.index("HOW TO DO THE WORK")


# ── decor (options round §4.5) ───────────────────────────────────────────────────
def test_decor_as_style_default_uses_the_small_style_scale():
    p = build_prompt(style="scandi", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None)
    assert "add small decor, including lamps" in p


def test_decor_as_style_seasonal_style_uses_the_large_scale():
    p = build_prompt(style="christmas", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None)
    assert "add decorations of any size, including large freestanding ones" in p


def test_decor_as_style_unknown_style_falls_back_to_small():
    p = build_prompt(style="not-a-style", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None)
    assert "add small decor, including lamps" in p


def test_decor_minimal():
    p = build_prompt(
        style="scandi", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None, decor="minimal"
    )
    assert (
        "add only a few chosen pieces of decor — one artwork, one lamp, one object — "
        "and leave most walls and surfaces clear"
    ) in p
    assert "add small decor" not in p


def test_decor_plenty():
    p = build_prompt(
        style="scandi", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None, decor="plenty"
    )
    assert (
        "add decor generously — layered art, lamps, cushions and objects on the "
        "walls and on every surface"
    ) in p


# ── plants (options round §4.6) ──────────────────────────────────────────────────
def test_plants_off_by_default():
    p = build_prompt(style="s", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None)
    assert "plant" not in p.lower()


def test_plants_on_adds_the_rule_line():
    p = build_prompt(
        style="s", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None, plants=True
    )
    assert "- Add a few potted plants, placed where they would naturally sit." in p


# ── palette (options round §4.7) ─────────────────────────────────────────────────
def test_palette_as_style_default_has_no_override_line():
    p = build_prompt(style="scandi", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None)
    assert "Override the palette above" not in p


def test_palette_override_with_walls_repaint():
    p = build_prompt(
        style="scandi", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None,
        palette="neutral", walls="repaint",
    )
    assert (
        "Override the palette above: use whites, greys and beiges, with colour "
        "coming only from wood and texture. Keep the materials, forms and "
        "everything else in the guide as described."
    ) in p
    assert "except the walls" not in p


def test_palette_override_with_walls_leave_notes_the_exception():
    p = build_prompt(
        style="scandi", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None,
        palette="warm",  # walls left at its default, "leave"
    )
    assert (
        "Override the palette above: use creams, terracotta, honey-toned wood and "
        "soft browns, except the walls, which keep their current colour. Keep the "
        "materials, forms and everything else in the guide as described."
    ) in p


def test_palette_line_sits_right_after_the_style_guide():
    p = build_prompt(
        style="scandi", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None, palette="bold"
    )
    assert p.index("- Avoid: ornate carving") < p.index("Override the palette above")
    assert p.index("Override the palette above") < p.index("WHAT IS IN THE PHOTOGRAPH")


@pytest.mark.parametrize("palette", ["neutral", "warm", "cool", "bold"])
def test_every_palette_family_has_its_own_phrase(palette):
    p = build_prompt(
        style="scandi", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None,
        palette=palette, walls="repaint",
    )
    assert f"Override the palette above: use {_PALETTE_FAMILIES[palette]}." in p


def test_user_prompt_is_included_after_the_style_guide():
    p = build_prompt(
        style="warm-minimal",
        user_prompt="lighter walls, keep it cosy",
        items=ITEMS,
        remove_ids=[],
        room_label=None,
    )
    assert "The customer also asked for: lighter walls, keep it cosy" in p
    assert p.index("Palette:") < p.index("The customer also asked for")


def test_rules_block_present():
    p = build_prompt(style="s", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None)
    assert "HOW TO DO THE WORK" in p
    assert (
        "If you are unsure whether something is part of the building, leave it exactly as it is."
        in p
    )
