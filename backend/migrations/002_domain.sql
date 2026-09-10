-- 002 — the domain (PRD §15, adjusted to the frozen contract and the spike).
-- A user owns rooms; a room holds one photo and one inventory; a render is one
-- attempt at restyling that room. Credits are an append-only ledger, not a number.

CREATE TABLE users (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- The Apple `sub` claim: stable, opaque, per-user. We deliberately do not
    -- store the relay email — we send no mail, so it is only a liability.
    apple_sub  text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE rooms (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label      text CHECK (label IS NULL OR char_length(label) <= 80),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX rooms_user_idx ON rooms (user_id);

CREATE TABLE photos (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- One photo per room; we do not ask for more (contract, PRD §8).
    room_id      uuid NOT NULL UNIQUE REFERENCES rooms(id) ON DELETE CASCADE,
    storage_key  text NOT NULL,
    content_type text NOT NULL CHECK (content_type IN ('image/jpeg', 'image/png')),
    width        int NOT NULL,
    height       int NOT NULL,
    byte_size    int NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now()
);

-- One inventory per room, items stored whole as JSONB (a list of the contract's
-- InventoryItem). The primary key on room_id is what enforces "one row per room";
-- re-running the inventory upserts.
CREATE TABLE inventories (
    room_id    uuid PRIMARY KEY REFERENCES rooms(id) ON DELETE CASCADE,
    items      jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE renders (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id           uuid NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    -- Denormalised so ownership and rate-limit checks don't need a join to rooms.
    user_id           uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status            text NOT NULL DEFAULT 'queued'
                      CHECK (status IN ('queued', 'running', 'done', 'failed')),
    style             text NOT NULL,
    prompt            text,
    remove_ids        jsonb NOT NULL DEFAULT '[]'::jsonb,
    idempotency_key   text NOT NULL,
    before_key        text,
    after_key         text,
    preservation_rate double precision
                      CHECK (preservation_rate IS NULL
                             OR (preservation_rate >= 0 AND preservation_rate <= 1)),
    missing_items     jsonb,
    error_code        text,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    -- A retry with the same key returns the existing render, not a second charge.
    UNIQUE (user_id, idempotency_key)
);
CREATE INDEX renders_room_idx ON renders (room_id, created_at DESC);

-- Append-only. A balance is sum(delta); a refund is just another row. Never
-- UPDATE or DELETE here.
CREATE TABLE credit_ledger (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    delta      int NOT NULL,
    reason     text NOT NULL,
    render_id  uuid REFERENCES renders(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX credit_ledger_user_idx ON credit_ledger (user_id);

-- Now that renders exists, tie the queue to it.
ALTER TABLE jobs
    ADD CONSTRAINT jobs_render_id_fkey
    FOREIGN KEY (render_id) REFERENCES renders(id) ON DELETE CASCADE;
