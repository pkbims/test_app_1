# app_1 — backend

Restyles a photo of a room without changing the room. The API is deliberately dull:
it writes to Postgres and drops slow work onto a queue that lives *in* Postgres. A
separate worker does the OpenAI calls (`gpt-4.1` for the inventory and the
preservation check, `gpt-image-2` for the restyle).

## Run it

From the repository root (one level up from here):

```bash
echo 'OPENAI_API_KEY=sk-...' > .env    # optional — see "Vision backend" below
docker compose up --build
```

Non-secret config lives in `compose.env` (committed). `.env` is layered on top and
wins, so it holds secrets and any local overrides.

Four containers:

| Service     | Port | What it is |
|-------------|------|------------|
| `api`       | 8000 | FastAPI — the 13 `/v1/...` operations, `GET /health`, `GET /metrics`. |
| `db`        | 5432 | Postgres 16 — the database *and* the job queue. |
| `worker`    | —    | Leases render jobs, calls the image model, scores preservation. |
| `dashboard` | 8080 | Server-rendered status page over `/health` and `/metrics`. |

```bash
curl -s localhost:8000/health | python3 -m json.tool
open http://localhost:8080
```

## Vision backend

`VISION_BACKEND=fake` (the committed default) uses a deterministic stand-in for both
model calls, so `docker compose up` works with **no OpenAI key**. Set
`VISION_BACKEND=openai` and `OPENAI_API_KEY=...` in `.env` for the real thing.
`test_vision_e2e.py` makes one real `gpt-4.1` call against `inputs/room.jpg` and is
skipped without a key.

## Shopping backend ("shop your restyle", post-v1)

`SHOPPING_BACKEND=fake` (the committed default) is a deterministic two-item
result, no network calls at all — `docker compose up` works with no SearchApi
key. Set `SHOPPING_BACKEND=openai_searchapi` with `OPENAI_API_KEY=...` and
`SEARCHAPI_KEY=...` in `.env` for the real pipeline.

**Local dev needs a tunnel.** Step 3 of the pipeline hands SearchApi a URL to the
render and SearchApi (Google) fetches it — `PUBLIC_BASE_URL=http://localhost:8000`
is not reachable from the internet, so the real backend cannot work against a
plain local `docker compose up`. To exercise it locally:

1. Tunnel port 8000 (e.g. `ngrok http 8000`, or any equivalent) and note the
   public HTTPS URL it gives you.
2. Set `PUBLIC_BASE_URL=<that URL>` in `.env` (overrides `compose.env`'s
   localhost default) and restart `api`/`worker` so signed URLs use it.
3. Set `SHOPPING_BACKEND=openai_searchapi`, `OPENAI_API_KEY`, `SEARCHAPI_KEY`.

Without a tunnel, leave `SHOPPING_BACKEND=fake` — this is also what CI and the
default integration tests use. `SHOPPING_BACKEND=off` writes `none` without
calling anything, for a deliberate kill switch.

**`SHOPPING_DEV_IMAGE_HOST=catbox` is a TEMPORARY, dev-only escape hatch from
step 1 above** (ORCH-QUESTIONS Q11) — set it instead of tunnelling and the
pipeline uploads the render to catbox.moe (a public host we do not control)
and hands SearchApi that URL. **Never set this in production** —
`Settings.load()` refuses to start if it is — no deletion guarantee on
catbox's side, no terms agreed, and it breaks the TR4 promise. Delete it (see
the block comment on `_upload_to_catbox` in `app/shopping/pipeline.py`) once
tunnelling is everyone's normal path.

## The flow

```
POST /v1/auth/apple      → verify the Apple identity token, create the user,
                           grant 1 credit, return access + refresh tokens
POST /v1/rooms            → a room
POST /v1/rooms/{id}/photos → one JPEG/PNG, ≤12 MB; returns a signed read URL
POST /v1/rooms/{id}/inventory → gpt-4.1 lists architecture + objects, lettered A, B…
POST /v1/rooms/{id}/renders  → spend 1 credit, enqueue a job, 202
   (worker: 3-section prompt → gpt-image-2 edit @1536×1024, no mask →
    preservation check → status done, preservation_rate + missing_items)
GET  /v1/renders/{id}     → poll every 2s until done / failed (a failure refunds)
```

Auth is enforced by one ASGI middleware on `/v1/*` (except `/v1/auth/*`); it also
stamps a request id (honouring an inbound `X-Request-Id`) that follows a render
into the worker's logs. The `contract/openapi.json` has no security scheme — the
iOS client sends `Authorization: Bearer <access>` regardless (ORCH-QUESTIONS Q3).

Photo and render-image bytes are served by `/files/{scope}/{key}?exp&sig`
(HMAC-SHA256, 24h, `include_in_schema=False` so the contract stays byte-identical —
ORCH-QUESTIONS Q1).

## Health is three states, not two

`GET /health` returns `ok`, `degraded`, or `down` (PRD §17):

