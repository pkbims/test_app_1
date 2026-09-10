# Handoff — app_1

Context for a fresh session acting as orchestrator. Read this, then `PRD.md`.

## What this is

App #1 of a planned series of ~30 small full-stack apps, each built to production
standards and filmed as a teaching video. The series doctrine is in `../CLAUDE.md`:
real auth, real database, Docker, CI/CD, tests that gate the pipeline, rate limiting,
health checks, error tracking, structured logging, metrics and a dashboard. Never
propose the shortcut version — that is the entire point of the series.

**This app:** an iOS app that restyles a photo of a room without changing the room.
Positioning: *"basically DecorAI or Interium, but it never invents architecture."*
The wedge is credibility. Every competitor hands back a different room; that is the
most repeated complaint in the research and the only problem this app solves.

## Where we are

Pipeline stages 1–4 are done. **The contract is frozen** — see `contract/openapi.json`,
generated from `backend/app/schemas.py` and `backend/app/main.py`.

**Stage 5 (build) started 2026-09-09.** Two worker agents (Sonnet) in git worktrees:
`backend` and `ios`. Briefs: `backend/AGENT.md`, `ios/AGENT.md`. Cross-cutting and
contract questions go in `ORCH-QUESTIONS.md`. Orchestrator pushes and integrates;
workers commit locally to their own branch only.

**Backend is done and merged into `main`** (`dac3e44`, 2026-09-09): docker compose
(api/db/worker/dashboard), three-state health, migrations, Sign in with Apple,
rooms + photos + signed file URLs, inventory (`gpt-4.1`), renders + queue worker
(`gpt-image-2`, no mask) + preservation scoring, rate limiting, `/metrics`,
structured logging, error tracking, the PRD §17 failure table, full CI. 151 tests
green (95 unit + 56 integration), a real-OpenAI end-to-end render passes, contract
byte-identical throughout. Independently verified by the orchestrator (clean
`docker compose up --build`, `/health` ok, 95 unit tests green in a fresh
container). `VISION_BACKEND=fake` is the default — the whole stack runs with no
OpenAI key. Four contract questions resolved (`ORCH-QUESTIONS.md` Q1–Q4); one
contract change made — `ErrorCode.not_found` (404), commit `4df0db7`.

**iOS resumed 2026-09-09** once the backend was verified — rebased onto the merged
`main`, now building against the real running API (not mocks) wherever practical.

| Artefact | Location |
|---|---|
| Research — 63 verbatim complaints, 45 people | `research/home-decorating.md` |
| Positioning — one paragraph, locked | `positioning.md` |
| Spec — interactive, 19 sections, 42 decisions | `spec/index.html` |
| Decisions — the source of truth | `spec/state.json` |
| PRD — **generated**, do not hand-edit | `PRD.md` (`python3 spec/build_prd.py`) |
| iOS designs — 8 screens, clickable | `ui_ux/DesignMyRoom iOS screens/` |
| Spike — the proof the idea works | `spike/` |

## The validated architecture — read this before writing any code

This was proven by experiment on 2026-09-09, not assumed. Five image edits, ~12 cents.

**It works like this, in two API calls:**

1. **Inventory** — a vision call (`gpt-4.1`) lists everything in the photo. Fixed
   architecture (fireplace, mantel, alcove, ceiling step, flooring, switches, walls)
   and moveable objects. Each item gets a letter, a short name for the user, and a
   precise positional description for the image model.
2. **Confirm** — the user sees the letters on their photo and taps what to remove.
   Everything else stays by default.
3. **Generate** — one `gpt-image-2` edit call whose prompt names every architectural
   item verbatim under "must remain exactly where they are", kept objects under
   "keep in the same positions", and tapped ones under "remove entirely".

**Things that are proven NOT to work. Do not reintroduce them:**

- **Masks do not work.** The `mask` parameter on `/v1/images/edits` does not preserve
  the masked region. In testing it deleted the fireplace we asked it to protect;
  measured pixel change inside the protected region was *higher* than outside.
