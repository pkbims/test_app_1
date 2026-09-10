# DesignMyRoom — iOS client

SwiftUI, iOS 17+. Restyles a photo of a room without changing the room — see
`../PRD.md` and `../HANDOFF.md` for the product; this file is build/run only.

## Layout

```
ios/
├── DesignMyRoomCore/     SwiftPM package — every testable line (models, networking,
│                         the render state machine, HEIC conversion, crash logging).
│                         `swift test` runs it with no Xcode project, no simulator.
├── DesignMyRoomApp/      SwiftUI views + view models. Thin — restyling a screen here
│                         must never mean touching DesignMyRoomCore.
├── project.yml           XcodeGen spec — the source of truth for project structure.
└── DesignMyRoom.xcodeproj  Generated from project.yml, committed so opening it in
                            Xcode needs no extra tooling.
```

## Run the backend first

From the repo root (one level up):

```bash
docker compose up --build
```

`VISION_BACKEND=fake` is the committed default — no OpenAI key needed, the whole
flow works offline with deterministic fake images. See `../backend/README.md`.

## Run the unit tests

```bash
cd DesignMyRoomCore
swift test
```

No simulator needed — the render state machine, token refresh, retry/backoff,
response decoding, and HEIC→JPEG all run as plain SwiftPM tests. A handful of tests
in `Tests/DesignMyRoomCoreTests/Integration/` talk to the real backend above instead
of a mock (per the orchestrator's instruction — a stronger test than a stub wherever
practical); they skip themselves (not a failure) if `docker compose up` isn't
running. `POST /v1/auth/apple` is rate-limited 10/hr per IP (PRD §16) shared across
every process hitting that backend, including your own repeated `swift test` runs —
if integration tests suddenly fail with `rateLimited`, that's why; `docker compose
restart api` resets the in-process limiter's window immediately instead of waiting
out the hour.

## Build and run the app

```bash
open DesignMyRoom.xcodeproj
```

Pick a simulator (iPhone 17 or similar, iOS 17+) and Run. Base URL defaults to
`http://localhost:8000`; override it without a code change by adding
`DESIGNMYROOM_BASE_URL` to the scheme's environment variables (Product ▸ Scheme ▸
Edit Scheme ▸ Run ▸ Arguments).

The Simulator shares the host Mac's network, so `localhost:8000` reaches the
Dockerized backend directly — and `localhost`/loopback connections are exempt from
App Transport Security by default, so no Info.plist change was needed. **On a real
device** this breaks: `localhost` means the device itself, not your Mac. Point
`DESIGNMYROOM_BASE_URL` at your Mac's LAN IP (`http://192.168.x.x:8000`) instead, and
that address will need its own ATS exception (`NSAppTransportSecurity` /
`NSExceptionDomains` in Info.plist) since it isn't the exempted loopback case —
nothing to do until on-device testing is actually needed.

Verified from the command line too:

```bash
xcodebuild -project DesignMyRoom.xcodeproj -scheme DesignMyRoom \
  -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' \
  -configuration Debug build
```

`BUILD SUCCEEDED`, code-signed "Sign to Run Locally" — no Apple Developer team
needed to build and run in the Simulator (only Sign in with Apple's actual handshake
needs one; see below).

### If you change `project.yml`

