"""Build the image-edit prompt (HANDOFF at `prompt_review/HANDOFF.md`).

Structure: a role preamble, a per-style guide (attribute-shaped — palette,
materials, forms, what to avoid — never scene-shaped, so it never names a sofa,
chair or table and invites substitution of an item `KEEP` is holding), the room's
inventory (architecture that must not move, kept objects that may be refinished,
removed objects), then the rules.

Removed items are rendered from `name`, never `description`. The spike proved that
naming an item in precise visual detail makes an image-edit model render it in
place — that is the entire `KEEP` mechanism. Using that same detailed-description
channel to ask for the opposite (removal) fights itself: negation is weak in
image-edit conditioning, detailed visual description is strong. `name` alone,
paired with a stated end state ("gone; the space it occupied is empty") gives the
model something positive to render instead of relying on suppression.
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

_RULES = """HOW TO DO THE WORK
- You may change wall colour, textiles, rugs, and {decor}.
- Anything listed as not in the room is gone. Do not draw it, and do not put a similar object in its place.
- Do not move the camera, change the framing, or change the angle of view.
- Do not add or remove any wall, opening or ceiling feature.
- Do not change the size, shape or proportions of the room.
- Where the style and the room disagree, the room wins.
- If you are unsure whether something is part of the building, leave it exactly as it is."""

_DECOR = {
    "small": "add small decor",
    "large": "add decorations of any size, including large freestanding ones",
}


@dataclass(frozen=True)
class Style:
    name: str  # display name, e.g. "Scandi"
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
        name="Scandi",
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
        name="Mid-century",
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
}


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

    architecture = [i for i in items if i.kind == "architecture"]
    keep_objects = [i for i in items if i.kind != "architecture" and i.id not in remove]
    remove_objects = [i for i in items if i.kind != "architecture" and i.id in remove]

    known = STYLES.get(style)
    if known is not None:
        header = f"THE STYLE THE CUSTOMER CHOSE — {known.name}: {known.summary}"
        decor = _DECOR[known.decor_scale]
    else:
        phrase = style.replace("-", " ").replace("_", " ").strip() or "restyled"
        header = f"THE STYLE THE CUSTOMER CHOSE — {phrase}."
        decor = _DECOR["small"]

    lines = [_PREAMBLE, "", header]
    if known is not None:
        lines.append(known.guide)
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

    lines += ["", _RULES.format(decor=decor)]
    return "\n".join(lines)


def _bullets(items: list[InventoryItem]) -> list[str]:
    return [f"- {i.description}" for i in items]
