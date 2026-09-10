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
- **Question:** `Photo.url`, `Render.before_url`, `Render.after_url` are URLs the client
  fetches, but no operation in `openapi.json` returns image bytes. Where does the
  client GET the actual image?
- **Blocks:** the *value* of the url fields (build steps 4, 6), not the endpoints.
- **Answer:** (orchestrator) **Signed static URLs, served by the API, not a documented
  operation — contract unchanged.** Mount a file route with
  `include_in_schema=False` so `openapi.json` stays byte-identical. Shape:
  `{PUBLIC_BASE_URL}/files/{scope}/{key}?exp={unix}&sig={hmac_sha256}` where `scope`
  is `photos` or `renders`, `sig` is HMAC over `"{scope}/{key}:{exp}"` with the app
  secret. Reads expire in 24h. Files live on local disk behind your storage
  interface (PRD T3). The client just loads whatever URL it is handed — it never
  builds one. iOS brief will say this.
- **Status:** answered

## Q2 — No 404 / "not found" in the contract
- **From:** backend
- **Date:** 2026-09-09
- **Question:** `E` has no 404 and `ErrorCode` has no `not_found`/`forbidden`.
  Path-id endpoints can't express "unknown id" or "not your resource".
- **Answer:** (orchestrator) **Contract changed — minimally.** Added
  `not_found = "not_found"` to `ErrorCode` (regenerated `openapi.json`, +1 enum
  value, nothing else moved). Behaviour: unknown id **and** "not yours" both return
  **404** with `{"code": "not_found", "message": ...}` — same response for both, so
  existence never leaks. No `forbidden`, no change to the `E` responses dict (a bare
  404 body is fine; over-advertising 404 on every route isn't worth it). Backend:
  merge `main`, then run `export_openapi.py` in your pinned toolchain and confirm the
  drift test still passes byte-for-byte; if pydantic 2.9.2 renders it differently
  than my 2.13.5 did, commit the canonical regen and tell me.
- **Status:** contract changed

## Q3 — Auth is not expressible in the frozen signatures (FYI)
- **From:** backend
- **Date:** 2026-09-09
- **Question:** No `Authorization` param in the signatures, no `securitySchemes` in
  the spec. Enforcing in ASGI middleware over `/v1/*` except `/v1/auth/*`.
- **Answer:** (orchestrator) **Accepted, no contract change.** The middleware
  approach is right — keeps the signatures frozen. Missing/invalid/expired token →
  `401` with an `Error` body (`token_expired` when it parsed but aged out,
  `apple_token_invalid` otherwise). The OpenAPI won't advertise auth; the iOS client
  sends `Authorization: Bearer <access>` on every `/v1/*` call except `/v1/auth/*`
  regardless (already in its brief). Not worth adding `securitySchemes` — it would
  mean a dependency on every route.
- **Status:** answered
