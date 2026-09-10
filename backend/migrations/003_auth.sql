-- 003 — refresh tokens.
-- Access tokens are stateless JWTs (~15 min). Refresh tokens are opaque random
-- strings (~30 days); we store only their SHA-256 hash, so a database leak does
-- not hand out live sessions. SHA-256 (not argon2) is fine here because the token
-- is 256 bits of randomness — there is nothing to brute-force.

CREATE TABLE refresh_tokens (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    -- Set when the token is rotated on /v1/auth/refresh, or on sign-out later.
    revoked_at timestamptz
);
CREATE INDEX refresh_tokens_user_idx ON refresh_tokens (user_id);