- **Compositing the original back is impossible.** Output is never pixel-aligned with
  input; the API returns fixed sizes and reframes the scene.
- **Padding the input to match the output aspect does not help.** It made drift worse.
- **Claude cannot generate images.** Vision only.

**Consequences already baked into the spec:** before/after must be stacked, never a
wipe slider (nothing aligns). Success is measured as *preservation rate* — a vision
call checks the result against the inventory list, item by item — not by pixel diff.

## Stack, all decided

Backend Python + FastAPI, PostgreSQL, job queue as a Postgres table, photos on local
disk (deliberately temporary), Sign in with Apple, client polls every 2s.
Client SwiftUI, tap-to-toggle outlines (no dragging), built locally with no CI/CD
(a deliberate, recorded hole), unit tests only.

Full list with rationale and rejected options: `PRD.md` § "Decisions on record".

## Environment

- **Xcode installed**, licence accepted. iOS work can start today.
- **Docker installed and running** (Desktop 4.90.0). `docker` + `docker compose` are
  on PATH in a fresh login shell. Homebrew still not installed (not needed — Postgres
  runs in Docker).
- **OpenAI key** in `app_1/.env` as `OPENAI_API_KEY`. Gitignored. Never print it,
  never commit it, never paste it into chat.
- Repos: `pkbims/test_app_1` (this) and `pkbims/building_apps` (pipeline + skills),
  both private.

## The plan

**The contract is frozen.** 13 operations in `contract/openapi.json`. Regenerate with
`python3 backend/export_openapi.py` after any signature change — never edit the JSON.
Note `RenderCreate.remove_ids`: the old spec said `keep_items`, but the validated flow
marks removals, because everything not tapped is kept by default.

**Two agents in git worktrees, not more than two.** They share no files —
Python and Swift — which is why parallelism is safe here.

```
herdr worktree create --cwd ~/Documents/building_apps/app_1 --branch ios --label ios
herdr worktree create --cwd ~/Documents/building_apps/app_1 --branch backend --label backend
herdr agent start ios --kind claude --pane <pane-id>
```

Each brief is written: `backend/AGENT.md`, `ios/AGENT.md` — what it owns, what it must
not touch, TDD, build order, and what done looks like.

**The one rule that matters:** neither agent may change the contract. When one finds
the contract wrong — and one will — it stops and asks. An agent that edits the
contract unilaterally has silently forked the system.

Docker now works, so this is no longer forced: backend starts first (schema + a
running API), iOS ~30 min later against the live server.

## Known issue: `remove_ids` is unreliable

Found 2026-09-10. `KEEP` holds up in every render (position, identity, finish
restyled correctly) — but items tapped for **removal** often survive in the output.
Opposite of the assumed failure direction. Being addressed as part of a
`render/prompt.py` rewrite (see below), which must ship with a test proving removal
actually works, not just a hoped-for side effect.

## Style expansion, 6 → 18, in progress

Prompt-engineering work (`prompt_review/HANDOFF.md` once written) is expanding the
style catalog from 6 to 18, including non-traditional directions (a "cyberpunk"
style was A/B tested), each with a `decor_scale` controlling how much new decor it
may introduce. `style` stays a plain unvalidated string for this pass — a contract
enum is the right eventual fix, deliberately deferred (the frozen OpenAPI must
regenerate byte-identically, more delicate than it looks).

Two decisions explicitly deferred, not blockers: whether a dark/moody style makes
the preservation *metric* unreliable (measurement gap vs. render bug), and whether
seasonal styles (e.g. Christmas) show year-round or need availability logic.

## Working agreement with the user

- Flag when something has been done two or three times — it is a candidate for a skill.
- State the tradeoff behind each engineering choice in a sentence; this gets narrated.
- The user consistently chooses speed over rigour at technical forks. That is a
  deliberate, coherent bias. Raise a consequence once, then respect the decision.
- Explain in plain words. No jargon without a plain-language line beside it.
