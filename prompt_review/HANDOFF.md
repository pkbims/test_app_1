# Handoff — prompt rewrite and the 6 → 18 style expansion

Written 2026-09-10 by the prompt-engineering session. Implementation brief for the
**backend agent** (owns `backend/`, works in its own worktree) and, for §2 only, the
**iOS agent**.

Nothing in this document has been implemented. `backend/app/render/prompt.py` is
untouched on every branch. Build from this doc; do not copy code out of
`prompt_review/`, which contains only throwaway test scripts.

**Evidence behind every claim here:** five real `gpt-image-2` renders of room
`edae7f0b-d22e-4657-b683-7a647e884122`, A/B'd across two styles, scored with the
product's own `preservation_check`. Result images are in `prompt_review/`.

---

## 1. What changes, in one paragraph

Today the style reaches the model as one bare adjective — `style.replace("-", " ")`
dropped into `Restyle this room in a {style} style.` — with no vocabulary behind it,
and the prompt never tells the model what job it is doing. This replaces that with a
role preamble, a per-style guide table of 18 entries, a labelled rules block, and a
redesigned removal section. Measured effect on the two styles tested: preservation
0.67 → 1.00 on `scandi`, and on `cyberpunk` the bare word changed **lighting only**
while the guide changed **materials** (oak and rattan → black lacquer and dark mesh).

---

## 2. The 18 styles

`decor_scale` controls the size of object a style may introduce. Two values:

| Value | Renders as | Used by |
|---|---|---|
| `small` | `add small decor` | all 16 non-seasonal styles |
| `large` | `add decorations of any size, including large freestanding ones` | `christmas`, `valentines` |

Seasonal styles are **additive**: they decorate the room rather than refinishing it.
That restraint is written into their own `Avoid:` line — do not special-case it in code.

**iOS agent:** the id list in `ios/AGENT.md:86` grows from 6 to these 18. Ids are the
wire format; display names are for the picker. Twelve new style-card sample images are
needed (PRD U4 — stock images, produced once, not rendered per user).

| Id | Display name | Zone | `decor_scale` |
|---|---|---|---|
| `warm-minimal` | Warm minimal | Light neutral | `small` |
| `scandi` | Scandi | Light neutral | `small` |
| `japandi` | Japandi | Light neutral | `small` |
| `modern-coastal` | Modern coastal | Light neutral | `small` |
| `mid-century` | Mid-century | Warm retro wood | `small` |
| `industrial` | Industrial | Dark raw | `small` |
| `traditional` | Traditional | Conventional | `small` |
| `art-deco` | Art Deco | Glamour, metallic | `small` |
| `dark-academia` | Dark Academia | Dark traditional | `small` |
| `maximalism` | Maximalism | Dense pattern | `small` |
| `moroccan` | Moroccan | Global warm | `small` |
| `cottagecore` | Cottagecore | Floral light | `small` |
| `rustic-farmhouse` | Rustic Farmhouse | Rustic wood | `small` |
| `mediterranean` | Mediterranean | Warm plaster | `small` |
| `cyberpunk` | Cyberpunk | Neon dark | `small` |
| `memphis` | Memphis | Playful primary | `small` |
| `christmas` | Christmas | Seasonal, additive | `large` |
| `valentines` | Valentine's Day | Seasonal, additive | `large` |

### 2.1 The guides

Each guide is the four lines below, verbatim, following a header line of the form:

```
THE STYLE THE CUSTOMER CHOSE — {display name}: {one-line summary}
```

Every guide is **attribute-shaped**, never scene-shaped. No guide names a sofa, chair
or table as a thing to place, because those are the items `KEEP` is holding — naming
them invites substitution. Keep that rule when editing.

---

**`warm-minimal` — Warm minimal: soft, tonal and quiet, in diffuse daylight.**
```
- Palette: oat, greige, sand and off-white in one tonal family; no black, no strong
  contrast; at most a soft clay accent.
- Materials: lime plaster, boucle, undyed cotton and linen, travertine, pale unpolished
  stone, matte ceramic.
- Forms and pieces: soft rounded upholstery with low arms; plinth and slab forms in
  stone; one large floor vase; sheer full-height curtains; a single dried branch; a
  deep-pile plain rug.
- Avoid: pattern of any kind, visible hardware, black metal, cool greys, gloss, busy
  surfaces, and anything that reads as a knick-knack.
```

