-- 008 — "shop your restyle" (post-v1, shopping_proto/HANDOFF.md §4.2).
--
-- One row per render, inserted `pending` the moment the shopping job is enqueued
-- (from the render job's own `_finish`, right after the render itself is marked
-- done). `items` is the whole `ShoppingItem` list, stored as the contract shapes
-- it — the API layer reads this straight into `Shopping.items`, no reshaping.
--
-- `searchapi_calls` / `searchapi_errors` are not in the handoff's column list but
-- are the only way to expose `shopping_searchapi_calls_total{outcome}` (§4.2's own
-- metrics list) without an in-process counter — the worker and the API are
-- separate processes, so an in-process Prometheus counter incremented by the
-- worker would never reach the API's /metrics scrape (see the identical reasoning
-- behind renders' own duration/preservation metrics being DB-scraped, not
-- in-process). Backend-internal, not contract-visible.

CREATE TABLE shopping (
    render_id       uuid PRIMARY KEY REFERENCES renders(id) ON DELETE CASCADE,
    status          text NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'ready', 'none')),
    items           jsonb NOT NULL DEFAULT '[]'::jsonb,
    total_from      numeric(10, 2),
    prices_as_of    date,
    cost_cents      numeric(8, 3),
    searchapi_calls int NOT NULL DEFAULT 0,
    searchapi_errors int NOT NULL DEFAULT 0,
    error           text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

-- The worker dispatches queued jobs by kind (`jobs.kind`, already a column since
-- 001_init.sql, always 'render' until now — no index needed, `lease_one` already
-- scans the small `jobs_runnable_idx` partial index and only branches on kind
-- after leasing). A shopping job's `jobs.render_id` points at the same render
-- it is shopping for — the existing FK already allows it, no schema change there.
