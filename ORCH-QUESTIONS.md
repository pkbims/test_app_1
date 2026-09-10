# Orchestrator questions

Where the two worker agents raise anything that touches the **contract** or the
**other half of the system**. The orchestrator owns this file's answers.

Rules:
- A worker **appends** a numbered entry, then keeps working on something else.
- A worker never edits `contract/openapi.json`, `backend/app/schemas.py`, or the
  route signatures in `backend/app/main.py`.
- The orchestrator answers inline, and — if the contract must change — regenerates
  `contract/openapi.json` with `python3 backend/export_openapi.py` and notes it here.

Format:

```
## Q1 — <short title>
- **From:** backend | ios
- **Date:** YYYY-MM-DD
- **Question:** ...
- **Blocks:** what you can't finish until this is answered
- **Answer:** (orchestrator) ...
- **Status:** open | answered | contract changed
```

---

<!-- new entries below -->

## Q1 — Nothing in the contract serves image bytes

- **From:** backend
- **Date:** 2026-09-09
- **Question:** `Photo.url` and `Render.before_url` / `after_url` are URLs the client
  fetches to display the photo and the before/after. But there is no operation in
  `openapi.json` that returns image bytes — the 11 paths are all JSON. Where does
  the client GET the actual image? Options I see:
  1. Add `GET /v1/photos/{token}` and `GET /v1/renders/{render_id}/image/{which}`
     (short-lived signed token in the path), served outside the documented API.
  2. `url` is a direct static path the API serves from a mounted photos dir
     (e.g. `/files/<key>?sig=...`), also not a documented operation.
  3. Something else the orchestrator has in mind.
  Any of these is a route added to `main.py`, which is frozen — hence this question.
- **Blocks:** the *value* of `Photo.url` and the render URL fields (build steps 4
  and 6). Not the endpoints themselves — I can build upload, inventory, render and
  the worker with a placeholder URL scheme and swap it once decided.
- **Answer:** (orchestrator)
- **Status:** open

## Q2 — `responses=E` has no 404; path-id endpoints can't say "not found"

- **From:** backend
- **Date:** 2026-09-09
- **Question:** The shared `E` responses dict is `{400, 401, 402, 413, 429, 500}` —
  no 404. `GET /v1/renders/{render_id}`, `GET /v1/rooms/{room_id}/inventory`,
  `DELETE /v1/rooms/{room_id}` etc. take an id that may not exist or may belong to
  another user. `ErrorCode` also has no `not_found` / `forbidden` member. Intended
  behaviour for "unknown id" and "not your resource"? My default, absent an answer:
  return **404 with an `Error` body** using the nearest existing code
  (`no_photos` / `no_inventory` where they fit, otherwise a generic 404 with
  `code: "rate_limited"` is clearly wrong — I'd rather return a bare 404). Please
  confirm, since the iOS client needs to know what to expect.
- **Blocks:** nothing yet — I'll implement rooms/renders with 404 + `Error` and
  revise if the answer differs.
- **Answer:** (orchestrator)
- **Status:** open

## Q3 — Auth is not expressible in the frozen signatures (FYI, not blocking)

- **From:** backend
- **Date:** 2026-09-09
- **Question:** The frozen route signatures take no `Authorization` parameter and
  `openapi.json` has no `securitySchemes`, so I'm enforcing auth in ASGI middleware
  over `/v1/*` (except `/v1/auth/*`): missing/expired token → 401 with an `Error`
  body (`token_expired` / `apple_token_invalid`). This keeps the generated spec
  byte-identical. Consequence: the OpenAPI does not advertise auth — the iOS client
  must send `Authorization: Bearer <access>` per the PRD §16 table regardless.
  Flagging in case the orchestrator would rather change the contract to make auth
  explicit.
- **Blocks:** nothing.
- **Answer:** (orchestrator)
- **Status:** open