**`scandi` — Scandi: bright, warm and uncluttered, in soft natural daylight.**
```
- Palette: white and chalky off-white walls; pale oak, ash and birch wood; light grey
  and greige textiles; matte black metal, sparingly; at most one muted accent colour
  (sage, dusty blue, clay).
- Materials: untreated or lightly whitewashed wood, wool, linen, boucle, rattan, jute,
  matte ceramic, sheepskin.
- Forms and pieces: slim tapered wood legs, low profiles, simple rounded sculptural
  shapes; a woven jute or flatweave wool rug; a paper or opal-glass globe pendant;
  linen curtains hung high; a sheepskin or chunky knit throw; one or two potted plants
  in plain ceramic; a few well-spaced ceramic or glass objects.
- Avoid: ornate carving, gilding, brass flourishes, heavy dark or red-toned wood,
  glossy black, busy patterns, velvet, and clutter. Leave most surfaces empty.
```

**`japandi` — Japandi: low, muted and handmade, in soft shadow.**
```
- Palette: warm off-white, muted clay, greige and soft charcoal; walnut and pale ash
  together; nothing bright, nothing pure white.
- Materials: matte-oiled wood, paper, tatami and rush, raw-edged linen, unglazed and
  crackle-glazed ceramic, bamboo, dark iron.
- Forms and pieces: furniture low and close to the floor; slatted screens; paper
  lanterns; a single stem in a rough vessel; floor cushions; a low platform bench; one
  deliberately imperfect handmade object.
- Avoid: bright white, chrome, gloss, tall or bulky forms, matching sets, pattern,
  sheepskin, and anything that looks new and mass-produced.
```

**`modern-coastal` — Modern coastal: airy and sun-bleached, in bright daylight.**
```
- Palette: chalk white and bleached driftwood, with sea blue, soft aqua and pale sand;
  daylight, never lamplight.
- Materials: rattan and cane, washed linen slipcovers, rope, limed and weathered wood,
  seagrass, unglazed white ceramic.
- Forms and pieces: loose slipcovered seating; cane-backed frames; a seagrass or
  flatweave rug; sheer white curtains; large woven baskets; a few shell or coral
  objects; generous open floor.
- Avoid: dark wood, heavy drapery, gold, gloss, saturated colour, and literal nautical
  motifs — no anchors, no rope as decoration, no stripes on everything.
```

**`mid-century` — Mid-century: warm walnut and confident colour, in even daylight.**
```
- Palette: walnut and teak browns with mustard, burnt orange, olive and teal; warm
  white walls.
- Materials: oiled walnut and teak, tweed and wool upholstery, brass, smoked glass,
  moulded plywood, earth-glazed ceramic.
- Forms and pieces: splayed tapered legs; low horizontal casework; welted or lightly
  tufted upholstery; a starburst or sputnik light; a geometric-pattern rug; an arced
  floor lamp; a bar cart; a large-leaved potted plant.
- Avoid: distressed or reclaimed finishes, chrome-heavy modernism, farmhouse and
  country motifs, pastels, ornate carving, and crowded surfaces.
```

**`industrial` — Industrial: raw, heavy and utilitarian, in hard directional light.**
```
- Palette: concrete grey, black, oxidised steel and warm tan leather; brick red only
  where brick already exists.
- Materials: blackened and galvanised steel, aged tan leather, reclaimed timber,
  concrete, wire mesh, clear bulb glass.
- Forms and pieces: heavy square-section metal frames; leather club seating;
  factory-style pendants on long flex; visible bolts and castors; a metal locker or
  trolley; a worn kilim; one large monochrome print.
- Avoid: pastels, chintz, gloss paint, delicate legs, fitted upholstery, gold, and
  anything precious or fragile-looking.
```

**`traditional` — Traditional: symmetrical, warm and settled, in soft lamplight.**
```
- Palette: warm neutrals with navy, deep red, forest green and soft gold; cream walls
  with white trim.
- Materials: cherry and mahogany-toned wood, damask and plain cotton upholstery, wool
  rugs, polished brass, silk lampshades.
- Forms and pieces: symmetrical arrangements; rolled arms; turned or cabriole legs; a
  skirted ottoman; framed landscape and botanical prints hung in pairs; table lamps
  flanking the seating; a bordered patterned rug.
- Avoid: industrial metal, exposed hardware, neon or fluorescent colour, minimalism,
  asymmetry, and anything that reads as ultra-modern.
```

