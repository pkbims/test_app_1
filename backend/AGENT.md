# Backend agent — brief

You are one of two worker agents building app_1. You own the **backend**. Another
agent owns the iOS client in `ios/` and you never touch it.

## Read first, in this order

1. This file.
2. `../HANDOFF.md` — the orchestrator context and the validated architecture.
3. `../PRD.md` — the full spec. Generated from `spec/state.json`; **never edit it**.
4. `../contract/openapi.json` — the frozen contract. Also **never edit** (see below).
5. `../../CLAUDE.md` — series doctrine. The non-negotiable baseline applies to you
   in full: real auth, real DB with migrations, Docker, GitHub Actions CI/CD, tests
   that gate the pipeline, rate limiting, health checks, error tracking, structured
   logging, metrics + a dashboard, deliberate failure handling. Never the shortcut.

## What you own

- Everything under `backend/`.
- `docker-compose.yml` at the repo root (API + Postgres + worker + dashboard).
- `.github/workflows/` for the backend pipeline.
- Database migrations.
- A `backend/README.md` with exact run instructions.

## What you must not touch

- `contract/openapi.json`, `backend/app/schemas.py`, and the **route signatures** in
  `backend/app/main.py`. You fill in the route *bodies*; you do not change shapes,
  paths, status codes, or field names.
- `ios/`, `PRD.md`, `spec/`, `research/`, `ui_ux/`, `positioning.md`.

## The one rule that matters

**You may not change the contract.** If you find it wrong — a missing field, an
impossible shape, a status code that can't work — you **stop**, append a numbered
entry to `../ORCH-QUESTIONS.md`, and keep working on the parts that don't depend on
it. Do not edit the contract yourself. A unilateral edit silently forks the system.
The orchestrator decides, regenerates `openapi.json` with
`python3 backend/export_openapi.py`, and tells you.

## TDD is mandatory

Red → green → refactor, every time. Write the failing test first, watch it fail,
then write the smallest code that passes. No endpoint, worker step, or helper gets
an implementation before it has a test. The CI pipeline gates on these tests — they
are the point, not an afterthought. Commit the test and the implementation together
or test-first; never implementation-first.

## Commit discipline

- Work on the `backend` branch (your worktree is already on it).
- Small, focused commits. Conventional-style messages (`feat:`, `test:`, `fix:`).
- End every commit message with:
  `Co-Authored-By: Claude <noreply@anthropic.com>`
- **Commit locally. Do not push.** The orchestrator handles pushing and integration.

## PRD prose vs. the contract — known deltas

The PRD was written before the spike and the freeze. Where they disagree, the
**contract + HANDOFF win**. Specifically:

- Render request marks **removals** (`remove_ids`), not keeps. Everything not tapped
  is kept by default. The PRD's `keep_items` is dead.
- **There is no mask anywhere.** No `mask_key`, no `mask_url`, no structure model,
  no depth/segmentation. Masking was tested and preserves nothing. The mechanism is
  two text calls (inventory → generate). The PRD's `STRUCTURE_MAP` table is replaced
  by `inventory` (a list of `InventoryItem`).
- Success metric is **`preservation_rate`** (0–1, a vision judgement over the
  architectural inventory items), not `fidelity_score`, not a pixel diff.
- Error codes are exactly the `ErrorCode` enum in `schemas.py`. The PRD's
  `structure_unavailable` is gone; use `inventory_failed` when the vision call fails.
- There is **no low-confidence flow** in v1. It belonged to the mask architecture.
  `Render` has no `low_confidence` field; do not invent one.

## Build order (from PRD §18, adapted to the frozen contract)

1. **`docker compose up`** brings up `api`, `db` (Postgres 16), `worker`, and the
   dashboard. Photos on a local-disk volume behind a small storage interface (one
   swap to S3 later, not a rewrite — PRD T3). `GET /health` returns the three-state
   check (db, photo storage, queue table, worker heartbeat, queue depth) per §17.
   `down` → non-zero, `degraded` → 200 with state, `ok` → 200.
2. **Migrations.** Pick a real tool (Alembic, or plain forward-only SQL files run on
   startup) and state the tradeoff in the README. Schema from PRD §15, adjusted:
   `users`, `rooms`, `photos`, `inventories` (items as JSONB, one row per room),
   `renders`, `credit_ledger` (append-only), `jobs` (the queue table).
3. **Sign in with Apple.** `POST /v1/auth/apple`: verify the identity token against
   Apple's JWKS, create the user on first sight, grant one free room as a
   `credit_ledger` row. Issue a JWT access token (~15 min) and a refresh token
   (~30 days, stored hashed). `POST /v1/auth/refresh`, `GET /v1/me` (credits = ledger
   sum). Rate limit `apple` 10/hr per IP, `refresh` 60/hr, `me` 60/min.
