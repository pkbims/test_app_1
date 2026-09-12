"""Build the image-edit prompt (`prompt_review/HANDOFF.md`, then the options
round in `options_review/HANDOFF.md`).

Structure: a role preamble, a per-style guide (attribute-shaped — palette,
materials, forms, what to avoid — never scene-shaped, so it never names a sofa,
chair or table and invites substitution of an item `KEEP` is holding), an
optional palette override, the room's inventory (architecture that must not
move, kept objects that may be refinished, removed objects), an optional ADD TO
THE ROOM block, then the rules — composed from the walls/furniture/decor/plants
options, with a fixed tail unaffected by any of them.

Removed items are rendered from `name`, never `description`. The spike proved that
naming an item in precise visual detail makes an image-edit model render it in
place — that is the entire `KEEP` mechanism. Using that same detailed-description
channel to ask for the opposite (removal) fights itself: negation is weak in
image-edit conditioning, detailed visual description is strong. `name` alone,
paired with a stated end state ("gone; the space it occupied is empty") gives the
model something positive to render instead of relying on suppression. Added
furniture is named the same restrained way — a display name only, no built
description — for the same reason: detail invites the model to redraw what is
already being kept to match it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ..schemas import InventoryItem

_PREAMBLE = """You are an expert interior designer, working here as a photo retoucher.

This photograph is a real room in a real customer's home. They want to see
THEIR room restyled. If they cannot recognise it as their own room, the work
has failed, however good the result looks on its own.