**`art-deco` — Art Deco: geometric, lacquered and glamorous, in warm pooled light.**
```
- Palette: black and cream with emerald, sapphire and oxblood; polished brass and gold
  throughout.
- Materials: lacquered ebony, brass and gold metal, velvet, strongly veined marble,
  mirrored and fluted glass, shagreen.
- Forms and pieces: fan, sunburst and chevron motifs; fluted and scalloped fronts;
  curved velvet upholstery; a mirrored or marble-topped bar; a geometric inlaid rug; a
  stepped or tiered light fitting; an oversized round mirror in a brass frame.
- Avoid: rustic or distressed wood, pastels, casual slipcovers, farmhouse and coastal
  motifs, matte or unfinished surfaces, and visible clutter.
```

**`dark-academia` — Dark Academia: bookish, shadowed and worn-in, in low warm lamplight.**
```
- Palette: deep forest green, oxblood, ink and chocolate against smoke-stained cream;
  warm low lamplight only, never daylight.
- Materials: dark stained oak and mahogany, worn tan and burgundy leather, heavy wool,
  brass, aged paper, dark marble.
- Forms and pieces: shelves packed to the ceiling with books; a leather chesterfield or
  wingback; a writing desk with a green glass lamp; framed prints and maps hung
  densely; a globe; a worn Persian rug; heavy curtains half-drawn.
- Avoid: bright or cool light, white walls, pale wood, minimalism, plastic, chrome, and
  anything new-looking or brightly coloured.
```

**`maximalism` — Maximalism: layered, saturated and unapologetic, in warm even light.**
```
- Palette: several saturated colours at once — emerald, fuchsia, ochre, cobalt —
  layered rather than balanced, with no neutral resting point.
- Materials: velvet, printed cotton, patterned wallpaper, lacquer, brass, ceramic, and
  mixed woods that deliberately do not match.
- Forms and pieces: a gallery wall hung frame-to-frame; layered rugs; pattern over
  pattern; boldly upholstered seating with many clashing cushions; shelves crowded with
  books and objects; a statement chandelier; plants at several heights.
- Avoid: empty walls, bare surfaces, a single neutral palette, matching furniture sets,
  and restraint of any kind.
```

**`moroccan` — Moroccan: warm, patterned and lantern-lit, in low golden light.**
```
- Palette: terracotta, saffron, deep teal and rose against warm lime-washed off-white;
  brass warmth throughout.
- Materials: hand-glazed tile, pierced brass, wool kilim and Beni rugs, leather
  pouffes, carved wood, hand-block-printed cotton.
- Forms and pieces: low seating banked with cushions along the wall; pierced brass
  lanterns throwing patterned light; layered flatweave rugs; a carved side table; a
  large brass tray table; a potted palm.
- Avoid: minimalism, cool greys, chrome, matching sets, tall Western sofas. Do not add
  arches, niches or carved plasterwork — this is a room, not a riad.
```

**`cottagecore` — Cottagecore: soft, floral and sun-faded, in gentle daylight.**
```
- Palette: soft cream, sage, butter yellow and faded rose; sun-bleached rather than
  saturated.
- Materials: floral and printed cotton, gingham, crochet and lace, painted wood,
  enamelware, wicker, stoneware.
- Forms and pieces: slipcovered or floral upholstery; mismatched painted chairs; open
  shelves of mismatched crockery; dried flowers and fresh cuttings in jugs; a patchwork
  quilt; gathered curtains; a wicker basket of blankets.
- Avoid: black, chrome, gloss, hard geometry, sleek modern forms, industrial materials,
  and anything that reads corporate or new.
```

**`rustic-farmhouse` — Rustic Farmhouse: weathered, practical and warm, in daylight.**
```
- Palette: warm white and putty with weathered grey-brown wood; black metal accents;
  a muted denim blue or sage.
- Materials: reclaimed and knotty wood, board panelling, galvanised metal, jute,
  ticking stripe and grain-sack linen, stoneware.
- Forms and pieces: chunky plank tables and benches; slipcovered seating; a black metal
  cage or lantern pendant; open wooden shelving; enamel jugs; a woven basket by the
  hearth; a simple striped rug.
- Avoid: gold, gloss, velvet, ornate carving, saturated colour, chrome, sleek
  minimalism, and anything delicate.
```

