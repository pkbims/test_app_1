-- 001 — operational tables the health check depends on.
-- Domain tables (users, rooms, photos, inventories, renders, credit_ledger) land
-- in 002, alongside build-order step 2.

CREATE TABLE worker_heartbeats (
    worker    text PRIMARY KEY,
    last_seen timestamptz NOT NULL DEFAULT now()
);

-- The job queue (PRD §16, T9). One row per unit of slow work. The worker leases a
-- row by setting leased_by / lease_expires_at; an expired lease means the worker
-- died and the row is free again (PRD §17).
CREATE TABLE jobs (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kind             text NOT NULL DEFAULT 'render',
    render_id        uuid,
    status           text NOT NULL DEFAULT 'queued'
                     CHECK (status IN ('queued', 'running', 'done', 'failed')),
    attempts         int NOT NULL DEFAULT 0,
    leased_by        text,
    lease_expires_at timestamptz,
    last_error       text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now()
);

-- Partial index: the worker only ever scans for queued work.
CREATE INDEX jobs_queued_idx ON jobs (created_at) WHERE status = 'queued';