| State      | HTTP | Meaning | Example |
|------------|------|---------|---------|
| `ok`       | 200  | nothing to do | everything green |
| `degraded` | 200  | still serving, someone should look | no worker heartbeat in 60s; >100 jobs queued |
| `down`     | 503  | a deploy must stop here | database unreachable; photo storage unwritable |

Try it: `docker compose stop worker` → `degraded` within ~60s.
`docker compose stop db` → `down` / 503, and every `/v1/*` route returns 503 too.

## Metrics & logs

- **`GET /metrics`** — Prometheus text. Leads with `app1_preservation_rate_mean` /
  `_p5` and the inventory-failure counters (is the promise holding?), then renders
  by status, failures by `error_code`, submit-to-done duration p50/p95, queue
  depth, live workers, an estimated cost. HTTP traffic is in-process counters;
  everything about renders is a scrape-time SQL query (the worker writes that data,
  not the API), so `/metrics` still answers while the render pipeline is wedged.
- **Logs** — one JSON object per line. One access line per request (`app1.access`),
  one line per worker job (`worker.render`), request id threaded through. Never
  logged: photos, URLs, tokens, emails, prompt text.
- **Error tracking** — Sentry SDK, no-op without `SENTRY_DSN`.

## Tests

```bash
docker compose run --rm --no-deps api pytest        # fast units, no database
docker compose run --rm api pytest -m ""            # + integration, needs Postgres
```

**TDD is the workflow** (see `AGENT.md`): failing test first, every time. CI gates on
the whole suite. Integration tests each get their own scratch database. The PRD §17
"when things break" table is covered in `test_failure_handling.py` +
`test_render_flow.py` + `test_worker.py`.

## Choices, and the tradeoff behind each

| Choice | Why | What it costs |
|---|---|---|
| **Migrations = forward-only `.sql` files** on startup, under an advisory lock | Small schema, every change hand-reviewed. No framework on camera. | You write the DDL; no down-migrations; all pending run in one transaction. |
| **Queue is a Postgres table**, not Redis | One fewer service. Fine at 10k users. | Polling load on the primary; revisit past this scale. |
| **Photos on a local-disk volume**, behind `Storage` | PRD T3 — knowingly temporary. | Breaks with a second API replica. S3 is a new subclass, not a rewrite. |
| **One Docker image** for all three processes | They run identical code; one build. | Each carries the others' deps — a few MB. |
| **Auth: build it** (our JWT access token + hashed opaque refresh) | Most teaching material of any decision here; no vendor in the login path. | We own the security mistakes. Refresh rotates but has no reuse-detection in v1. |
| **In-process rate limiter** (fixed window) | Ship the skeleton; the waste is visible on the dashboard. | Resets on restart; per-replica; up to 2× at a window boundary. One swap to Redis behind the interface. |
| **Dashboard: server-rendered HTML**, not Grafana + Prometheus | Two fewer services, no scrape config or dashboard JSON. | Point-in-time only — no history or alerting. |
| **Error tracking: Sentry SDK**, not self-hosted GlitchTip | One env var vs. four more containers. Same protocol either way. | Events leave the box. Swap the DSN for GlitchTip later. |
| **Cost metric is an estimate** (`$0.04/render`) | Real per-call usage isn't logged yet. | Wrong if model prices move; label says "estimate". |
| **FastAPI / Pydantic pinned exactly** (`0.128.8` / `2.9.2`) | The frozen contract regenerates from these; their OpenAPI output drifts between minors. | Security bumps need a manual re-check with the orchestrator. |

## The contract is frozen

`app/schemas.py`, the route signatures in `app/main.py`, and `contract/openapi.json`
are not ours to change — we fill in route *bodies* only. `test_contract_frozen.py`
and a CI step fail if `export_openapi.py` output drifts. Those two files are excluded
from `ruff`/`mypy` — a reformat is a fork. Contract problems go to
`../ORCH-QUESTIONS.md`.

## Layout

```
backend/
  app/
    main.py       frozen route signatures + our route bodies
    schemas.py    frozen contract types
    middleware.py request id + auth + metrics + access log
    errors.py     ApiError → Error body; DB-down → 503
    ratelimit.py  RateLimiter interface + in-process impl + the LIMITS table
    settings.py   env → Settings
    db.py         the connection pool
    migrate.py    forward-only migration runner
    storage.py    Storage interface + LocalDiskStorage
    files.py      signed read URLs; files_route.py serves the bytes
    health.py     the three-state check
    metrics.py    Prometheus text (+ scrape-time SQL collector)
    logs.py       JSON logging
    tracking.py   Sentry init
    vision.py     gpt-4.1: inventory + preservation check (+ Fake/Disabled)
    imagegen.py   gpt-image-2: the edit call (+ Fake/Disabled)
    runtime.py    process-wide handles
    auth/  rooms/  inventory/  render/   — one package per area, service.py each
    shopping/     "shop your restyle" (post-v1): searchapi.py (vendor client),
                  judge.py (the model calls), pipeline.py (the steps), service.py (reads)
  migrations/     NNN_name.sql, applied in order
  worker/         leasing + the render pipeline + the shopping pipeline + the loop
  dashboard/      the status page
  tests/
```
