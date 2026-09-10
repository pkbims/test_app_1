# DesignMyRoom — visual redesign handoff

Status: **approved**, 2 review rounds closed. Decisions final: `home-layout = grid`, `accent = clay`.
Live reference (keep running, don't tear down): `http://localhost:7777` — every screen below is built
there as a clickable mockup; this document is the spec to build against, the page is the picture.

This covers restyling only. No flow, endpoint, or state-machine logic changes — every screen below still
drives the same `RoomFlowViewModel` / `HomeViewModel` / `RoomDetailViewModel` it does today. Where a screen
needs new data (one case, flagged below), that's called out explicitly as a contract dependency, not a UI
decision.

---

## 1. Visual system

### Color

All hex values are exact — pull these into `Assets.xcassets` as named color sets (`Color("Paper")`,
`Color("Accent")`, etc.) rather than hardcoding literals, so a future palette swap stays a one-file change
per CLAUDE.md's "restyling must stay cheap" constraint.

| Token | Hex | Usage |
|---|---|---|
| `paper` | `#F7F3EA` | App background (replaces system `.background`) |
| `surface` | `#FFFFFF` | Card / sheet surfaces, phone status-bar-adjacent chrome |
| `surface2` | `#FBF8F1` | Recessed surfaces — locked inventory rows, image placeholders |
| `ink` | `#1C1912` | Primary text (replaces `.primary`) |
| `inkSoft` | `#5B5548` | Secondary text (replaces `.secondary` in body copy) |
| `faint` | `#948C7C` | Tertiary text — timestamps, captions, placeholder copy |
| `line` | `#E6DFD0` | Hairlines, dashed borders, card outlines |
| **`accent` (final)** | **`#B2582F`** | Primary buttons, selection rings, fidelity numeral, credits chip — **replaces the current `AccentColor.colorset` value `(R:0.086, G:0.310, B:0.404)` ≈ `#164F67`, a dark teal that was never a deliberate brand choice.** |
| `accentDeep` | `#8A4322` | Accent text-on-light (labels inside `accentSoft` chips) |
| `accentSoft` | `#F2DFCB` | Accent-tinted fills — selected chips, the "N left" credits pill |
| `accentInk` | `#FFF7EF` | Text/icon on filled-accent surfaces where pure white is too stark |
| `warn` | `#9C5A1E` | Low-confidence banner text/icon |
| `warnSoft` | `#F5E7D3` | Low-confidence banner background |

**Rejected alternative:** a `moss` / olive accent (`#5C6B45` / soft `#E2E6D4`) was built and compared
side-by-side in round 1. Clay was chosen because it reads as "designer," not "tech," and is closer to the
warm-light tones already in the six style-sample photos. Don't build the moss variant — it's in the
reference page only as a record of the comparison.

**Dark mode:** out of scope for this pass. The palette above is a deliberate single warm-light system, not
a themeable one; ship it as the only appearance for now (this is consistent with `Info.plist` not yet
declaring dark mode support — confirm before ship if that's still true).

### Type

Three roles, not the current one (system font everywhere):

| Role | Typeface | Used for |
|---|---|---|
| Display | **Fraunces** (weights 400/500/600, plus italic 400) | Screen titles, the fidelity numeral, the sign-in headline |
| UI / body | System (`-apple-system` / SF) | Everything functional — buttons, list rows, form fields, copy |
| Meta | System monospace (`ui-monospace` / SF Mono) | Small counted things: credits chip, inventory letters (A/B/C…), the low-key eyebrow labels |

**Build note:** Fraunces is a Google Font, not a system font — it must be bundled. Download the static
`.ttf`/`.otf` weights actually used (Regular 400, Medium 500, SemiBold 600, Italic 400), add them to the
Xcode target, and register them in `Info.plist` under `UIAppFonts`. Budget this as a real task, not a
detail — until it's done, screens will silently fall back to the system font and the type hierarchy below
won't read correctly. If sequencing is tight, `.system(size:, design: .serif)` (San Francisco's serif,
"New York") is an acceptable temporary stand-in that keeps the serif/sans contrast without a font-bundling
step — swap later.

Concrete instances used across the app:

| Instance | Font | Size | Weight | Notes |
|---|---|---|---|---|
| Sign-in headline | Fraunces | 34pt | Medium (500) | Line height ~1.06, two lines |
| Home title ("My Latest Decors") | Fraunces | 24pt | Medium (500) | |
| Confirm / Add-photo / Style-picker screen titles | Fraunces | 20–22pt | Medium (500) | |
| Fidelity numeral ("96%") | Fraunces | 30pt | SemiBold (600) | Color `accentDeep` |
| Style card name, room card label | System | 14–15.5px | Medium/SemiBold | |
| Body copy, subtitles | System | 13.5–15px | Regular | Color `inkSoft` |
| Eyebrow / mono labels | SF Mono | 10.5–11px | Semibold, uppercase, `+0.12em` tracking | Color `faint` or `accentDeep` on a chip |

### Spacing scale

Adopt one 8-ish-point scale everywhere instead of ad hoc padding: **6 · 8 · 10 · 12 · 16 · 24 · 32** pt.
Screen-edge padding is 20pt; card internal padding is 12–18pt depending on density.

### Corner radii

| Element | Radius |
|---|---|
| Primary button (pill) | 16pt |
| Chips / credits pill | capsule (999) |
| Grid room card | 16pt |
| Feed room card | 18pt |
| Style card artwork | 16pt |
| Before/after image | 16pt |
| Inventory letter badge | 7pt |
| "New room" dashed inline card | 18pt |

### Elevation / shadow

Two tiers cover everything in-app (a third, larger shadow exists on the reference page but only dresses
the *device bezel mockup* — not a real in-app element, ignore it):

- **Card** — `color: .black.opacity(0.08), radius: 6, x: 0, y: 2` — room cards, style cards, before/after images.
- **Raised** — `color: .black.opacity(0.12), radius: 14, x: 0, y: 6` — reserved for anything that should
  read as floating above the list (not currently needed by any screen below, but keep it in the token set).
- **Primary CTA button** gets its own accent-tinted shadow, not the neutral one:
  `color: Color(hex: "B2582F").opacity(0.28), radius: 8, x: 0, y: 6`.

### Photography treatment

No hard borders on photos, ever — corner radius + shadow only. Text-over-photo always sits on a gradient
scrim (`linear-gradient` from ~90% black at the text edge to transparent), never a flat tint, so the photo
stays legible through it. This rule applies everywhere a room/style photo carries a label: grid cards, the
sign-in mosaic, the style-picker check-badge corner.

---

## 2. Per-screen changes

### Sign in — `Sources/Auth/SignInView.swift`

**Today:** centered column — wordmark, one-line subtitle, black `SignInWithAppleButton`, all on plain
background. `#if DEBUG` block below adds a dev-only identifier field + button (kept, stripped from Release
per `ios/AGENT.md` / ORCH-QUESTIONS Q7).

**Redesign (round-2 rework, after "make this more interesting" feedback on round 1's single-photo-strip
version):**
- Full-bleed **three-photo mosaic** fills the entire screen: one large image left (full height), two
  stacked smaller images right. Use three of the six bundled style samples — pick ones that read well
  together (japandi + warm-minimal + industrial was used in the mockup for contrast/variety; any three is
  fine, they're already bundled assets, no network dependency).
- A single gradient scrim sits over the whole mosaic: ~94% black at the bottom fading to ~8% in the middle,
  back up to ~18% at the very top (keeps the status bar legible without darkening the photo mid-screen).
- All text and the CTA sit **inside** the dark zone at the bottom, over the photo — not below it on plain
  background:
  - Eyebrow: `DESIGNMYROOM`, SF Mono 10.5pt, white 72% opacity, `+0.14em` tracking.
  - Headline: **"It's still your room."** — Fraunces 34pt Medium, white, two lines. (This line is new copy,
    borrowed from the earlier `ui_ux/` design pass — it states the positioning directly; keep the existing
    subtitle below it rather than replacing it.)
  - Subtitle: unchanged copy — "Restyles your room. Never invents a different one." — white 82% opacity,
    14pt, max-width constrained so it wraps to two short lines instead of running edge-to-edge.
  - CTA: `SignInWithAppleButton` in **`.white`** style (not `.black` as today) — the dark photo behind it
    means the white button reads clearly; black would disappear into the scrim.
  - Trust line: `ONE FREE ROOM · NO PASSWORD, EVER`, SF Mono 10pt, white 60% opacity, centered. This is a
    new micro-copy addition (not in the current screen) — cheap trust reinforcement right at the moment R4
    is riskiest (nobody's seen the product work yet). Flag to product/copy owner if it should be cut.
- Error copy (`signInFailed` state) needs a home on this new dark layout — put it directly above the
  button, same white-on-dark treatment, not the current plain red text (red-on-dark-photo is low contrast).

**Implementation snag to resolve, not a design question:** the `#if DEBUG` dev-sign-in block (text field +
button) has nowhere to go in a full-bleed photo layout — there's no plain-background zone left for a text
input. Recommend: keep it compiled out of Release as today, and in DEBUG builds render it as a small
translucent panel pinned below the "Sign in with Apple" button (still inside the dark zone, same white-ish
treatment) rather than trying to preserve its current plain-list look. This only affects local/dev builds,
never what ships.

### Home — `Sources/Home/HomeView.swift`, `HomeViewModel.swift`, `RootView.swift` (`HomeContainerView`)

**Today:** `List` of text-only rows (`RoomRow`: label + date, no image), plain "New Room" bordered button
pinned via `.safeAreaInset`, credits shown as a footnote `Text` above the list, "Sign out" as a toolbar
item.

**Redesign — Gallery grid (the finalized direction; do not build the editorial-feed alternative, it was a
comparison-only option and `home-layout` was decided as `grid`):**

See §3 below for full build detail. Summary of what changes and why:
- `RoomRow` is replaced by an image-first `RoomCard` — this is the actual point of the whole pass, this
  product's photography needs to be on the one screen people open every session.
- Header becomes an in-list row (not `.navigationTitle`, kept as plain content like the credits line is
  today) — title **"My Latest Decors"** (copy change from "My Rooms") left, credits pill + "Sign out" right.
- Bottom CTA keeps the same `.safeAreaInset(edge: .bottom)` pinning as today — same pattern, restyled: a
  full-width accent pill, copy changed to **"Decorate a New Room"**.
- Empty state copy updates to match: *"No rooms yet. Tap "Decorate a New Room" to restyle your first one —
  it's free."*

**Contract dependency — now unblocked.** `Room.thumbnail_url` has been added to the contract and the
backend is implementing its resolution. On the client: add `thumbnailURL: String?` to
`DesignMyRoomCore/Sources/DesignMyRoomCore/Models/Room.swift`, regenerate/hand-sync the OpenAPI-derived
model per the pinned FastAPI/Pydantic contract process, and have `RoomCard` render it via `AsyncImage` with
`surface2` as the loading/failure placeholder color (never a broken-image glyph). Until the backend
actually returns a populated URL, render the placeholder color — don't block the rest of the redesign on
that landing first.

### Add a photo — `Sources/AddPhoto/AddPhotoView.swift`

**Today:** small camera SF Symbol + headline + subtitle + separate "Add a photo" button below.

**Redesign:** same copy verbatim ("Add a photo of your room" / "One photo is all we need. Frame the whole
room — anything we can't see, we can't protect."). The icon-plus-button pairing becomes one large
square drop-zone card (dashed `line`-colored border, `surface2` fill, rounded 22pt) that *is* the tap
target — camera icon in an `accentSoft` circle, centered, with "Tap to take or choose a photo" beneath it.
Primary button below stays, same copy, same `.confirmationDialog` / picker wiring — only the empty-state
visual changes, not the picker flow.

### What's in this room (Confirm) — `Sources/Confirm/ConfirmView.swift`

**Today:** photo, title, two flat sections (`SectionHeader` + `InventoryRow`), architecture rows show a
lock glyph, object rows show a bordered Remove/Removed button.

**Redesign:** same information architecture — still a labelled list over a static photo, *not* drawn
outlines (the frozen `InventoryItem` has no coordinates, that constraint hasn't changed). What changes:
- Architecture rows get a **recessed surface** (`surface2` background, ~85% opacity content) in addition
  to the lock glyph, so "this is locked" reads as a visual state, not just an icon someone might miss.
  Object rows stay on plain background so the two groups read apart at a glance.
- Inventory letter (`A`, `B`, `C`…) moves from plain monospace text into a small rounded badge
  (`letter` token: 24×24pt, 7pt radius, `surface2` fill, `line` border) — same information, more legible
  against a row.
- "Remove" / "Removed" becomes a small pill chip instead of a bordered destructive button — the
  `InventoryRow`'s `onToggle` logic and `removeIds` state are unchanged, only the button's `ButtonStyle`.

### Pick a style — `Sources/Style/StylePickerView.swift`

**Today:** horizontal rail of 130×130 square cards, checkmark overlay when selected.

**Redesign:** cards become **118×150 portrait**, not square — the six bundled style-sample photos are
real interiors and read much better tall than as thumbnails. Selection state changes from a thin ring
overlay to a filled accent circular check-badge in the top-right corner (22pt, white checkmark) — clearer
at a glance while scrolling. `StyleImageResolver`'s fallback-to-tinted-placeholder behavior for a style
with no bundled art is unchanged — it just needs to render at the new 118×150 size instead of square.
Prompt field and character-counter copy are unchanged.

### Rendering — `Sources/Rendering/RenderingView.swift`

**Today:** system `ProgressView` (spinner) + status text, both driven by `flow.renderState`.

**Redesign:** replace the system spinner with a custom **88×88 ring** — 5pt stroke, `accentSoft` track,
`accent` for the animated arc, continuous rotation. Same status copy, same state-driven text logic
(`RenderStateMachine` is untouched — this is a pure `ProgressView` → custom ring swap).

### Compare — `Sources/Compare/CompareView.swift` (shares `Sources/Shared/RenderSummaryView.swift`)

**Today:** stacked before/after images (`RenderSummaryView`, unchanged decision — U3, never a slider,
output isn't pixel-aligned with input), a plain `HStack` "Preservation — NN%" row, missing-items warning
text, edge states (`renderFailed` / `requestFailed` / `signedOut`) as centered icon+text+button.

**Redesign:**
- Before/after images get a small uppercase tag chip (`Before` / `After`) overlaid top-left instead of a
  separate label row above each image — saves vertical space, reads faster.
- The preservation percentage moves out of a plain `HStack` into a dedicated **fidelity card**:
  `surface2` background, `line` border, 16pt radius, the number rendered large in Fraunces SemiBold
  (`accentDeep`) next to a two-line description ("Preservation — how much of your room's structure survived
  the restyle."). This is deliberate: PRD §9 says fidelity is the headline metric, watched at the 5th
  percentile on the dashboard — it should look like the number the product is staking its promise on, not a
  footnote.
- Edge states keep the same three-way switch (`renderFailed` / `requestFailed(.signedOut/.api/.other)`) and
  same `ErrorCopy` messages — only the container changes: the low-confidence warning gets a `warnSoft`
  banner card with an icon, and the failed/try-again state gets a plain `surface` card with a ghost-style
  "Try again" button instead of a full-width filled one (it's a recovery action, not the primary flow).

### Room detail — `Sources/RoomDetail/RoomDetailView.swift`

**Today:** scrollable list of `RenderHistoryRow`s, each reusing `RenderSummaryView` for `.done` renders,
plain text for `.failed`/`.queued`/`.running`.

**Redesign:** inherits every token change from Compare above (same fidelity-card treatment, same image
corner radius/shadow) since it's the same shared `RenderSummaryView` — keeping this screen visually
consistent with Compare is the whole point of them sharing a component today, and that should stay true
after the restyle. No structural change beyond what flows through from `RenderSummaryView`. Screen title
stays the room's own label (`viewModel.room.label ?? "Room"`), rendered in the same Fraunces 20–22pt used
for other screen titles.

---

## 3. Home grid — build spec

This is the flagship screen; here's what's needed to build it exactly, not just describe it.

**Layout:** 2-column grid, 12pt gaps (both axes), 20pt screen-edge padding. Each `RoomCard`:

- **Aspect ratio 3:4** (portrait), 16pt corner radius, `surface2` background (shows while the thumbnail
  loads), `Card` shadow (see §1).
- Thumbnail image fills the card edge-to-edge, `.aspectRatio(contentMode: .fill)`, clipped to the card
  shape — no padding between photo and card edge.
- A bottom-anchored gradient scrim (`linear-gradient`, ~78% black at the bottom fading to transparent by
  ~68% up the card) sits over the lower third of the photo so the label stays legible regardless of what's
  in the thumbnail.
- Text sits inside the scrim, 12pt left/right inset, 10pt from the bottom edge:
  - Label: 14pt, SemiBold, white — e.g. `Living Room`.
  - Date: 11pt, white at 82% opacity, one line below the label — e.g. `Sep 8`. Use the existing
    `createdAt.formatted(date: .abbreviated, time: .shortened)` truncated to just the date portion for the
    card (the full date+time is still fine for Room Detail's history rows, which have more room).
- Tap target is the whole card → same `NavigationLink(value: room)` → `RoomDetailView` push that exists
  today, just wrapping the new card instead of `RoomRow`.

**Header row** (first thing in the scroll content, not a `List` section or toolbar item — same reasoning
as today's credits `Text`: arbitrary-length content shouldn't fight fixed-width toolbar chrome):

- Left: **"My Latest Decors"**, Fraunces 24pt Medium.
- Right: two elements, 10pt gap — a credits chip (`accentSoft` capsule, `accentDeep` text, SF Mono,
  e.g. `2 LEFT`) and "Sign out" as plain underlined text, 12.5pt, `faint` color (same action as today's
  toolbar button, just relocated into the header row for visual consistency with the title).

**Bottom CTA:** unchanged mechanism — `.safeAreaInset(edge: .bottom)`, full-width accent pill button,
16pt corner radius, white text, weight 650, copy **"Decorate a New Room"** (with a leading `+`). Same
`onNewRoom` closure wiring as today.

**Empty state** (no rooms yet): centered card, dashed `line` border, 18pt radius, `surface` background,
36pt vertical padding — a large emoji/glyph, "No rooms yet" (SemiBold), and the updated copy: *"Tap
"Decorate a New Room" to restyle your first one — it's free."* This replaces the current plain centered
`Text` in `HomeView.swift`.

---

## 4. Sign-in mosaic — build spec

(Full detail already folded into §2's Sign-in entry above — repeating the concrete numbers here since this
screen got the most rework.)

- **Mosaic grid:** CSS-equivalent is a 2-column layout, left column ~57% width spanning the full screen
  height (one image), right column split into two equal-height stacked images, 3pt gaps between all three
  images (in SwiftUI: a `HStack` with an inner `VStack`, `.clipped()` on each image, no rounding — the
  mosaic bleeds to all four screen edges, it's the background, not a card).
- **Images:** three of the six bundled `StyleSamples` — any three read fine since they're all real,
  warm-lit interiors; the mockup used japandi (large, left), warm-minimal and industrial (stacked, right).
- **Scrim:** one `LinearGradient`, top-to-bottom stops roughly `black@18% → black@8% (mid-screen) →
  black@62% → black@94% (bottom)` — the middle stays lightest so the mosaic is actually visible, both ends
  darken for status-bar and text legibility.
- **Content stack**, bottom-anchored via `Spacer()` above it, 26pt horizontal padding, 26pt bottom padding:
  1. Eyebrow `DESIGNMYROOM` — SF Mono 10.5pt, white 72%, `+0.14em` tracking, 10pt bottom margin.
  2. Headline `It's still your room.` — Fraunces 34pt Medium, white, two lines, line-height ~1.06pt tight,
     10pt bottom margin.
  3. Subtitle — existing copy, white 82%, 14pt, max-width ~280pt so it wraps short, 24pt bottom margin.
  4. `SignInWithAppleButton(.signIn)`, **`.white`** style, 50pt height, full width.
  5. Trust line `ONE FREE ROOM · NO PASSWORD, EVER` — SF Mono 10pt, white 60%, centered, 14pt top margin.
- Sign-in-failed error text: same white-on-dark treatment as the trust line but in a warning tone (white
  text is fine here too — this dark background never needs a separate "error mode" color, just placement
  directly above the button).

---

## 5. Hold off on / sequence carefully

- **Editorial feed (Home direction B).** Fully built and compared on the reference page, but `home-layout`
  was decided as `grid`. Don't implement it — it exists only as the rejected alternative for the record.
- **Fraunces font bundling.** Real work (licensing/downloading static weights, Xcode target + `Info.plist`
  registration), not a style tweak. Sequence it early since it affects every screen's title treatment; use
  system serif (`design: .serif`) as a temporary stand-in only if this genuinely needs to be deferred past
  the rest of the visual pass.
- **`Room.thumbnail_url`.** Contract field exists, backend resolution is in progress per the orchestrator.
  Build the grid card to consume it via `AsyncImage` now, but don't block the rest of this redesign on it
  landing — render the `surface2` placeholder until it's populated for real.
- **Dev-only sign-in block placement.** Needs a decision (see §2's Sign-in note) on how the `#if DEBUG`
  panel sits inside the new full-bleed layout. Doesn't block Release, but will visibly break local dev
  testing if left as-is against the new dark background — worth resolving before the redesign lands on the
  `ios` branch, not after.
- **Edge states (low-confidence banner, render-failed card) on Compare.** These got one pass each on the
  reference page, not the same iteration the core happy-path screens got. Tokens are consistent with
  everything else, but sanity-check the actual copy/layout against `ErrorCopy` once built — treat these as
  lower-confidence than Home, Sign-in, Style, and Confirm.
- **Dark mode.** Explicitly not addressed. Don't add `prefers-color-scheme`-style adaptive tokens as part
  of this pass — the palette is a single deliberate light system for now.
