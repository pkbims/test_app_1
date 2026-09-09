# iOS agent — brief

You are one of two worker agents building app_1. You own the **iOS client**. Another
agent owns the backend in `backend/` and you never touch it.

## Read first, in this order

1. This file.
2. `../HANDOFF.md` — orchestrator context and the validated architecture.
3. `../PRD.md` — the full spec (§13 is the iOS section). Generated; **never edit it**.
4. `../contract/openapi.json` — the frozen contract. Your client is built against
   exactly these shapes. **Never edit it** (see below).
5. `../../CLAUDE.md` — series doctrine. Most of the baseline lives in the backend by
   decision (PRD C2); your share is unit tests and crash/error reporting. No health
   checks, no Docker, and — deliberately — **no CI/CD** (PRD F3).
6. The designs: open `../ui_ux/DesignMyRoom iOS screens/DesignMyRoom.dc.html` in a
   browser (it is a clickable prototype — 8 flow screens + 6 edge states) and read
   `../ui_ux/DesignMyRoom iOS screens/github.md` for the screen map.

## What you own

- Everything under `ios/` — a new SwiftUI app (create the Xcode project here).
- `ios/README.md` with exact build/run instructions.

## What you must not touch

- Anything outside `ios/`. Not `backend/`, not the contract, not `PRD.md`, not
  `spec/`, not `ui_ux/`.

## The one rule that matters

**You may not change the contract.** If you find it wrong or insufficient — a field
you need that isn't there, a shape that can't drive the screen — you **stop**,
append a numbered entry to `../ORCH-QUESTIONS.md`, and keep working on the parts
that don't depend on it. The orchestrator decides. A unilateral edit forks the
system.

## TDD is mandatory

Red → green → refactor. Write the failing test first, watch it fail, then implement.
This applies especially to the render state machine and the networking/retry layer
(PRD F5) — that is where client bugs live. Pure logic (state machine, token
refresh, retry/backoff, response decoding, HEIC→JPEG) is all testable without the
simulator; test it that way. View code that is pure layout does not need a test;
anything with a branch does.

## Commit discipline

- Work on the `ios` branch (your worktree is already on it).
- Small, focused commits. Conventional-style messages.
- End every commit message with:
  `Co-Authored-By: Claude <noreply@anthropic.com>`
- **Commit locally. Do not push.** The orchestrator handles pushing and integration.

## Decisions already locked (PRD §13) — do not relitigate

- **SwiftUI** (F1), iOS 17+ target.
- **Networking:** hand-written `URLSession` + `async/await`. No third-party
  dependencies. Base URL configurable; default `http://localhost:8000` for local dev.
- **Auth:** Sign in with Apple (`AuthenticationServices`). Access token in memory,
  refresh token in the Keychain. On `401 token_expired`, refresh silently once and
  retry the original request; on refresh failure, sign out.
- **Confirm screen:** tap items on/off — **no dragging** (F2). See the deviation
  note below for how this is drawn.
- **Before/after:** **stacked**, both visible at once, no slider (U3). Nothing in the
  output aligns with the input, so a wipe slider is impossible — don't build one.
- **Style picker:** scrollable image cards with generic sample photos (U4), preset
  style id + optional free-text prompt (≤280 chars).
- **Client baseline (F5):** unit tests on the render state machine + networking.
  Crash/error reporting is in scope. Funnel events optional. **No CI.**

## Deviations from the PRD that the orchestrator has already decided

The PRD §8 / F2 imagine letter outlines positioned *on the photo*. The frozen
`InventoryItem` has **no coordinates** — only `id`, `kind`, `name`, `description`,
`removable`. The spike never produced geometry and adding it isn't proven. So:

- **The confirm screen is a labelled list, not a photo overlay.** Show the photo at
  the top for reference. Below it, the inventory as rows: letter + `name`, grouped
  architecture vs. objects. Architecture rows are informational ("locked"). Object
  rows (`removable == true`) have a "Remove" toggle. Tapped rows go into
  `remove_ids` on the render request. Everything not toggled is kept.
- **No low-confidence screen.** There is no confidence field in the contract; that
  flow belonged to the removed mask architecture. Skip screen 4 of the prototype.
- **Style ids** (shared with the backend — hard-code this list, raise a question if
  the backend's list differs): `warm-minimal`, `scandi`, `mid-century`, `japandi`,
  `modern-coastal`, `industrial`.

If you disagree with these, raise it in `../ORCH-QUESTIONS.md` — don't just diverge.

## Screens to build (PRD §8, github.md)

1. **Sign in** — Sign in with Apple button → `POST /v1/auth/apple` with the identity
   token → store tokens. One free room is granted server-side.
2. **Add a photo** — `PHPickerViewController` or camera. Convert HEIC→JPEG client
   side with ImageIO (the image API rejects HEIC). Check ≤12 MB. `POST` multipart to
   `/v1/rooms/{id}/photos`. One photo, asked once, silently (U1).
3. **Confirm** — `POST /v1/rooms/{id}/inventory`, then the labelled-list screen
   described above. "Continue" proceeds with the chosen `remove_ids`.
4. **Pick a style** — scrollable cards + optional prompt field.
5. **Rendering** — `POST /v1/rooms/{id}/renders` with `style`, `prompt`,
   `remove_ids`, a client-generated `idempotency_key` (UUID). Then poll
   `GET /v1/renders/{id}` every 2 s. State machine: `queued → running → done |
   failed`. This is the unit-tested core.
6. **Compare** — stacked `before_url` / `after_url` (use `AsyncImage`), show
   `preservation_rate` as a percentage and list `missing_items` if any are present.
   "Restyle" returns to the style picker.
7. **Edge states** — map each `Error.code` to the user-facing copy in the PRD §16
   table: `no_credits`, `rate_limited`, `photo_too_large`, `no_photos`,
   `inventory_failed`, `render_failed`, `apple_token_invalid`. Show `Error.message`
   verbatim when present.

## Architecture the app must keep cheap (CLAUDE.md)

- Adding a screen or a style must be cheap. Restyling the UI must not touch
  networking or the state machine. Keep a clean split: a `APIClient` layer that
  returns typed models, a per-render state machine, and dumb SwiftUI views on top.

## Known open items — raise in ORCH-QUESTIONS.md, don't block on them

- **Sign in with Apple entitlement** needs an Apple Developer team. If none is
  configured, build the real SIWA path anyway, document the limitation in the
  README, and note it as a question — do not add a fake-login path that isn't in the
  contract without the orchestrator's sign-off.
- **Credits model:** the contract says a render "spends one credit" but also "one
  free room / three restyles". Display whatever `Render.credits_left` and `/v1/me`
  return; don't hard-code the rule.

## Done looks like

The app builds in Xcode and runs in the simulator. With the backend running locally
(`docker compose up` in the repo root), the full flow works end to end: sign in →
add photo → confirm → style → render → compare. Unit tests pass for the render state
machine, token refresh, retry/backoff, response decoding, and HEIC→JPEG.
`ios/README.md` explains how to build and run.

## When you're stuck or blocked

Append to `../ORCH-QUESTIONS.md` and switch to something else. Never guess at the
contract.