**`mediterranean` — Mediterranean: sun-washed, earthen and calm, in strong daylight.**
```
- Palette: lime-washed white and warm sand with olive green, terracotta and a single
  deep blue; strong sunlight.
- Materials: rough lime plaster, terracotta tile, olive and pine wood, raw linen, woven
  rush, hand-thrown glazed ceramic.
- Forms and pieces: chunky plaster-toned upholstery; rush-seated frames; terracotta
  pots holding olive or citrus; hand-painted ceramic bowls; a rough wooden bench;
  simple linen curtains; a jute rug.
- Avoid: gloss, chrome, dark wood, heavy drapery, pastels, fitted carpet. Do not add
  arches, niches or ceiling beams.
```

**`cyberpunk` — Cyberpunk: a dark room lit entirely by artificial coloured light, after dark.**
```
- Palette: near-black and deep charcoal surfaces; saturated magenta, cyan and electric
  violet light; one acid green or amber accent. No daylight, no warm white.
- Materials: black lacquer, brushed gunmetal, smoked glass, matte black plastic, vinyl,
  bare concrete, wire mesh.
- Forms and pieces: low slab seating in dark upholstery; LED strips along edges,
  skirtings and under furniture; neon signage glow on one wall; visible cable runs; a
  lit screen; a glossy floor reflecting the coloured light; a single plant uplit from
  below.
- Avoid: daylight, warm wood tones, beige, brass, florals, natural linen or wool, cosy
  textures, clutter. Do not turn the room into a spaceship, a city skyline or a film
  set — it is an ordinary room, lit and finished differently.
```

**`memphis` — Memphis: flat, primary and deliberately absurd, in bright even light.**
```
- Palette: primary red, yellow and blue with hot pink, mint, and black-and-white
  squiggle, on a white ground; flat colour with little shading.
- Materials: laminate, terrazzo, matte plastic, powder-coated metal, coloured glass,
  patterned melamine.
- Forms and pieces: forms built from stacked geometric solids — circles, triangles,
  zigzags; squiggle and confetti pattern; asymmetric mirrors; a terrazzo top; tubular
  metal frames; lamps in clashing shapes.
- Avoid: wood tones, neutrals, symmetry, natural texture, subtlety, and anything
  tasteful or muted.
```

**`christmas` — Christmas: the room dressed for Christmas, in warm firelight and fairy-light glow.**
```
- Palette: deep green and red with warm gold and white; low warm light from the fire,
  candles and string lights.
- Materials: fir and pine foliage, red velvet ribbon, knitted wool, brass and gold
  baubles, kraft paper, candlelight.
- Forms and pieces: a decorated fir tree with lights and wrapped gifts beneath it;
  garland along the mantel and shelves; stockings hung; a wreath; warm string lights;
  a knitted throw; grouped candles.
- Avoid: cool or blue-white light, plastic novelty and inflatables, clashing neon, and
  decoration so dense the room is hidden. Leave the room's wall colour, flooring and
  furniture finishes as they are — this style decorates the room, it does not restyle it.
```

**`valentines` — Valentine's Day: the room dressed for Valentine's Day, in soft warm light.**
```
- Palette: blush and dusty rose with deep red and white; soft warm light, candles
  rather than overhead lighting.
- Materials: rose petals, satin and velvet ribbon, tulle, foil balloons, fresh roses,
  candle wax.
- Forms and pieces: heart balloons clustered at the ceiling; rose petals scattered on
  floor and surfaces; vases of red and pink roses; candles grouped on the mantel and
  tables; a garland of paper hearts; a soft pink throw and cushions.
- Avoid: cold light, garish plastic, and decoration so dense the room is hidden. Leave
  the room's wall colour, flooring and furniture finishes as they are — this style
  decorates the room, it does not restyle it.
```

---

## 3. The new `prompt.py`

`build_prompt()`'s signature does not change. `room_label` is still used (§3.4).
`_HEADER_KEEP` keeps its exact current wording — it is proven and `KEEP` works.

