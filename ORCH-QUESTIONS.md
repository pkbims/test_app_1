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
