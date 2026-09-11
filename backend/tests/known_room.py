"""The known room shared by the render-level acceptance tests.

`/inputs/room.jpg` and this exact inventory were used to prove the REMOVE fix
(`test_remove_bug_acceptance.py`, room `edae7f0b-d22e-4657-b683-7a647e884122` in
the original prompt-rewrite handoff) and are reused here for the options round
so each acceptance test doesn't spend a second real vision call re-deriving the
same inventory. It is a living room — a fireplace, mantel, alcove, TV and stand.
"""

from __future__ import annotations

import pathlib

SAMPLE_PHOTO = pathlib.Path("/inputs/room.jpg")

ITEMS = [
    {"id": "A", "kind": "architecture", "name": "fireplace", "removable": False,
     "description": "Rectangular wooden mantel with grey tile inlay on the left side of the room, "
                     "partially in view."},
    {"id": "B", "kind": "architecture", "name": "mantel", "removable": False,
     "description": "Light wood shelf resting on top of the fireplace, extending horizontally "
                     "under decorative objects."},
    {"id": "C", "kind": "architecture", "name": "alcove", "removable": False,
     "description": "Recessed inset in wall to the left of center, above the mantel and fireplace, "
                     "providing a shallow nook."},
    {"id": "D", "kind": "architecture", "name": "wall with bulkhead", "removable": False,
     "description": "Main wall with a prominent horizontal bulkhead running across upper portion, "
                     "central to the image and surrounding television."},
    {"id": "E", "kind": "architecture", "name": "flooring", "removable": False,
     "description": "Wide plank, wood-look flooring covering the entire visible lower area of the "
                     "room."},
    {"id": "F", "kind": "architecture", "name": "light switches", "removable": False,
     "description": "Two white rectangular light switches, one below the bulkhead near the floor "
                     "lamp and another partially visible on the far right wall."},
    {"id": "G", "kind": "object", "name": "large wall clock", "removable": True,
     "description": "Round white clock with gold hands and tick marks, leaning on the mantel at "
                     "the left side of the alcove."},
    {"id": "H", "kind": "object", "name": "framed wedding photo", "removable": True,
     "description": "Square framed photo of a couple in ceremonial attire, resting against the "
                     "wall on the mantel to the right of the clock."},
    {"id": "I", "kind": "object", "name": "wooden plaque", "removable": True,
     "description": "Rectangular wooden plaque with engraved accents, placed on the mantel at the "
                     "far left."},
    {"id": "J", "kind": "object", "name": "decorative small box", "removable": True,
     "description": "Small square box with a shiny lid, on the mantel between the plaque and the "
                     "clock."},
    {"id": "K", "kind": "object", "name": "floor lamp", "removable": True,
     "description": "Tall tripod lamp with woven shade, turned on, standing to the right of the "
                     "alcove between the TV stand and the fireplace."},
    {"id": "L", "kind": "object", "name": "TV and stand", "removable": True,
     "description": "Large flat-screen TV on light wood stand with rattan-front cabinets, centered "
                     "along the main wall."},
    {"id": "M", "kind": "object", "name": "candles on TV stand", "removable": True,
     "description": "Multiple small candles in glass holders, grouped on top of the TV stand, "
                     "mostly to the left of the TV base."},
    {"id": "N", "kind": "object", "name": "framed photos on TV stand", "removable": True,
     "description": "Three small framed photographs in a row, placed in front of the central open "
                     "shelf of the TV stand."},
    {"id": "O", "kind": "object", "name": "assorted decor under TV stand", "removable": True,
     "description": "Assorted small decorative items including stones and keepsakes, placed on the "
                     "lower central shelf of the TV stand."},
    {"id": "P", "kind": "object", "name": "laundry basket", "removable": True,
     "description": "Tall cylindrical white woven laundry basket with light contents, on the floor "
                     "to the right of the TV stand near wall."},
]