Your job: restyle the room in this photograph. Repaint it, refinish it and
redress it. Do not rebuild it."""

_HEADER_INVENTORY = """WHAT IS IN THE PHOTOGRAPH
This is a {where}. Every item below was identified in this specific photograph.
This list is what you are working with — nothing in it is generic."""

_HEADER_KEEP_ARCH = "MUST REMAIN EXACTLY WHERE THEY ARE, unchanged in shape, size and position:"
_HEADER_KEEP_OBJ = "KEEP these items, in the same positions (you may restyle their finish):"
_HEADER_GONE = "NOT IN THE ROOM — the customer has thrown these away:"

_REFINISH = """Restyle the kept items by changing only their material, colour and finish.
Their shape, size, silhouette and position stay exactly as they are."""

_EMPTY_ROOM = """The customer has removed everything that was in this room: furnish it fully
in this style, at a realistic scale for the room, leaving open floor space."""

_RULES_HEADER = "HOW TO DO THE WORK"

# The tail is unaffected by any option — same six bullets as before the options
# round, in the same order.
_RULES_TAIL = """- Anything listed as not in the room is gone. Do not draw it, and do not put a similar object in its place.
- Do not move the camera, change the framing, or change the angle of view.
- Do not add or remove any wall, opening or ceiling feature.
- Do not change the size, shape or proportions of the room.
- Where the style and the room disagree, the room wins.
- If you are unsure whether something is part of the building, leave it exactly as it is."""

_DECOR = {
    "small": "add small decor, including lamps",
    "large": "add decorations of any size, including large freestanding ones",
}
_DECOR_MINIMAL = (
    "add only a few chosen pieces of decor — one artwork, one lamp, one object — and "
    "leave most walls and surfaces clear"
)
_DECOR_PLENTY = (
    "add decor generously — layered art, lamps, cushions and objects on the walls "
    "and on every surface"
)

# ── walls (§4.3, D3) ─────────────────────────────────────────────────────────
_RULE_WALLS_UNCHANGED = "- The wall colour stays exactly as it is."
_RULE_SKIRTING = (
    "- Skirting boards, door frames and window frames match the walls: repaint "
    "them to suit if the walls are repainted, otherwise leave them. The ceiling "
    "and the floor stay exactly as they are."
)

# ── furniture (§4.4) ─────────────────────────────────────────────────────────
_HEADER_ADD = "ADD TO THE ROOM — the customer wants these pieces, which are not in the photograph:"
_ADD_FOOTER = """Place them where such pieces would naturally go, at a realistic scale for the room,
in the chosen style, without moving anything that is kept."""
_RULE_ADD_ONLY_LISTED = (
    "- Add only the pieces listed under ADD TO THE ROOM. Do not add any other furniture."
)
_RULE_NO_FURNITURE = "- Do not add any furniture."

# ── plants (§4.6) ────────────────────────────────────────────────────────────
_RULE_PLANTS = "- Add a few potted plants, placed where they would naturally sit."

# ── palette (§4.7) ───────────────────────────────────────────────────────────
_PALETTE_FAMILIES = {
    "neutral": "whites, greys and beiges, with colour coming only from wood and texture",
    "warm": "creams, terracotta, honey-toned wood and soft browns",
    "cool": "blues, greens, slate greys and pale wood",
    "bold": "strong, saturated colour on the walls or the largest pieces",
}

# ── options round (options_review/HANDOFF.md §7) ────────────────────────────────
ROOM_TYPES: dict[str, str] = {
    "living_room": "Living room",
    "bedroom": "Bedroom",
    "kitchen": "Kitchen",
    "dining_room": "Dining room",
    "home_office": "Home office",
    "kids_room": "Kids' room",
    "nursery": "Nursery",
    "bathroom": "Bathroom",
    "hallway": "Hallway",
    "studio": "Studio",
    "workshop": "Workshop",
    "server_room": "Server room",
}

# id -> {furniture id: display name}, HANDOFF §7.2. Backend validates
# `add_furniture` ids against the list for the resolved room type; the prompt's
# ADD TO THE ROOM block (§4.4) names them, lower-cased with an article.
FURNITURE_BY_ROOM_TYPE: dict[str, dict[str, str]] = {
    "living_room": {
        "sofa": "Sofa", "armchair": "Armchair", "coffee_table": "Coffee table",
        "side_table": "Side table", "tv_unit": "TV unit", "bookcase": "Bookcase",
        "sideboard": "Sideboard",
    },
    "bedroom": {
        "bed": "Bed", "bedside_table": "Bedside table", "wardrobe": "Wardrobe",
        "chest_of_drawers": "Chest of drawers", "desk": "Desk", "armchair": "Armchair",
        "dressing_table": "Dressing table",
    },
    "kitchen": {
        "dining_table": "Dining table", "chairs": "Chairs", "bar_stools": "Bar stools",
        "island": "Island", "open_shelving": "Open shelving",
    },
    "dining_room": {
        "dining_table": "Dining table", "chairs": "Chairs", "sideboard": "Sideboard",
        "bench": "Bench", "bar_cart": "Bar cart",
    },
    "home_office": {
        "desk": "Desk", "office_chair": "Office chair", "bookcase": "Bookcase",
        "storage_cabinet": "Storage cabinet", "armchair": "Armchair",
    },
    "kids_room": {
        "bed": "Bed", "desk": "Desk", "wardrobe": "Wardrobe",
        "toy_storage": "Toy storage", "bookcase": "Bookcase", "chair": "Chair",
    },
    "nursery": {
        "cot": "Cot", "changing_table": "Changing table", "nursing_chair": "Nursing chair",
        "wardrobe": "Wardrobe", "shelving": "Shelving",
    },
    "bathroom": {
        "vanity": "Vanity", "storage_cabinet": "Storage cabinet", "stool": "Stool",
        "shelving": "Shelving",
    },
    "hallway": {
        "console_table": "Console table", "bench": "Bench", "coat_stand": "Coat stand",
        "shoe_storage": "Shoe storage",
    },
    "studio": {
        "sofa_bed": "Sofa bed", "desk": "Desk", "table": "Table", "chairs": "Chairs",
        "shelving": "Shelving", "wardrobe": "Wardrobe",
    },
    "workshop": {
        "workbench": "Workbench", "stool": "Stool", "shelving": "Shelving",
        "tool_cabinet": "Tool cabinet",
    },
    "server_room": {
        "rack": "Rack", "desk": "Desk", "chair": "Chair", "cabinet": "Cabinet",
    },
}


def _where(room_type: str | None, room_label: str | None) -> str:
    """The fallback chain in HANDOFF §3.4: resolved room type, else the room's
    free-text label, else the generic word."""
    if room_type:
        display = ROOM_TYPES.get(room_type)
        if display:
            return display.lower()
    if room_label and room_label.strip():
        return room_label.strip().lower()
    return "room"


def _article(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


def _add_furniture_block(ids: list[str], room_type: str | None) -> list[str]:
    names = FURNITURE_BY_ROOM_TYPE.get(room_type, {}) if room_type else {}
    lines = [_HEADER_ADD]
    for fid in ids:
        display = (names.get(fid) or fid.replace("_", " ")).lower()
        lines.append(f"- {_article(display)} {display}")
    lines.append(_ADD_FOOTER)
    return lines


def _palette_line(palette: str, walls: str) -> str:
    family = _PALETTE_FAMILIES.get(palette, palette)
    if walls == "leave":
        return (
            f"Override the palette above: use {family}, except the walls, which keep "
            "their current colour. Keep the materials, forms and everything else in "
            "the guide as described."
        )
    return (
        f"Override the palette above: use {family}. Keep the materials, forms and "
        "everything else in the guide as described."
    )


def _decor_phrase(decor: str, known: "Style | None") -> str:
    if decor == "minimal":
        return _DECOR_MINIMAL
    if decor == "plenty":
        return _DECOR_PLENTY
    return _DECOR[known.decor_scale] if known is not None else _DECOR["small"]


def _rules_block(*, walls: str, decor_phrase: str, add_active: bool, plants: bool) -> str:
    if walls == "repaint":
        first = f"- You may change wall colour, textiles, rugs, and {decor_phrase}."
    else:
        first = f"- You may change textiles, rugs, and {decor_phrase}."

    lines = [_RULES_HEADER, first]
    if walls != "repaint":
        lines.append(_RULE_WALLS_UNCHANGED)
    lines.append(_RULE_SKIRTING)
    lines.append(_RULE_ADD_ONLY_LISTED if add_active else _RULE_NO_FURNITURE)
    if plants:
        lines.append(_RULE_PLANTS)
    lines.append(_RULES_TAIL)
    return "\n".join(lines)


@dataclass(frozen=True)
class Style:
    name: str  # display name, e.g. "Scandinavian"
    summary: str  # the clause after the colon in the header line
    guide: str  # the four "- ..." lines, verbatim, newline-joined
    decor_scale: str  # "small" | "large"


STYLES: dict[str, Style] = {
    "warm-minimal": Style(
        name="Warm minimal",
        summary="soft, tonal and quiet, in diffuse daylight.",
        guide="\n".join([
            "- Palette: oat, greige, sand and off-white in one tonal family; no black, no strong "
            "contrast; at most a soft clay accent.",
            "- Materials: lime plaster, boucle, undyed cotton and linen, travertine, pale unpolished "
            "stone, matte ceramic.",
            "- Forms and pieces: soft rounded upholstery with low arms; plinth and slab forms in "
            "stone; one large floor vase; sheer full-height curtains; a single dried branch; a "
            "deep-pile plain rug.",
            "- Avoid: pattern of any kind, visible hardware, black metal, cool greys, gloss, busy "
            "surfaces, and anything that reads as a knick-knack.",
        ]),
        decor_scale="small",
    ),
    "scandi": Style(
        name="Scandinavian",
        summary="bright, warm and uncluttered, in soft natural daylight.",
        guide="\n".join([
            "- Palette: white and chalky off-white walls; pale oak, ash and birch wood; light grey "
            "and greige textiles; matte black metal, sparingly; at most one muted accent colour "
            "(sage, dusty blue, clay).",
            "- Materials: untreated or lightly whitewashed wood, wool, linen, boucle, rattan, jute, "
            "matte ceramic, sheepskin.",
            "- Forms and pieces: slim tapered wood legs, low profiles, simple rounded sculptural "
            "shapes; a woven jute or flatweave wool rug; a paper or opal-glass globe pendant; "
            "linen curtains hung high; a sheepskin or chunky knit throw; one or two potted plants "
            "in plain ceramic; a few well-spaced ceramic or glass objects.",
            "- Avoid: ornate carving, gilding, brass flourishes, heavy dark or red-toned wood, "
            "glossy black, busy patterns, velvet, and clutter. Leave most surfaces empty.",
        ]),
        decor_scale="small",
    ),
    "japandi": Style(
        name="Japandi",
        summary="low, muted and handmade, in soft shadow.",
        guide="\n".join([
            "- Palette: warm off-white, muted clay, greige and soft charcoal; walnut and pale ash "
            "together; nothing bright, nothing pure white.",
            "- Materials: matte-oiled wood, paper, tatami and rush, raw-edged linen, unglazed and "
            "crackle-glazed ceramic, bamboo, dark iron.",
            "- Forms and pieces: furniture low and close to the floor; slatted screens; paper "
            "lanterns; a single stem in a rough vessel; floor cushions; a low platform bench; one "
            "deliberately imperfect handmade object.",
            "- Avoid: bright white, chrome, gloss, tall or bulky forms, matching sets, pattern, "
            "sheepskin, and anything that looks new and mass-produced.",
        ]),
        decor_scale="small",
    ),
    "modern-coastal": Style(
        name="Modern coastal",
        summary="airy and sun-bleached, in bright daylight.",
        guide="\n".join([
            "- Palette: chalk white and bleached driftwood, with sea blue, soft aqua and pale sand; "
            "daylight, never lamplight.",
            "- Materials: rattan and cane, washed linen slipcovers, rope, limed and weathered wood, "
            "seagrass, unglazed white ceramic.",
            "- Forms and pieces: loose slipcovered seating; cane-backed frames; a seagrass or "
            "flatweave rug; sheer white curtains; large woven baskets; a few shell or coral "
            "objects; generous open floor.",
            "- Avoid: dark wood, heavy drapery, gold, gloss, saturated colour, and literal nautical "
            "motifs — no anchors, no rope as decoration, no stripes on everything.",
        ]),
        decor_scale="small",
    ),
    "mid-century": Style(
        name="Mid-Century Modern",
        summary="warm walnut and confident colour, in even daylight.",
        guide="\n".join([
            "- Palette: walnut and teak browns with mustard, burnt orange, olive and teal; warm "
            "white walls.",
            "- Materials: oiled walnut and teak, tweed and wool upholstery, brass, smoked glass, "
            "moulded plywood, earth-glazed ceramic.",
            "- Forms and pieces: splayed tapered legs; low horizontal casework; welted or lightly "
            "tufted upholstery; a starburst or sputnik light; a geometric-pattern rug; an arced "
            "floor lamp; a bar cart; a large-leaved potted plant.",
            "- Avoid: distressed or reclaimed finishes, chrome-heavy modernism, farmhouse and "
            "country motifs, pastels, ornate carving, and crowded surfaces.",
        ]),
        decor_scale="small",
    ),
    "industrial": Style(
        name="Industrial",
        summary="raw, heavy and utilitarian, in hard directional light.",
        guide="\n".join([
            "- Palette: concrete grey, black, oxidised steel and warm tan leather; brick red only "
            "where brick already exists.",
            "- Materials: blackened and galvanised steel, aged tan leather, reclaimed timber, "
            "concrete, wire mesh, clear bulb glass.",
            "- Forms and pieces: heavy square-section metal frames; leather club seating; "
            "factory-style pendants on long flex; visible bolts and castors; a metal locker or "
            "trolley; a worn kilim; one large monochrome print.",
            "- Avoid: pastels, chintz, gloss paint, delicate legs, fitted upholstery, gold, and "
            "anything precious or fragile-looking.",
        ]),
        decor_scale="small",
    ),
    "traditional": Style(
        name="Traditional",
        summary="symmetrical, warm and settled, in soft lamplight.",
        guide="\n".join([
            "- Palette: warm neutrals with navy, deep red, forest green and soft gold; cream walls "
            "with white trim.",
            "- Materials: cherry and mahogany-toned wood, damask and plain cotton upholstery, wool "
            "rugs, polished brass, silk lampshades.",
            "- Forms and pieces: symmetrical arrangements; rolled arms; turned or cabriole legs; a "
            "skirted ottoman; framed landscape and botanical prints hung in pairs; table lamps "
            "flanking the seating; a bordered patterned rug.",
            "- Avoid: industrial metal, exposed hardware, neon or fluorescent colour, minimalism, "
            "asymmetry, and anything that reads as ultra-modern.",
        ]),
        decor_scale="small",
    ),
    "art-deco": Style(
        name="Art Deco",
        summary="geometric, lacquered and glamorous, in warm pooled light.",
        guide="\n".join([
            "- Palette: black and cream with emerald, sapphire and oxblood; polished brass and gold "
            "throughout.",
            "- Materials: lacquered ebony, brass and gold metal, velvet, strongly veined marble, "
            "mirrored and fluted glass, shagreen.",
            "- Forms and pieces: fan, sunburst and chevron motifs; fluted and scalloped fronts; "
            "curved velvet upholstery; a mirrored or marble-topped bar; a geometric inlaid rug; a "
            "stepped or tiered light fitting; an oversized round mirror in a brass frame.",
            "- Avoid: rustic or distressed wood, pastels, casual slipcovers, farmhouse and coastal "
            "motifs, matte or unfinished surfaces, and visible clutter.",
        ]),
        decor_scale="small",
    ),
    "dark-academia": Style(
        name="Dark Academia",
        summary="bookish, shadowed and worn-in, in low warm lamplight.",
        guide="\n".join([
            "- Palette: deep forest green, oxblood, ink and chocolate against smoke-stained cream; "
            "warm low lamplight only, never daylight.",
            "- Materials: dark stained oak and mahogany, worn tan and burgundy leather, heavy wool, "
            "brass, aged paper, dark marble.",
            "- Forms and pieces: shelves packed to the ceiling with books; a leather chesterfield or "
            "wingback; a writing desk with a green glass lamp; framed prints and maps hung "
            "densely; a globe; a worn Persian rug; heavy curtains half-drawn.",
            "- Avoid: bright or cool light, white walls, pale wood, minimalism, plastic, chrome, and "
            "anything new-looking or brightly coloured.",
        ]),
        decor_scale="small",
    ),
    "maximalism": Style(
        name="Maximalism",
        summary="layered, saturated and unapologetic, in warm even light.",
        guide="\n".join([
            "- Palette: several saturated colours at once — emerald, fuchsia, ochre, cobalt — "
            "layered rather than balanced, with no neutral resting point.",
            "- Materials: velvet, printed cotton, patterned wallpaper, lacquer, brass, ceramic, and "
            "mixed woods that deliberately do not match.",
            "- Forms and pieces: a gallery wall hung frame-to-frame; layered rugs; pattern over "
            "pattern; boldly upholstered seating with many clashing cushions; shelves crowded with "
            "books and objects; a statement chandelier; plants at several heights.",
            "- Avoid: empty walls, bare surfaces, a single neutral palette, matching furniture sets, "
            "and restraint of any kind.",
        ]),
        decor_scale="small",
    ),
    "moroccan": Style(
        name="Moroccan",
        summary="warm, patterned and lantern-lit, in low golden light.",
        guide="\n".join([
            "- Palette: terracotta, saffron, deep teal and rose against warm lime-washed off-white; "
            "brass warmth throughout.",
            "- Materials: hand-glazed tile, pierced brass, wool kilim and Beni rugs, leather "
            "pouffes, carved wood, hand-block-printed cotton.",
            "- Forms and pieces: low seating banked with cushions along the wall; pierced brass "
            "lanterns throwing patterned light; layered flatweave rugs; a carved side table; a "
            "large brass tray table; a potted palm.",
            "- Avoid: minimalism, cool greys, chrome, matching sets, tall Western sofas. Do not add "
            "arches, niches or carved plasterwork — this is a room, not a riad.",
        ]),
        decor_scale="small",
    ),
    "cottagecore": Style(
        name="Cottagecore",
        summary="soft, floral and sun-faded, in gentle daylight.",
        guide="\n".join([
            "- Palette: soft cream, sage, butter yellow and faded rose; sun-bleached rather than "
            "saturated.",
            "- Materials: floral and printed cotton, gingham, crochet and lace, painted wood, "
            "enamelware, wicker, stoneware.",
            "- Forms and pieces: slipcovered or floral upholstery; mismatched painted chairs; open "
            "shelves of mismatched crockery; dried flowers and fresh cuttings in jugs; a patchwork "
            "quilt; gathered curtains; a wicker basket of blankets.",
            "- Avoid: black, chrome, gloss, hard geometry, sleek modern forms, industrial materials, "
            "and anything that reads corporate or new.",
        ]),
        decor_scale="small",
    ),
    "rustic-farmhouse": Style(
        name="Rustic Farmhouse",
        summary="weathered, practical and warm, in daylight.",
        guide="\n".join([
            "- Palette: warm white and putty with weathered grey-brown wood; black metal accents; "
            "a muted denim blue or sage.",
            "- Materials: reclaimed and knotty wood, board panelling, galvanised metal, jute, "
            "ticking stripe and grain-sack linen, stoneware.",
            "- Forms and pieces: chunky plank tables and benches; slipcovered seating; a black metal "
            "cage or lantern pendant; open wooden shelving; enamel jugs; a woven basket by the "
            "hearth; a simple striped rug.",
            "- Avoid: gold, gloss, velvet, ornate carving, saturated colour, chrome, sleek "
            "minimalism, and anything delicate.",
        ]),
        decor_scale="small",
    ),
    "mediterranean": Style(
        name="Mediterranean",
        summary="sun-washed, earthen and calm, in strong daylight.",
        guide="\n".join([
            "- Palette: lime-washed white and warm sand with olive green, terracotta and a single "
            "deep blue; strong sunlight.",
            "- Materials: rough lime plaster, terracotta tile, olive and pine wood, raw linen, woven "
            "rush, hand-thrown glazed ceramic.",
            "- Forms and pieces: chunky plaster-toned upholstery; rush-seated frames; terracotta "
            "pots holding olive or citrus; hand-painted ceramic bowls; a rough wooden bench; "
            "simple linen curtains; a jute rug.",
            "- Avoid: gloss, chrome, dark wood, heavy drapery, pastels, fitted carpet. Do not add "
            "arches, niches or ceiling beams.",
        ]),
        decor_scale="small",
    ),
    "cyberpunk": Style(
        name="Cyberpunk",
        summary="a dark room lit entirely by artificial coloured light, after dark.",
        guide="\n".join([
            "- Palette: near-black and deep charcoal surfaces; saturated magenta, cyan and electric "
            "violet light; one acid green or amber accent. No daylight, no warm white.",
            "- Materials: black lacquer, brushed gunmetal, smoked glass, matte black plastic, vinyl, "
            "bare concrete, wire mesh.",
            "- Forms and pieces: low slab seating in dark upholstery; LED strips along edges, "
            "skirtings and under furniture; neon signage glow on one wall; visible cable runs; a "
            "lit screen; a glossy floor reflecting the coloured light; a single plant uplit from "
            "below.",
            "- Avoid: daylight, warm wood tones, beige, brass, florals, natural linen or wool, cosy "
            "textures, clutter. Do not turn the room into a spaceship, a city skyline or a film "
            "set — it is an ordinary room, lit and finished differently.",
        ]),
        decor_scale="small",
    ),
    "memphis": Style(
        name="Memphis",
        summary="flat, primary and deliberately absurd, in bright even light.",
        guide="\n".join([
            "- Palette: primary red, yellow and blue with hot pink, mint, and black-and-white "
            "squiggle, on a white ground; flat colour with little shading.",
            "- Materials: laminate, terrazzo, matte plastic, powder-coated metal, coloured glass, "
            "patterned melamine.",
            "- Forms and pieces: forms built from stacked geometric solids — circles, triangles, "
            "zigzags; squiggle and confetti pattern; asymmetric mirrors; a terrazzo top; tubular "
            "metal frames; lamps in clashing shapes.",
            "- Avoid: wood tones, neutrals, symmetry, natural texture, subtlety, and anything "
            "tasteful or muted.",
        ]),
        decor_scale="small",
    ),
    "christmas": Style(
        name="Christmas",
        summary="the room dressed for Christmas, in warm firelight and fairy-light glow.",
        guide="\n".join([
            "- Palette: deep green and red with warm gold and white; low warm light from the fire, "
            "candles and string lights.",
            "- Materials: fir and pine foliage, red velvet ribbon, knitted wool, brass and gold "
            "baubles, kraft paper, candlelight.",
            "- Forms and pieces: a decorated fir tree with lights and wrapped gifts beneath it; "
            "garland along the mantel and shelves; stockings hung; a wreath; warm string lights; "
            "a knitted throw; grouped candles.",
            "- Avoid: cool or blue-white light, plastic novelty and inflatables, clashing neon, and "
            "decoration so dense the room is hidden. Leave the room's wall colour, flooring and "
            "furniture finishes as they are — this style decorates the room, it does not restyle it.",
        ]),
        decor_scale="large",
    ),
    "valentines": Style(
        name="Valentine's Day",
        summary="the room dressed for Valentine's Day, in soft warm light.",
        guide="\n".join([
            "- Palette: blush and dusty rose with deep red and white; soft warm light, candles "
            "rather than overhead lighting.",
            "- Materials: rose petals, satin and velvet ribbon, tulle, foil balloons, fresh roses, "
            "candle wax.",
            "- Forms and pieces: heart balloons clustered at the ceiling; rose petals scattered on "
            "floor and surfaces; vases of red and pink roses; candles grouped on the mantel and "
            "tables; a garland of paper hearts; a soft pink throw and cushions.",
            "- Avoid: cold light, garish plastic, and decoration so dense the room is hidden. Leave "
            "the room's wall colour, flooring and furniture finishes as they are — this style "
            "decorates the room, it does not restyle it.",
        ]),
        decor_scale="large",
    ),
    # ── DecorAI parity batch (60-style picker) — ids are ours, names match DecorAI
    # exactly. Existing 18 ids/names are unchanged except two cosmetic renames
    # (scandi -> "Scandinavian", mid-century -> "Mid-Century Modern") noted above;
    # warm-minimal and rustic-farmhouse are not DecorAI names and stay as extras.
    "minimalistic": Style(
        name="Minimalistic",
        summary="pared to essentials, calm and uncluttered, in even daylight.",
        guide="\n".join([
            "- Palette: white, off-white and one soft neutral; no more than one accent colour, "
            "used sparingly; nothing saturated.",
            "- Materials: matte painted surfaces, plain oak or ash, frosted or clear glass, "
            "unpolished concrete, plain cotton and wool.",
            "- Forms and pieces: low-slung furniture with clean rectilinear lines; a single "
            "freestanding sculptural object; open shelving left mostly empty; one plain floor "
            "lamp; a rug with no pattern, if any.",
            "- Avoid: ornament of any kind, more than one pattern, visible clutter, warm wood "
            "tones in excess, anything decorative without a function.",
        ]),
        decor_scale="small",
    ),
    "modern": Style(
        name="Modern",
        summary="clean-lined and confident, with high-contrast materials, in bright even light.",
        guide="\n".join([
            "- Palette: white and warm grey with black, walnut brown and one saturated accent "
            "(deep blue or rust); contrast used deliberately.",
            "- Materials: polished chrome and matte black metal, tempered glass, walnut veneer, "
            "leather, poured concrete.",
            "- Forms and pieces: low modular seating with sharp rectilinear edges; a glass or "
            "marble-topped coffee table; a sculptural pendant light; a large abstract canvas; a "
            "geometric-pattern rug in neutral tones.",
            "- Avoid: ornate carving, floral pattern, distressed or rustic finishes, pastel "
            "colour, clutter on surfaces.",
        ]),
        decor_scale="small",
    ),
    "transitional": Style(
        name="Transitional",
        summary="traditional shapes softened into a simplified, neutral palette, in soft daylight.",
        guide="\n".join([
            "- Palette: warm greige, oatmeal and soft white, with navy or charcoal as the only "
            "deep accent.",
            "- Materials: matte-finish oak, linen and plain performance-weave upholstery, "
            "brushed nickel, honed marble.",
            "- Forms and pieces: rolled-arm upholstery in a plain fabric; simple turned or "
            "tapered wood legs; a drum-shade lamp; a bordered but low-contrast rug; furniture "
            "arranged in understated symmetrical pairs.",
            "- Avoid: heavy ornate carving, high-gloss finishes, bold pattern, anything that "
            "reads as strictly period or strictly ultra-modern.",
        ]),
        decor_scale="small",
    ),
    "contemporary": Style(
        name="Contemporary",
        summary="of-the-moment and curated, softly curved, in bright natural light.",
        guide="\n".join([
            "- Palette: warm white and taupe with one current accent (sage, terracotta or dusty "
            "blue); tonal layering over hard contrast.",
            "- Materials: matte metal, engineered stone, bouclé, blonde or ashy wood, natural "
            "undyed textiles.",
            "- Forms and pieces: curved-arm upholstered seating; an organic free-form coffee "
            "table; a sculptural floor lamp; oversized understated art; a jute or low-pile "
            "plain rug.",
            "- Avoid: heavy period ornament, dated 1980s-1990s motifs, dark wood-heavy schemes, "
            "busy pattern mixing.",
        ]),
        decor_scale="small",
    ),
    "japanese": Style(
        name="Japanese",
        summary="spare, natural and ordered around light and shadow, in soft filtered daylight.",
        guide="\n".join([
            "- Palette: unbleached tatami gold, warm wood brown, charcoal and paper white; no "
            "bright colour.",
            "- Materials: hinoki and cedar wood, washi paper, tatami rush matting, bamboo, "
            "black iron, unglazed ceramic.",
            "- Forms and pieces: a low table for floor seating; a shoji lattice screen or door; "
            "a single alcove-style display of one scroll or ikebana arrangement; floor cushions "
            "in place of raised furniture; exposed wood beam detailing.",
            "- Avoid: upholstered Western furniture, bright colour, clutter, synthetic "
            "materials, ornament that breaks the room's quiet symmetry.",
        ]),
        decor_scale="small",
    ),
    "eclectic": Style(
        name="Eclectic",
        summary="confidently mixed, personal and layered, in warm daylight.",
        guide="\n".join([
            "- Palette: a curated mix of two or three unrelated colour families, tied together "
            "by one repeated accent tone.",
            "- Materials: mixed woods, vintage brass, woven natural fibre, velvet and printed "
            "cotton together.",
            "- Forms and pieces: furniture from different eras placed together; a gallery wall "
            "of mismatched frames; one bold vintage statement piece; layered rugs; objects that "
            "look collected rather than matched.",
            "- Avoid: a single matching furniture set, monochrome schemes, anything that reads "
            "as a showroom, empty walls.",
        ]),
        decor_scale="small",
    ),
    "rustic": Style(
        name="Rustic",
        summary="rough-hewn, heavy and close to the material, in warm low light.",
        guide="\n".join([
            "- Palette: bark brown, oatmeal, forest green and charcoal; nothing polished or "
            "bright.",
            "- Materials: rough-sawn and log-hewn timber, stacked stone, cast iron, cowhide, "
            "heavy wool.",
            "- Forms and pieces: a chunky exposed-joinery table; a stone or brick fireplace "
            "surround; wrought-iron light fixtures; a cowhide or heavy wool rug; carved-wood or "
            "antler accents.",
            "- Avoid: high gloss, glass and chrome, pastel colour, delicate or spindly forms, "
            "anything that reads as manufactured.",
        ]),
        decor_scale="small",
    ),
    "bohemian": Style(
        name="Bohemian",
        summary="layered, global and free-spirited, in warm golden light.",
        guide="\n".join([
            "- Palette: terracotta, mustard, deep burgundy and jewel tones over a warm neutral "
            "base.",
            "- Materials: macrame, rattan, kilim and ikat textiles, unlacquered brass, raw wood.",
            "- Forms and pieces: floor cushions and a low platform for seating; heavily layered "
            "rugs; a macrame wall hanging; trailing plants on plant stands at several heights; a "
            "rattan peacock-style chair.",
            "- Avoid: matching furniture sets, cool greys, hard minimalism, rigid symmetry, "
            "empty walls.",
        ]),
        decor_scale="small",
    ),
    "farmhouse": Style(
        name="Farmhouse",
        summary="crisp white and black-accented, practical and bright, in clear daylight.",
        guide="\n".join([
            "- Palette: white and warm white walls with black metal accents and one soft "
            "neutral (greige or sage).",
            "- Materials: shiplap-look panelling, painted wood, galvanised and matte black "
            "metal, cotton canvas, stoneware.",
            "- Forms and pieces: a trestle-leg table; open shelving with plain white dishware; "
            "a black metal cage or lantern pendant; a woven or jute rug; slipcovered seating.",
            "- Avoid: dark heavy wood, ornate carving, saturated colour, glossy finishes, "
            "clutter of small decor.",
        ]),
        decor_scale="small",
    ),
    "vintage": Style(
        name="Vintage",
        summary="gently worn and time-collected, in warm lamplight.",
        guide="\n".join([
            "- Palette: faded rose, sage, mustard and cream, softened as if sun-aged.",
            "- Materials: worn leather, aged brass, walnut and mahogany veneer, chintz and "
            "lace, milk glass.",
            "- Forms and pieces: a curved-arm upholstered piece in a period silhouette; a "
            "mirrored or marquetry side table; framed vintage prints; a fringed lampshade; "
            "mismatched dining chairs around a shared table.",
            "- Avoid: anything glossy or obviously new, minimalist forms, cool industrial "
            "materials, stark white.",
        ]),
        decor_scale="small",
    ),
    "victorian": Style(
        name="Victorian",
        summary="ornate, layered and richly coloured, in a warm gaslight-like glow.",
        guide="\n".join([
            "- Palette: deep burgundy, forest green and navy with gold accents; patterned "
            "wallpaper tones.",
            "- Materials: dark mahogany and walnut, velvet and damask upholstery, wrought iron, "
            "stained glass, brass.",
            "- Forms and pieces: a tufted chesterfield or fainting couch; a marble-topped "
            "console on carved legs; heavy tasseled drapery; an ornate gilt-framed mirror; a "
            "patterned Persian-style rug.",
            "- Avoid: minimalism, bare walls, industrial or raw materials, pale or cool colour, "
            "anything sparse.",
        ]),
        decor_scale="small",
    ),
    "retro": Style(
        name="Retro",
        summary="playful and boldly coloured, evoking the 1960s-70s, in warm even light.",
        guide="\n".join([
            "- Palette: avocado green, burnt orange, mustard yellow and brown, with an "
            "occasional shot of hot pink.",
            "- Materials: shag-pile textiles, moulded plastic, chrome, laminate, cork.",
            "- Forms and pieces: a bubble or egg-shaped hanging seat; a sunburst clock; a lava "
            "lamp; a shag rug; bold geometric or psychedelic-pattern textiles.",
            "- Avoid: muted neutrals, minimalism, matte natural materials, anything that reads "
            "as restrained or corporate.",
        ]),
        decor_scale="small",
    ),
    "zen": Style(
        name="Zen",
        summary="quiet, spare and meditative, in soft diffuse light.",
        guide="\n".join([
            "- Palette: sand, stone grey, moss green and unbleached white; nothing saturated.",
            "- Materials: smooth river stone, bamboo, unglazed ceramic, raw linen, light "
            "unfinished wood.",
            "- Forms and pieces: a low platform seating area; a small tabletop water feature or "
            "single stone arrangement; one bonsai or single-stem arrangement; a plain floor "
            "cushion; wide open, uncluttered floor space.",
            "- Avoid: pattern, clutter, bright colour, ornate furniture, more than a few "
            "objects visible at once.",
        ]),
        decor_scale="small",
    ),
    "biophilic": Style(
        name="Biophilic",
        summary="green, textured and nature-immersed, in bright natural daylight.",
        guide="\n".join([
            "- Palette: leaf green, warm terracotta and natural wood tones against white or "
            "stone.",
            "- Materials: living plant walls, raw and reclaimed wood, natural stone, jute, "
            "cork, unfinished rattan.",
            "- Forms and pieces: an abundance of large potted plants at multiple heights; a "
            "wood-slat room divider; a stone or pebble accent surface; a rattan hanging chair; "
            "a small water feature.",
            "- Avoid: synthetic materials, artificial-looking plastic plants, dark or "
            "windowless-feeling schemes, hard minimalism with no greenery.",
        ]),
        decor_scale="small",
    ),
    "solarpunk": Style(
        name="Solarpunk",
        summary="optimistic, green-technological and sun-bright, in vivid daylight.",
        guide="\n".join([
            "- Palette: leaf green and sky blue with warm terracotta and brushed gold accents; "
            "bright, never dark.",
            "- Materials: living plants integrated with reclaimed wood, glass, woven natural "
            "fibre, warm-toned recycled metal.",
            "- Forms and pieces: climbing plants trained along a trellis or frame; a "
            "stained-glass-look panel catching light; greenery mixed with clean modern "
            "furniture; a solar-lantern-style light fixture; an open, airy arrangement.",
            "- Avoid: dark or industrial-dystopian materials, muted or grey palettes, synthetic "
            "plastic finishes, cramped arrangement.",
        ]),
        decor_scale="small",
    ),
    "tropical": Style(
        name="Tropical",
        summary="lush, breezy and colourful, in bright humid-feeling daylight.",
        guide="\n".join([
            "- Palette: leaf green, hibiscus pink and sunny yellow against white or rattan tan.",
            "- Materials: rattan, bamboo, palm-leaf print textiles, teak, woven raffia.",
            "- Forms and pieces: oversized leafy plants such as monstera or palm; a rattan "
            "peacock or papasan-style chair; a wood-look ceiling fan; botanical-print "
            "textiles; a woven pendant light.",
            "- Avoid: cool greys, heavy dark wood, minimalism, wintery or muted colour, "
            "synthetic-looking plastic greenery.",
        ]),
        decor_scale="small",
    ),
    "parisian": Style(
        name="Parisian",
        summary="elegant, effortless and softly aged, in soft grey daylight.",
        guide="\n".join([
            "- Palette: warm white, soft grey and black, with a single muted rose or blue "
            "accent.",
            "- Materials: herringbone oak, aged brass, marble, linen, gilt-edged mirror glass.",
            "- Forms and pieces: a Louis-style chair with plain upholstery; a marble-topped "
            "console; a large gilt-framed mirror leaning against the wall; a slender brass "
            "floor lamp; a cafe-style bistro chair as an accent.",
            "- Avoid: bulky modern furniture, saturated colour, matching furniture sets, "
            "plastic or laminate finishes, clutter.",
        ]),
        decor_scale="small",
    ),
    "brutalist": Style(
        name="Brutalist",
        summary="raw, monolithic and unapologetically concrete, in stark directional light.",
        guide="\n".join([
            "- Palette: concrete grey, charcoal and off-white; no accent colour.",
            "- Materials: raw poured concrete, unfinished steel, exposed brick, dark oiled "
            "wood.",
            "- Forms and pieces: heavy geometric furniture with blocky, unornamented forms; a "
            "sculptural concrete or stone side table; a single oversized pendant in raw metal; "
            "minimal sculptural decor; a hard-edged rug or bare floor.",
            "- Avoid: soft textiles in excess, pastel colour, ornate detail, anything delicate "
            "or highly decorative.",
        ]),
        decor_scale="small",
    ),
    "vaporwave": Style(
        name="Vaporwave",
        summary="neon pastel and retro-digital, lit by artificial glow, after dark.",
        guide="\n".join([
            "- Palette: pastel pink and cyan-teal neon over a dark or lavender-grey base; no "
            "natural earth tones.",
            "- Materials: glossy laminate, chrome, mirrored and iridescent glass, matte black "
            "plastic.",
            "- Forms and pieces: neon or LED strip lighting along edges; a checkerboard-pattern "
            "floor or rug; a glossy geometric console; retro-grid or CRT-style wall art; "
            "palm-silhouette accents.",
            "- Avoid: warm wood tones, natural fibre, muted earthy colour, daylight, cosy "
            "traditional furniture. Do not turn the window view into a city skyline or add a "
            "cityscape — it is an ordinary room, lit and finished differently.",
        ]),
        decor_scale="small",
    ),
    "hollywood-regency": Style(
        name="Hollywood Regency",
        summary="glamorous, high-contrast and mirrored, in warm dramatic light.",
        guide="\n".join([
            "- Palette: black and white or cream with bold jewel accents (emerald, fuchsia or "
            "royal blue) and gold.",
            "- Materials: lacquered wood, mirrored and lucite surfaces, velvet, gold leaf, "
            "faux fur.",
            "- Forms and pieces: a tufted velvet seat with slender gold legs; a mirrored "
            "console or bar cart; an oversized starburst mirror; a crystal or geometric "
            "chandelier; a bold leopard-print accent textile.",
            "- Avoid: rustic or reclaimed wood, muted earth tones, matte natural finishes, "
            "understatement of any kind. Do not render any visible brand names, logos or text "
            "on books, packaging or objects.",
        ]),
        decor_scale="small",
    ),
    "art-nouveau": Style(
        name="Art Nouveau",
        summary="flowing, organic and hand-crafted, in soft warm light.",
        guide="\n".join([
            "- Palette: sage green, mustard, deep plum and warm gold against cream.",
            "- Materials: carved wood with whiplash curves, stained glass, wrought iron, "
            "brass, hand-painted tile.",
            "- Forms and pieces: furniture with sinuous, plant-inspired curved lines; a "
            "stained-glass lamp with organic floral motifs; wrought-iron detailing on light "
            "fixtures; a botanical mural-style artwork; a curved-back upholstered seat.",
            "- Avoid: straight rigid lines, minimalism, industrial materials, geometric Art "
            "Deco motifs, plain unornamented surfaces.",
        ]),
        decor_scale="small",
    ),
    "korean-hanok": Style(
        name="Korean Hanok",
        summary="quiet, wood-framed and floor-oriented, in soft natural light.",
        guide="\n".join([
            "- Palette: warm wood brown, whitewashed clay walls, charcoal roof-tile grey; no "
            "bright colour.",
            "- Materials: unfinished pine and hardwood, hanji mulberry paper, woven floor "
            "matting, celadon ceramic, plain cotton.",
            "- Forms and pieces: a low wooden table for floor seating; a hanji-paper lattice "
            "screen or door; a single celadon vase; floor cushions instead of raised furniture; "
            "exposed wood beam detailing.",
            "- Avoid: upholstered Western furniture, bright synthetic colour, glossy finishes, "
            "clutter, tall raised furniture that blocks the floor lines.",
        ]),
        decor_scale="small",
    ),
    "southwestern": Style(
        name="Southwestern",
        summary="sun-baked, earthen and pattern-rich, in warm desert light.",
        guide="\n".join([
            "- Palette: terracotta, adobe tan, turquoise and rust against warm white.",
            "- Materials: adobe-look plaster, hand-woven wool, leather, turquoise-inlaid "
            "silver accents, weathered wood.",
            "- Forms and pieces: a Navajo or Saltillo-pattern rug; leather-and-wood accent "
            "seating; woven wall hangings; a cowhide or leather pouf; terracotta pottery.",
            "- Avoid: cool greys and blues, glossy modern finishes, minimalism, pale "
            "Scandinavian wood, clutter of unrelated global patterns.",
        ]),
        decor_scale="small",
    ),
    "nordic-hygge": Style(
        name="Nordic Hygge",
        summary="cosy, candlelit and soft-textured, in warm low light.",
        guide="\n".join([
            "- Palette: warm white, oatmeal and soft grey with muted blush or clay accents.",
            "- Materials: chunky knit wool, sheepskin, pale oak, matte ceramic, beeswax "
            "candles.",
            "- Forms and pieces: deep upholstery piled with knit cushions and a chunky throw; a "
            "sheepskin draped over a simple wood-framed seat; clustered candles on a low "
            "surface; a soft wool rug; simple pale-wood open shelving.",
            "- Avoid: cold hard surfaces left unsoftened, bright overhead lighting, clutter, "
            "saturated or neon colour.",
        ]),
        decor_scale="small",
    ),
    "baroque": Style(
        name="Baroque",
        summary="opulent, dramatic and gilded, in a warm candlelit glow.",
        guide="\n".join([
            "- Palette: deep burgundy, royal blue and emerald with heavy gold ornament "
            "throughout.",
            "- Materials: gilded and carved wood, velvet and brocade, marble, crystal, ornate "
            "wrought iron.",
            "- Forms and pieces: heavily carved and gilded upholstered seating; a crystal "
            "chandelier; an ornate gilt mirror with scrollwork; richly tasseled drapery; a "
            "marble-topped table on carved legs.",
            "- Avoid: minimalism, plain unornamented surfaces, pale or neutral colour, "
            "industrial or raw materials, restraint of any kind.",
        ]),
        decor_scale="small",
    ),
    "bauhaus": Style(
        name="Bauhaus",
        summary="geometric, functional and primary-coloured, in bright even light.",
        guide="\n".join([
            "- Palette: white and black with primary red, yellow and blue used as flat "
            "accents.",
            "- Materials: tubular chrome steel, moulded plywood, leather, matte-painted "
            "surfaces, glass.",
            "- Forms and pieces: a tubular-steel cantilever seat; a geometric primary-colour "
            "wall composition; unornamented rectilinear shelving; a simple grid-pattern "
            "textile; a single functional pendant light.",
            "- Avoid: ornament or applied decoration, pastel or muted colour, traditional or "
            "period furniture forms, clutter.",
        ]),
        decor_scale="small",
    ),
    "futuristic": Style(
        name="Futuristic",
        summary="sleek, high-tech and curved, lit by cool ambient light.",
        guide="\n".join([
            "- Palette: white, silver and charcoal with one glowing accent colour (blue or "
            "violet light).",
            "- Materials: high-gloss white plastic and lacquer, brushed steel, smoked glass, "
            "integrated LED strip lighting.",
            "- Forms and pieces: a smooth curved-form seat with no visible legs; a sculptural "
            "pod-shaped chair; integrated ambient lighting along ceiling or floor lines; a "
            "glossy white console with no visible hardware; minimal screen-like art.",
            "- Avoid: natural wood tones, traditional ornament, warm lamplight, clutter, "
            "visible mechanical hardware. Do not turn the window view into a city skyline or "
            "add a cityscape — it is an ordinary room, lit and finished differently.",
        ]),
        decor_scale="small",
    ),
    "colonial": Style(
        name="Colonial",
        summary="symmetrical, dark-wood and formal, in warm lamplight.",
        guide="\n".join([
            "- Palette: deep mahogany brown, cream and hunter green with brass accents.",
            "- Materials: dark mahogany and cherry wood, wrought iron, toile and stripe "
            "fabric, brass.",
            "- Forms and pieces: a four-poster bed frame or wingback-shaped upholstery; a "
            "campaign-style chest with brass hardware; paneled or shuttered-look window "
            "treatments; a braided or oriental-style rug; furniture arranged in symmetrical "
            "pairs.",
            "- Avoid: bright saturated colour, minimalism, glossy modern surfaces, asymmetry, "
            "plastic or laminate finishes.",
        ]),
        decor_scale="small",
    ),
    "tudor": Style(
        name="Tudor",
        summary="half-timbered, heavy and medieval-leaning, in warm low light.",
        guide="\n".join([
            "- Palette: dark oak brown, cream plaster white and deep burgundy or forest green.",
            "- Materials: dark exposed timber beams, wrought iron, leaded glass, "
            "tapestry-weight fabric, stone.",
            "- Forms and pieces: a heavy carved oak table or chest; wrought-iron candle-style "
            "light fixtures; a stone or brick fireplace surround; a tapestry or heraldic wall "
            "hanging; leaded-look window styling.",
            "- Avoid: pale modern wood, minimalism, glossy finishes, bright colour, sleek "
            "contemporary furniture.",
        ]),
        decor_scale="small",
    ),
    "shaker": Style(
        name="Shaker",
        summary="plain, honest and finely made, in clear daylight.",
        guide="\n".join([
            "- Palette: warm white, soft grey-blue and natural wood tone; no ornament colour.",
            "- Materials: plain solid maple, cherry and pine, woven-seat chairs, wool, "
            "unadorned wrought iron.",
            "- Forms and pieces: a ladder-back chair with a woven seat; a wall-mounted peg "
            "rail for hanging items; a plain trestle table; simple unadorned cabinetry; a "
            "single plain oval box or basket.",
            "- Avoid: carving or applied ornament, upholstered excess, pattern, gilt or "
            "metallic finishes, clutter.",
        ]),
        decor_scale="small",
    ),
    "rococo": Style(
        name="Rococo",
        summary="delicate, curved and pastel-gilded, in soft romantic light.",
        guide="\n".join([
            "- Palette: powder pink, mint and pale gold against cream or ivory.",
            "- Materials: gilded carved wood, silk damask, porcelain, gilt bronze, mirrored "
            "glass.",
            "- Forms and pieces: an asymmetrical curved-leg settee; a gilt-framed oval mirror; "
            "porcelain figurines or a delicately scrolled chandelier; a marble-topped console "
            "on cabriole legs; pastel silk drapery.",
            "- Avoid: straight rigid lines, minimalism, dark heavy wood, industrial materials, "
            "bold saturated colour.",
        ]),
        decor_scale="small",
    ),
    "deconstructivism": Style(
        name="Deconstructivism",
        summary="fragmented, angular and deliberately unresolved, in stark directional light.",
        guide="\n".join([
            "- Palette: concrete grey, black and white with sharp unexpected colour "
            "fragments.",
            "- Materials: raw steel, angled glass, exposed concrete, unfinished plywood.",
            "- Forms and pieces: furniture with fractured, non-parallel angles; a sculptural "
            "asymmetric shelving unit; a canted or off-axis mirror; bare structural elements "
            "left exposed as a feature; a single dramatically angular light fixture.",
            "- Avoid: symmetry, ornament, soft traditional upholstery, warm cosy textiles, "
            "anything predictable or matched.",
        ]),
        decor_scale="small",
    ),
    "wabi-sabi": Style(
        name="Wabi-Sabi",
        summary="imperfect, weathered and quietly beautiful, in soft natural light.",
        guide="\n".join([
            "- Palette: unbleached linen, clay, charcoal and stone tones; nothing bright or "
            "new-looking.",
            "- Materials: raw unfinished wood, hand-thrown crackle-glazed ceramic, unbleached "
            "linen, natural plaster, rough stone.",
            "- Forms and pieces: a low, irregularly-shaped wood stool; a single asymmetric "
            "ceramic vessel with visible imperfection; a rough plaster or lime-washed wall "
            "finish; a plain linen throw; one dried branch or seed-pod arrangement.",
            "- Avoid: glossy or symmetrical finishes, bright colour, matching sets, anything "
            "that looks factory-new, clutter.",
        ]),
        decor_scale="small",
    ),
    "organic-modern": Style(
        name="Organic Modern",
        summary="curved, natural-toned and softly sculptural, in warm daylight.",
        guide="\n".join([
            "- Palette: warm white, sand and clay with soft sage or terracotta accents.",
            "- Materials: light oiled wood, bouclé, natural linen, travertine, unglazed "
            "ceramic.",
            "- Forms and pieces: curved-arm seating in bouclé; an organic free-form coffee "
            "table; a sculptural ceramic floor vase; a plain jute or wool rug; softly rounded "
            "floor lamps.",
            "- Avoid: sharp geometric lines, high-gloss or chrome finishes, saturated colour, "
            "ornate period detail, clutter.",
        ]),
        decor_scale="small",
    ),
    "quiet-luxury": Style(
        name="Quiet Luxury",
        summary="understated, exquisitely made and logo-free, in soft warm light.",
        guide="\n".join([
            "- Palette: cream, taupe and camel with a single deep neutral accent (charcoal or "
            "ink).",
            "- Materials: cashmere-weight wool, brushed brass, honed natural stone, fine "
            "leather, unmarked quality wood veneer.",
            "- Forms and pieces: a low-profile seat in plain fine-weave fabric; understated "
            "brass hardware with no visible branding; a plain cashmere throw; one considered "
            "art piece rather than many; a single well-made occasional table.",
            "- Avoid: visible logos or branding, loud pattern, bright saturated colour, "
            "cheap-looking materials, visual clutter of any kind.",
        ]),
        decor_scale="small",
    ),
    "french-country": Style(
        name="French Country",
        summary="warm, rustic-elegant and sun-faded, in soft golden daylight.",
        guide="\n".join([
            "- Palette: soft ochre, lavender, cream and warm terracotta.",
            "- Materials: weathered oak, toile and provincial-print cotton, wrought iron, "
            "glazed terracotta, limestone.",
            "- Forms and pieces: a ladder-back chair with a woven rush seat; a distressed "
            "farmhouse-style hutch; a wrought-iron chandelier; lavender or toile-print "
            "textiles; a glazed terracotta pot.",
            "- Avoid: cold modern minimalism, chrome or glossy plastic, bright primary colour, "
            "stark geometric form.",
        ]),
        decor_scale="small",
    ),
    "english-country": Style(
        name="English Country",
        summary="layered, chintz-warm and lived-in, in soft filtered daylight.",
        guide="\n".join([
            "- Palette: forest green, faded rose and warm cream with floral chintz tones.",
            "- Materials: worn leather, chintz and floral cotton, aged brass, dark wood, "
            "needlepoint textiles.",
            "- Forms and pieces: a deep roll-arm seat in floral chintz; a Chesterfield-style "
            "leather chair; a skirted table with a fringed lamp; layered patterned cushions; a "
            "gallery of framed botanical prints.",
            "- Avoid: sleek modern minimalism, chrome or glossy surfaces, monochrome schemes, "
            "empty uncluttered walls.",
        ]),
        decor_scale="small",
    ),
    "neoclassical": Style(
        name="Neoclassical",
        summary="symmetrical, columned and restrained, in even formal light.",
        guide="\n".join([
            "- Palette: ivory, soft grey and gold with a single deep accent (navy or hunter "
            "green).",
            "- Materials: marble, gilt-edged wood, silk damask, bronze, plaster relief detail.",
            "- Forms and pieces: a klismos-style chair with tapered legs; a marble-topped "
            "console on fluted legs; a symmetrical pair of urn-form lamps; a gilt-framed "
            "classical-style mirror; restrained plaster relief detailing.",
            "- Avoid: ornate Baroque excess, industrial materials, asymmetry, bright saturated "
            "colour, rustic or distressed finishes.",
        ]),
        decor_scale="small",
    ),
    "alpine-chalet": Style(
        name="Alpine Chalet",
        summary="timber-lined and snug, warmed by firelight, in soft mountain light.",
        guide="\n".join([
            "- Palette: warm honey wood tones, cream and forest green with black metal "
            "accents.",
            "- Materials: knotty pine and spruce panelling, sheepskin, wrought iron, chunky "
            "wool knit, stone.",
            "- Forms and pieces: a stone fireplace surround; a chunky wood table with turned "
            "legs; a sheepskin-draped seat; a wrought-iron antler-style chandelier; a thick "
            "wool or fair-isle-pattern textile.",
            "- Avoid: glossy modern finishes, cool grey palettes, minimalism, tropical or "
            "beach motifs, bare unwarmed surfaces.",
        ]),
        decor_scale="small",
    ),
    "hacienda": Style(
        name="Hacienda",
        summary="sun-warmed, earthen and hand-crafted, in strong warm daylight.",
        guide="\n".join([
            "- Palette: terracotta, warm white plaster, deep blue and mustard.",
            "- Materials: hand-glazed talavera tile, dark carved wood, wrought iron, rough "
            "plaster, leather.",
            "- Forms and pieces: a heavy carved wood table; wrought-iron light fixtures; "
            "talavera-tile accents on a surface or niche; a leather-and-wood equipale-style "
            "seat; terracotta pots.",
            "- Avoid: cool minimalism, glossy modern surfaces, pale Scandinavian wood, muted "
            "grey palettes.",
        ]),
        decor_scale="small",
    ),
    "chinoiserie": Style(
        name="Chinoiserie",
        summary="ornate, lacquered and East-Asian-inspired, in soft warm light.",
        guide="\n".join([
            "- Palette: black and red lacquer with jade green, gold and porcelain "
            "blue-and-white.",
            "- Materials: black lacquered wood, hand-painted silk-panel-look wallcoverings, "
            "porcelain, brass, bamboo-motif detailing.",
            "- Forms and pieces: a black lacquered cabinet with painted motifs; blue-and-white "
            "porcelain vases; a bamboo-fretwork screen or mirror frame; a pagoda-style light "
            "fixture; hand-painted botanical or bird motifs on a feature surface.",
            "- Avoid: minimalism, industrial materials, Scandinavian pale wood, plain "
            "unornamented surfaces.",
        ]),
        decor_scale="small",
    ),
    "shabby-chic": Style(
        name="Shabby Chic",
        summary="soft, distressed-white and romantic, in gentle daylight.",
        guide="\n".join([
            "- Palette: white, soft pink and pale sage, all slightly faded.",
            "- Materials: distressed painted wood, chippy white finishes, lace and linen, "
            "worn brass.",
            "- Forms and pieces: a distressed white-painted dresser; slipcovered seating in "
            "faded floral or plain linen; a chandelier with a few crystals and a worn finish; "
            "lace-edged cushions; a chippy-paint mirror frame.",
            "- Avoid: sleek modern minimalism, dark heavy wood, glossy chrome, saturated bold "
            "colour.",
        ]),
        decor_scale="small",
    ),
    "gothic": Style(
        name="Gothic",
        summary="dark, dramatic and cathedral-inspired, in a low candlelit glow.",
        guide="\n".join([
            "- Palette: black, deep burgundy and charcoal with dark wrought-iron metal.",
            "- Materials: dark stained oak, wrought iron, velvet, stained or leaded glass, "
            "aged leather.",
            "- Forms and pieces: a high-backed carved wood chair; a wrought-iron "
            "candelabra-style light fixture; a pointed-arch mirror or panel motif; heavy dark "
            "velvet drapery; small trefoil-motif accents.",
            "- Avoid: bright or pastel colour, minimalism, pale wood, cheerful daylight "
            "staging, plastic or laminate finishes.",
        ]),
        decor_scale="small",
    ),
    "steampunk": Style(
        name="Steampunk",
        summary="brass-fitted and Victorian-industrial, lit by warm Edison-bulb glow.",
        guide="\n".join([
            "- Palette: aged brass, dark leather brown, oxblood and charcoal.",
            "- Materials: exposed brass gears and pipework, aged leather, dark iron, "
            "reclaimed wood, exposed filament bulbs.",
            "- Forms and pieces: a leather chesterfield-style seat with brass studs; a "
            "gear-motif clock or wall art; a pipe-fitting-style light fixture with exposed "
            "bulbs; a wood-and-brass campaign trunk; a factory-gauge or map-motif accent.",
            "- Avoid: bright clean minimalism, pastel colour, glossy plastic, Scandinavian "
            "pale wood, sleek modern lines.",
        ]),
        decor_scale="small",
    ),
}


def build_prompt(
    *,
    style: str,
    user_prompt: str | None,
    items: Iterable[InventoryItem],
    remove_ids: Iterable[str],
    room_label: str | None,
    room_type: str | None = None,
    walls: str = "leave",
    furniture: str = "keep_only",
    add_furniture: Iterable[str] = (),
    decor: str = "as_style",
    plants: bool = False,
    palette: str = "as_style",
) -> str:
    items = list(items)
    remove = set(remove_ids)
    add_furniture = list(add_furniture)
    where = _where(room_type, room_label)

    architecture = [i for i in items if i.kind == "architecture"]
    keep_objects = [i for i in items if i.kind != "architecture" and i.id not in remove]
    remove_objects = [i for i in items if i.kind != "architecture" and i.id in remove]

    known = STYLES.get(style)
    if known is not None:
        header = f"THE STYLE THE CUSTOMER CHOSE — {known.name}: {known.summary}"
    else:
        phrase = style.replace("-", " ").replace("_", " ").strip() or "restyled"
        header = f"THE STYLE THE CUSTOMER CHOSE — {phrase}."

    lines = [_PREAMBLE, "", header]
    if known is not None:
        lines.append(known.guide)
    if palette != "as_style":
        lines.append(_palette_line(palette, walls))
    if not keep_objects:
        lines.append(_EMPTY_ROOM)
    if user_prompt and user_prompt.strip():
        lines.append(f"The customer also asked for: {user_prompt.strip()}")

    lines += ["", _HEADER_INVENTORY.format(where=where), "", _HEADER_KEEP_ARCH]
    lines += _bullets(architecture)
    lines.append("")

    if keep_objects:
        lines.append(_HEADER_KEEP_OBJ)
        lines += _bullets(keep_objects)
        lines.append(_REFINISH)

    if remove_objects:
        lines.append("")
        lines.append(_HEADER_GONE)
        lines += [f"- {i.name} — gone; the space it occupied is empty" for i in remove_objects]

    add_active = furniture == "add" and bool(add_furniture)
    if add_active:
        lines.append("")
        lines += _add_furniture_block(add_furniture, room_type)

    lines += [
        "",
        _rules_block(
            walls=walls,
            decor_phrase=_decor_phrase(decor, known),
            add_active=add_active,
            plants=plants,
        ),
    ]
    return "\n".join(lines)


def _bullets(items: list[InventoryItem]) -> list[str]:
    return [f"- {i.description}" for i in items]
