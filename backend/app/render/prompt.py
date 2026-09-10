"""Build the image-edit prompt in the three-section form the spike proved
(`spike/out/inventory_driven.txt`):

- architecture, verbatim, under "MUST REMAIN EXACTLY WHERE THEY ARE"
- kept objects under "KEEP these items"
- tapped objects (`remove_ids`) under "REMOVE these entirely"

The model does not fail from unwillingness — it fails from not knowing what is in
the picture. Naming every item is what makes preservation work.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..schemas import InventoryItem

_HEADER_KEEP = "MUST REMAIN EXACTLY WHERE THEY ARE, unchanged in shape, size and position:"
_HEADER_OBJECTS = "KEEP these items, in the same positions (you may restyle their finish):"
_HEADER_REMOVE = "REMOVE these entirely:"
_FOOTER = (
    "You may change wall colour, textiles, rugs, and add small decor. Do not move "
    "the camera. Do not add or remove any wall, opening or ceiling feature."
)


def build_prompt(
    *,
    style: str,
    user_prompt: str | None,
    items: Iterable[InventoryItem],
    remove_ids: Iterable[str],
    room_label: str | None,
) -> str:
    items = list(items)
    remove = set(remove_ids)
    where = room_label.strip().lower() if room_label and room_label.strip() else "room"
    style_phrase = style.replace("-", " ").replace("_", " ").strip() or "restyled"

    architecture = [i for i in items if i.kind == "architecture"]
    keep_objects = [i for i in items if i.kind != "architecture" and i.id not in remove]
    remove_objects = [i for i in items if i.kind != "architecture" and i.id in remove]

    lines = [f"Restyle this {where} in a {style_phrase} style."]
    if user_prompt and user_prompt.strip():
        lines.append(user_prompt.strip())

    lines += ["", _HEADER_KEEP, *_bullets(architecture)]
    if keep_objects:
        lines += ["", _HEADER_OBJECTS, *_bullets(keep_objects)]
    if remove_objects:
        lines += ["", _HEADER_REMOVE, *_bullets(remove_objects)]
    lines += ["", _FOOTER]
    return "\n".join(lines)


def _bullets(items: list[InventoryItem]) -> list[str]:
    return [f"- {i.description}" for i in items]
