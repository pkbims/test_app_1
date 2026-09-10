from __future__ import annotations

from app.render.prompt import build_prompt
from app.schemas import InventoryItem


def _item(id_, kind, desc, removable):
    return InventoryItem(id=id_, kind=kind, name=id_.lower(), description=desc, removable=removable)


ITEMS = [
    _item("A", "architecture", "White back wall spanning the frame.", False),
    _item("B", "architecture", "Wood-plank flooring across the floor.", False),
    _item("C", "object", "Grey sofa against the back wall.", True),
    _item("D", "object", "Laundry hamper to the right of the sofa.", True),
]


def test_three_sections_in_order():
    p = build_prompt(
        style="warm-minimal",
        user_prompt=None,
        items=ITEMS,
        remove_ids=["D"],
        room_label="Living Room",
    )
    assert p.startswith("Restyle this living room in a warm minimal style.")
    assert p.index("MUST REMAIN") < p.index("KEEP these items") < p.index("REMOVE these entirely")
    # architecture verbatim under MUST REMAIN
    assert "- White back wall spanning the frame." in p
    # kept object
    assert "- Grey sofa against the back wall." in p.split("KEEP these items")[1]
    # removed object
    assert "- Laundry hamper to the right of the sofa." in p.split("REMOVE these entirely")[1]


def test_remove_section_omitted_when_nothing_removed():
    p = build_prompt(style="s", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None)
    assert "REMOVE these entirely" not in p
    assert "Restyle this room in a s style." in p


def test_architecture_never_appears_as_removable():
    # even if an architecture id is passed in remove_ids, it stays under MUST REMAIN
    p = build_prompt(style="s", user_prompt=None, items=ITEMS, remove_ids=["A"], room_label=None)
    assert "- White back wall spanning the frame." in p.split("MUST REMAIN")[1].split("KEEP")[0]


def test_user_prompt_is_included_but_after_the_style_line():
    p = build_prompt(
        style="calm",
        user_prompt="lighter walls, keep it cosy",
        items=ITEMS,
        remove_ids=[],
        room_label=None,
    )
    lines = p.splitlines()
    assert lines[0].startswith("Restyle this room")
    assert lines[1] == "lighter walls, keep it cosy"


def test_footer_present():
    p = build_prompt(style="s", user_prompt=None, items=ITEMS, remove_ids=[], room_label=None)
    assert p.rstrip().endswith("ceiling feature.")
