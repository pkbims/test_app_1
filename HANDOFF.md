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
generated from `backend/app/schemas.py` and `backend/app/main.py`. Nothing of the app
itself is built yet; route bodies raise NotImplementedError on purpose.

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
- **Docker NOT installed.** Backend can be written but not run. Homebrew not installed.
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

Give each a brief in `backend/AGENT.md` / `ios/AGENT.md` saying what it owns, what it
must not touch, and what done looks like.

**The one rule that matters:** neither agent may change the contract. When one finds
the contract wrong — and one will — it stops and asks. An agent that edits the
contract unilaterally has silently forked the system.

Start iOS first; Docker is still missing, so a backend agent cannot run anything yet.

## Working agreement with the user

- Flag when something has been done two or three times — it is a candidate for a skill.
- State the tradeoff behind each engineering choice in a sentence; this gets narrated.
- The user consistently chooses speed over rigour at technical forks. That is a
  deliberate, coherent bias. Raise a consequence once, then respect the decision.
- Explain in plain words. No jargon without a plain-language line beside it.