### 3.1 Constants

```python
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
_HEADER_KEEP_OBJ  = "KEEP these items, in the same positions (you may restyle their finish):"
_HEADER_GONE      = "NOT IN THE ROOM — the customer has thrown these away:"

_REFINISH = """Restyle the kept items by changing only their material, colour and finish.
Their shape, size, silhouette and position stay exactly as they are."""

_EMPTY_ROOM = """The customer has removed everything that was in this room: furnish it fully
in this style, at a realistic scale for the room, leaving open floor space."""

_RULES = """HOW TO DO THE WORK
- You may change wall colour, textiles, rugs, and {decor}.
- Anything listed as not in the room is gone. Do not draw it, and do not put a
  similar object in its place.
- Do not move the camera, change the framing, or change the angle of view.
- Do not add or remove any wall, opening or ceiling feature.
- Do not change the size, shape or proportions of the room.
- Where the style and the room disagree, the room wins.
- If you are unsure whether something is part of the building, leave it exactly
  as it is."""
```

### 3.2 The style table

```python
@dataclass(frozen=True)
class Style:
    name: str          # display name, e.g. "Scandi"
    summary: str       # the clause after the colon in the header line
    guide: str         # the four "- ..." lines, verbatim, newline-joined
    decor_scale: str   # "small" | "large"

STYLES: dict[str, Style] = { ... 18 entries from §2 ... }

_DECOR = {
    "small": "add small decor",
    "large": "add decorations of any size, including large freestanding ones",
}
```

**Unknown style id** — must not raise (`style` is an unvalidated string, see §6).
Fall back to today's behaviour: emit
`THE STYLE THE CUSTOMER CHOSE — {style.replace("-", " ")}.` with no guide lines, and
`decor_scale = "small"`. A typo degrades to current quality rather than 500ing.

### 3.3 Assembly order

```
_PREAMBLE
<blank>
THE STYLE THE CUSTOMER CHOSE — {name}: {summary}
{guide}                                    ← the four lines
[_EMPTY_ROOM]                              ← only when keep_objects is empty
[The customer also asked for: {user_prompt}]   ← only when user_prompt is non-blank
<blank>
_HEADER_INVENTORY
<blank>
_HEADER_KEEP_ARCH
- {architecture descriptions, verbatim}
<blank>                                    ← the next two blocks are conditional
_HEADER_KEEP_OBJ
- {kept object descriptions, verbatim}
_REFINISH                                  ← only when keep_objects is non-empty
<blank>
_HEADER_GONE
- {removed object NAMES — see §4}
<blank>
_RULES
```

Style near the top, preservation blocks last before the rules: the final things the
model reads are what to protect and what not to touch. This ordering was chosen
deliberately over placing the style last.

### 3.4 `room_label`

Used only in `_HEADER_INVENTORY` as `This is a {where}.`, with the existing
lower-cased fallback to `"room"`. It is deliberately **not** in the preamble — "the
room in this photograph" is stronger than naming it, because the model can see it.

---

## 4. The `REMOVE` bug — required fix, with a test

**Status: reproduced in 4 of 4 renders, across 2 styles, on both the old and the new
prompt.** Items listed for removal came back — the TV, its stand and a laundry basket,
recognisably the same pieces. `KEEP` works correctly in the same renders. This is
*not* fixed by the round-2 rewrite; §3 above already contains the intended fix and it
is **unproven**.

### 4.1 Diagnosis — the mechanism

The inventory `description` field is doing two contradictory jobs.

The spike proved that naming an item in precise visual detail makes an image-edit model
*render it in place* — that is the entire preservation mechanism. The current prompt
then uses **the same mechanism, the same field and the same bullet format** to ask for
the opposite outcome. A line like

```
- Large flat-screen TV on light wood stand with rattan-front cabinets, centered along the main wall.
```

is, to a model conditioned on the photograph, a high-quality rendering specification for
an object that is visibly present. The negation carrying the opposite intent is a single
word in a header several lines above. Negation is weak in image-edit conditioning;
detailed visual description is strong. We are out-shouting our own instruction.

Two aggravating factors: the removal list currently sits **last**, so the final nouns
before generation are precisely the objects that should be absent; and the footer's
permissive `add small decor` sits directly beneath it.

