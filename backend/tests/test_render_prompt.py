from __future__ import annotations

from app.render.prompt import STYLES, build_prompt
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
    assert "THE STYLE THE CUSTOMER CHOSE — Scandi: bright, warm and uncluttered" in p
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


def test_all_18_styles_are_in_the_table():
    assert len(STYLES) == 18


def test_every_style_guide_has_exactly_four_bullets():
    for style_id, style in STYLES.items():
        bullets = style.guide.splitlines()
        assert len(bullets) == 4, style_id
        assert all(b.startswith("- ") for b in bullets), style_id


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