The project is generated with [XcodeGen](https://github.com/yonaskolb/XcodeGen). It
isn't preinstalled here and there's no Homebrew in this environment, so it was built
from source instead:

```bash
git clone --depth 1 --branch 2.42.0 https://github.com/yonaskolb/XcodeGen.git /tmp/xcodegen-src
cd /tmp/xcodegen-src && swift build -c release --product xcodegen
cp .build/release/xcodegen ~/.local/bin/xcodegen   # or wherever's on your PATH
```

Then, after editing `project.yml`:

```bash
xcodegen generate --spec project.yml
```

`DesignMyRoom.xcodeproj` is committed, so this step is only needed when the project
*structure* changes (a new target, a new Info.plist key, ...) — not for ordinary
Swift file edits, which Xcode's existing project already picks up.

## Known limitation: Sign in with Apple needs a human, once

No Apple Developer team is configured in this environment (`security find-identity`
shows zero signing identities). The sign-in code itself is real —
`AuthenticationServices`' `SignInWithAppleButton`, no fake/bypass login path — and the
app builds, installs, and renders the sign-in screen correctly. But actually
completing a sign-in past the button tap needs one of:

- **An Apple ID signed into the Simulator** (Settings ▸ Sign in to your iPhone), or
- **A real Apple Developer team** added in Xcode (Signing & Capabilities), with an
  App ID that has the Sign in with Apple capability registered, matching the
  `com.apple.developer.applesignin` entitlement already in
  `DesignMyRoomApp/DesignMyRoom.entitlements`.

Both are Xcode-UI/Apple-account steps — see `../ORCH-QUESTIONS.md` Q5. Everything
past that handshake is proven end-to-end against the real backend already: the
`RenderFlowIntegrationTests` in `DesignMyRoomCore` sign in via the backend's
documented dev-JWT path (`backend/app/auth/apple.py::verify_dev_token`, active
whenever `APPLE_CLIENT_ID` is unset — the committed `compose.env` default) and drive
the full flow: room → photo → inventory → render → poll to done, plus the
idempotency-key, `no_photos`, and `not_found` edge cases.

## Architecture, and the tradeoff behind each choice

| Choice | Why | What it costs |
|---|---|---|
| **A local SwiftPM package (`DesignMyRoomCore`) holds all testable logic**, a thin app target on top | TDD without the simulator — `swift test` is seconds, a simulator boot isn't. Also enforces the CLAUDE.md split: restyling a screen can't accidentally reach into networking. | A second Package.swift to keep in sync; trivial here since the app target only imports it. |
| **Hand-written `URLSession` + `async/await`**, no generated client, no dependency | PRD F4. The API is 13 operations — small enough that a generated client wouldn't save much, and every retry/refresh/decoding edge case is exactly the kind of thing worth owning and testing by hand. | More code than `URLSession.shared.data(for:)` one-liners; that code is what's tested. |
| **`APIClient` retries only idempotent requests** (every GET/DELETE, plus render creation specifically because its `idempotency_key` makes a retry safe) | A lost response after a non-idempotent POST (room creation, photo upload) could otherwise double it up. | Room creation, photo upload, and inventory creation don't get automatic retry — a transient failure there surfaces to the user as an error to retry manually. |
| **`RenderStateMachine` is a separate actor from `APIClient`**, not folded into the view model | It's the one piece PRD F5 names as "where client bugs live," so it gets its own unit tests independent of any UI. | An extra type to wire through `RoomFlowViewModel`; worth it for the isolation. |
| **HEIC passthrough-or-convert, not always-convert** (`PhotoFormatConverter`) | Re-encoding an already-JPEG/PNG photo is a needless quality/CPU cost; only HEIC/HEIF (what the camera/picker actually hand back by default) pays for a conversion. | The picker has to load the *original file bytes*, not a decoded `UIImage`, or the passthrough check never sees the real format — see `AddPhoto/PhotoPicker.swift`'s doc comment. |
| **No CI/CD** (PRD F3) | iOS CI needs macOS runners (~10× the cost of Linux minutes) and code-signing/provisioning-profile automation — the single fiddliest thing in the whole series, and deliberately not solved here. Build and test locally. | Nothing gates a bad commit before it lands; a deliberate, recorded hole in the baseline, same as the backend's. |
| **Crash/error reporting: a home-grown JSON-line log** (`CrashReporter`), not a vendor SDK | The client brief locks "no third-party dependencies"; the backend's Sentry choice doesn't extend to the client. | No dashboard, no alerting, no crash symbolication, and it cannot catch a Swift-level fatal trap (`fatalError`, a force-unwrapped `nil`) — only `NSException`-style crashes and errors explicitly logged from a `catch` block. Real error tracking is worth a vendor once this justifies the spend. |
| **Style catalog is hard-coded**, not fetched | `RenderCreate.style` is a bare string in the contract — there's no endpoint that lists styles. Six ids, shared with the backend by convention (`ios/AGENT.md`), not a contract field. | If the backend's accepted list ever differs, that's a cross-cutting question (`../ORCH-QUESTIONS.md`), not something either side can discover from the contract alone. |
| **Style cards are placeholder art**, not real sample photography | No stock-photo asset pipeline exists for this client yet. | Visually thin next to the design mock in `../ui_ux/`; swapping in real assets touches only `StylePickerView`, nothing else, by design. |

## What's tested, and how

`DesignMyRoomCore`'s test suite (`swift test`) — TDD throughout, red before green:

- **Models** — every `contract/openapi.json` schema round-trips through
  `JSONCoding`'s snake_case↔camelCase conversion and flexible ISO-8601 dates.
- **`RetryPolicy`** — backoff timing, and exactly which failures count as transient.
- **`KeychainTokenStore`** — against the real Keychain (this environment has one),
  not a fake: access token in memory only, refresh token persisted, survives a new
  store instance, `nil` on `save` doesn't erase an existing refresh token.
- **`APIClient`** — every operation, over a scripted `MockTransport`: auth headers,
  the silent 401-refresh-and-retry dance (and its failure mode, `.signedOut`),
  retry/backoff per method's idempotency, `restoreSession()` at cold launch, every
  error-decoding path (`ApiError`, `422` validation, a malformed body), the
  hand-built multipart upload.
- **`RenderStateMachine`** — the full `queued → running → done | failed` lifecycle,
  `renderFailed` vs. `requestFailed` as genuinely distinct terminal states,
  cancellation, resuming an existing render by id.
- **`PhotoFormatConverter`** — against the real fixture files in `../inputs/`
  (`IMG_1519.HEIC`, an actual iPhone photo; `room.jpg`; `mask_fireplace.png`), not
  synthetic bytes.
- **`ErrorCopy`** — every `ErrorCode` has fixed copy (PRD §16); `ApiError.message`
  wins over it when present.
- **`CrashReporter`** — the JSON-line sink appends correctly and survives a fresh
  instance (an app relaunch) without truncating what a previous one wrote.
- **Live integration** (`RenderFlowIntegrationTests`) — the same suite, but every
  call goes to a real running backend instead of `MockTransport`: full sign-in
  (dev-JWT) → room → photo → inventory → render → poll-to-done, plus the real HEIC
  fixture converted and uploaded, `no_photos`, `not_found`, and idempotency-key
  reuse. Skips itself if the backend isn't running.

View code is intentionally not unit-tested (CLAUDE.md: pure layout doesn't need a
test) — verified instead by building for the simulator and taking it through the
flow by hand.