### 4.2 The fix, and why it should work

Three changes, all in §3, all pulling the same direction:

1. **Use `name`, not `description`, for removed items.** `InventoryItem` already
   carries a short `name` ("large wall clock", "floor lamp"). Removing the rich
   positional detail removes the rendering specification. Identify the object; do not
   paint it.
2. **State the end state, not the operation.** `NOT IN THE ROOM — the customer has
   thrown these away:` describes a *fact about the room* rather than issuing a negated
   instruction. Pair each entry with the resulting emptiness, e.g.
   `- the television and its stand — that stretch of wall and floor is now empty`.
   Giving the model something positive to render is the standard remedy for weak
   negation; suppression alone is not a thing these models do well.
3. **Move removals ahead of the rules block, and add an explicit rule** — the second
   bullet of `_RULES` — so the instruction is restated after the list, not before it.

Suggested line template:

```python
f"- {i.name} — gone; the space it occupied is empty"
```

### 4.3 Acceptance criteria — both required

**This is a required, tested outcome, not a hoped-for side effect.** Do not close the
work on unit tests alone; a unit test cannot see a TV.

**(a) Unit tests**, mirroring the rigour `KEEP` already has in
`tests/test_render_prompt.py`:

- removed items appear **only** under `_HEADER_GONE`, never under `KEEP` or the
  architecture block;
- removed items are rendered from `name`, and their `description` string does **not**
  appear anywhere in the prompt;
- the `Anything listed as not in the room is gone` rule is present whenever the removal
  section is;
- the removal section is omitted entirely when `remove_ids` is empty;
- an architecture id passed in `remove_ids` still appears under `MUST REMAIN` (existing
  test, must keep passing).

**(b) A render-level acceptance test** — the one that actually proves it. Same shape as
`tests/test_vision_e2e.py` (real-OpenAI, opt-in, not in the default CI lane):

- render a room with a large, unambiguous object marked for removal;
- ask a vision call whether that object is present in the output;
- assert it is absent.

Use room `edae7f0b-d22e-4657-b683-7a647e884122` with the TV and stand removed — it has
failed this four times and is a known-bad case. **If (b) does not pass, the removal
redesign has not worked**; report that rather than shipping, and treat §4.2 as a first
hypothesis rather than the answer. Two further levers exist if it fails: dropping
removed items from the prompt entirely (say nothing, on the theory that any mention
renders), or naming only the surface left behind ("the mantel is bare") without naming
the object at all.

---

## 5. Open questions — deferred, not resolved

**5.1 Does a dark style break the preservation metric?**
`scandi` scored 1.00 and `cyberpunk` 0.67 on identical setups. The item cyberpunk
"lost" — a recessed alcove — is present in the render, but near-black on a near-black
wall. It was not deleted; it became unreadable. So preservation rate is
**style-dependent**, and a single headline number will drift with the style mix and
read as a regression when it is really a change in what users picked. PRD §9 says to
watch the 5th percentile — that will be all-dark-styles unless this is handled.
Open: is an unreadable alcove in a deliberately dark style a render failure or a
measurement gap? A photograph of the real room at night would do the same thing.
Likely resolution is segmenting the metric by style. Not a blocker for §2–§4.

**5.2 Do seasonal styles show year-round?**
`christmas` and `valentines` in July is odd. Hiding them needs availability logic and a
rule about what the picker shows out of season. Deliberately unresolved.

---

## 6. Deferred: `style` is not validated

`style` is a plain `"type": "string"` in `contract/openapi.json` and
`backend/app/schemas.py:101` — no enum, no server-side check. The backend accepts any
string and drops it into the prompt, so `scandy` renders silently at bare-word quality
instead of returning an error. The list exists only in the iOS client and
`ios/AGENT.md:86`.

An enum is the right fix and is **deliberately deferred for this pass**: it is a
contract change, and the frozen OpenAPI must regenerate byte-identically
(`python3 backend/export_openapi.py`, with the pinned FastAPI/Pydantic versions). That
is a more delicate job than it looks and is not needed to ship 18 styles. The
unknown-style fallback in §3.2 is what makes deferring safe.

Flagged so it is not lost: **this gets riskier as the list grows from 6 to 18.**