4. **Rooms & photos.** Create room, delete room (cascade: photo rows + files on
   disk). `POST /v1/rooms/{id}/photos`: multipart, ≤12 MB (`photo_too_large`),
   JPEG/PNG only — reject HEIC and everything else with `photo_unsupported`. Return
   a short-lived read URL (signed path or token). One photo per room.
5. **Inventory.** `POST /v1/rooms/{id}/inventory` calls `gpt-4.1` vision. Reuse the
   prompt and JSON schema from `../spike/identify.py` verbatim — it is proven.
   Architecture items → `kind=architecture`, `removable=false`; objects →
   `kind=object`, `removable=true`. Assign letters A, B, … then AA, AB if >26.
   Persist; `GET` reads it back. Vision-call failure → `inventory_failed`. No photo →
   `no_photos`.
6. **Renders.** `POST /v1/rooms/{id}/renders`: require an inventory (`no_inventory`),
   check the rate limit, dedup on `idempotency_key` (return the existing render, no
   second charge), check credits (`no_credits` → 402), spend one credit (ledger −1),
   insert a `queued` job, return 202. The **worker**: leases a job with a 5-minute
   lease (expired lease → back to `queued`), builds the prompt in the proven
   three-section form from `../spike/out/inventory_driven.txt` — architecture verbatim
   under "MUST REMAIN EXACTLY WHERE THEY ARE", kept objects under "KEEP …", the
   `remove_ids` items under "REMOVE these entirely" — calls `gpt-image-2`
   `/v1/images/edits` at `size=1536x1024`, **no mask**. Two retries with backoff;
   final failure → status `failed`, refund the credit (ledger +1), set `error_code`
   `render_failed`. On success, run the **preservation check**: a `gpt-4.1` vision
   call compares the result against the architectural inventory items and returns
   `preservation_rate` (fraction present) and `missing_items`. Store `before_url` /
   `after_url`.
7. `GET /v1/renders/{id}` (poll, 120/min), `GET /v1/rooms/{id}/renders` (list).
8. **Rate limiting** for every row in the PRD §16 table. In-process is acceptable at
   this scale — state the tradeoff (resets on restart, wrong behind multiple API
   replicas) and keep it behind one interface.
9. **`/metrics`** in Prometheus text format. Lead with `preservation_rate` mean and
   5th percentile, and inventory failure rate. Then render duration p50/p95, queue
   depth, worker count, failure rate by error code, cost per render.
10. **Structured JSON logging**, one line per request, a request id propagated from
    API into the worker and back. Log the fields §17 lists under "Always"; never log
    photos, photo URLs, tokens, emails, or prompt text.
11. **Error tracking.** Sentry SDK or self-hosted GlitchTip. State the tradeoff.
12. **Dashboard.** The doctrine requires one. Grafana in compose provisioned from a
    checked-in dashboard JSON against `/metrics`, or a small server-rendered HTML
    page. Pick one, state the tradeoff.
13. **CI/CD** — GitHub Actions: ruff + a type checker, unit tests, integration tests
    against a real Postgres service container, then build the image. The backend
    keeps the **full** pipeline (only the iOS half is exempt — PRD F3).
14. **Deliberate failure handling** — the PRD §17 "When things break" table, each row
    with a test: image-model error → retry then refund; worker dies mid-job →
    requeue after lease; structure/vision unavailable → refuse, never fall back to
    unconstrained generation; DB down → `/health` down + 503 everywhere.

## Environment

- `OPENAI_API_KEY` is in `.env` at this worktree's root (the orchestrator copies it
  in; it is gitignored). Load it from there. **Never** print, log, echo, or commit
  it. Compose reads it via `env_file`.
- Models: `gpt-4.1` (vision: inventory + preservation check), `gpt-image-2`
  (generation). Use the official `openai` Python SDK — add it to `requirements.txt`.
- Docker is installed and working (Desktop 4.90.0). A fresh login shell has `docker`
  and `docker compose` on PATH.
- Postgres: use the `postgres:16` image. No Homebrew needed.

## Done looks like

From a clean checkout: `docker compose up` → `/health` reports `ok` → a test can
sign in (mocked Apple token path), create a room, upload a photo, run the inventory,
submit a render, and poll it to `done` with a real `preservation_rate` — against
real OpenAI once, in an end-to-end test that is skippable in CI without a key. CI is
green. `backend/README.md` explains how to run everything. The §17 failure table is
covered by tests.

## When you're stuck or blocked

Append to `../ORCH-QUESTIONS.md` and keep moving on something else. Do not block the
whole build on one question, and do not guess at the contract.
