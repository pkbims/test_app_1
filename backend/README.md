# app_1 — backend

Restyles a photo of a room without changing the room. The API is deliberately dull:
it writes to Postgres and drops slow work onto a queue that lives *in* Postgres. A
separate worker does the OpenAI calls.

## Run it

From the repository root (one level up from here):

```bash
echo 'OPENAI_API_KEY=sk-...' > .env    # your real key; .env is gitignored
docker compose up --build
```

Non-secret config lives in `compose.env` (committed). `.env` is layered on top and
wins, so it holds secrets and any local overrides.

That brings up four containers:

| Service     | Port | What it is |
|-------------|------|------------|
| `api`       | 8000 | FastAPI. `GET /health`, and the `/v1/...` routes. |
| `db`        | 5432 | Postgres 16. Database *and* job queue. |
| `worker`    | —    | Records a heartbeat now; runs renders from build step 6 on. |
| `dashboard` | 8080 | Server-rendered status page over `/health` and `/metrics`. |

Check it:

```bash
curl -s localhost:8000/health | python3 -m json.tool
open http://localhost:8080
```

## Health is three states, not two

`GET /health` returns `ok`, `degraded`, or `down` (PRD §17):

| State      | HTTP | Meaning | Example |
|------------|------|---------|---------|
| `ok`       | 200  | nothing to do | everything green |
| `degraded` | 200  | still serving, someone should look | no worker heartbeat in 60s; >100 jobs queued |
| `down`     | 503  | a deploy must stop here | database unreachable; photo storage unwritable |

A two-state check makes every wobble look like an outage and people stop trusting
it. The middle state is the whole point.

Try it: `docker compose stop worker` → `degraded` within ~60s.
`docker compose stop db` → `down` / HTTP 503.

## Tests

```bash
docker compose run --rm --no-deps api pytest        # fast units, no database
docker compose run --rm api pytest -m ""            # + integration, needs Postgres
```

**TDD is the workflow here** (see `../backend/AGENT.md`): a failing test first,
every time. CI gates on the whole suite.

- **Unit tests** use fakes — no database, no network. The health-check logic, the
  storage interface, threshold maths.
- **Integration tests** (`@pytest.mark.integration`) get their own scratch database,
  created and dropped per test, so they never touch dev data.

## Choices, and the tradeoff behind each

| Choice | Why | What it costs |
|---|---|---|
| **Migrations = plain forward-only `.sql` files**, run on startup under an advisory lock | The schema is small and every change is hand-reviewed anyway. No framework to explain on camera. | No autogenerate — you write the DDL. No down-migrations — you roll forward with a fix. All pending migrations run in one transaction. |
| **Job queue is a Postgres table**, not Redis | One fewer service. Genuinely fine at 10k users. | A busy queue is polling load on the primary. Revisit past this scale. |
| **Photos on a local-disk volume**, behind a `Storage` interface | PRD T3 — knowingly temporary. | Breaks with a second API replica. Swapping to S3 is a new `Storage` subclass, not a rewrite. |
| **One Docker image** for api / worker / dashboard | Guarantees the three run identical code; one build. | Each carries the others' deps. A few MB at this size. |
| **Dashboard is a server-rendered HTML page**, not Grafana + Prometheus | Two fewer services, no scrape config, no dashboard JSON to keep in sync. | Point-in-time only — no history, no alerting. Swap in Grafana if we need trends. |
| **In-process everything** for now (no rate-limit store yet, heartbeat in a table) | Ship the skeleton first. | Rate limits (build step 8) will reset on restart and misbehave behind >1 replica — stated again there. |
| **FastAPI / Pydantic pinned exactly** (`0.128.8` / `2.9.2`) | `contract/openapi.json` is frozen and regenerated from these; their OpenAPI output drifts between minor versions. A test asserts the generated spec still equals the committed one. | Security updates need a manual bump + re-check with the orchestrator. |

## The contract is frozen

`app/schemas.py`, the route signatures in `app/main.py`, and `contract/openapi.json`
are not ours to change. We fill in route *bodies*. `tests/test_contract_frozen.py`
and a CI step fail if the generated spec drifts. If the contract is wrong, it goes
in `../ORCH-QUESTIONS.md` — never a unilateral edit.

Those two files are excluded from `ruff` and `mypy` for the same reason: a reformat
is a fork.

## Layout

```
backend/
  app/
    main.py        frozen route signatures + our route bodies
    schemas.py     frozen contract types
    settings.py    env → Settings
    db.py          the connection pool
    migrate.py     forward-only migration runner
    storage.py     Storage interface + LocalDiskStorage
    health.py      the three-state check
    runtime.py     process-wide handles (pool, storage, settings)
  migrations/      NNN_name.sql, applied in order
  worker/          the render worker (heartbeat only, for now)
  dashboard/       the status page
  tests/
```
