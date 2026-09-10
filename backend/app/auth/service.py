"""Sign-in, refresh, and the current-user read.

One free room is granted at signup as a `credit_ledger` row, not a column — so a
render spend and a refund are just more rows, and the balance can always be
recounted (PRD §15).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import ApiError
from ..schemas import ErrorCode, Me, Tokens
from . import tokens as tok
from .apple import AppleAuthError, AppleIdentity

SIGNUP_GRANT = 1
_SIGN_IN_FAILED = "That sign-in didn't work. Please try again."
_REFRESH_FAILED = "Your session has ended. Please sign in again."


@dataclass(frozen=True)
class Issued:
    user_id: str
    tokens: Tokens


def authenticate(
    conn, raw_token: str, verifier, *, secret: str, access_ttl_s: int, refresh_ttl_s: int
) -> Issued:
    try:
        identity = verifier(raw_token)
    except AppleAuthError as exc:
        raise ApiError(ErrorCode.apple_token_invalid, _SIGN_IN_FAILED) from exc

    with conn.transaction():
        user_id, created = _upsert_user(conn, identity)
        if created:
            conn.execute(
                "INSERT INTO credit_ledger (user_id, delta, reason) "
                "VALUES (%s, %s, 'signup_grant')",
                (user_id, SIGNUP_GRANT),
            )
        issued_tokens = _issue(conn, user_id, secret, access_ttl_s, refresh_ttl_s)
    return Issued(user_id=user_id, tokens=issued_tokens)


def refresh(
    conn, raw_refresh: str, *, secret: str, access_ttl_s: int, refresh_ttl_s: int
) -> Tokens:
    token_hash = tok.hash_refresh_token(raw_refresh)
    with conn.transaction():
        row = conn.execute(
            "SELECT id, user_id FROM refresh_tokens "
            "WHERE token_hash = %s AND revoked_at IS NULL AND expires_at > now() "
            "FOR UPDATE",
            (token_hash,),
        ).fetchone()
        if row is None:
            raise ApiError(ErrorCode.apple_token_invalid, _REFRESH_FAILED)
        rt_id, user_id = row
        # Rotation: the old token is spent. A leaked refresh token therefore works
        # only until the real client next refreshes. We do not add reuse-detection
        # (kill the whole session on seeing a revoked token) in v1.
        conn.execute("UPDATE refresh_tokens SET revoked_at = now() WHERE id = %s", (rt_id,))
        return _issue(conn, str(user_id), secret, access_ttl_s, refresh_ttl_s)


def current_user(conn, user_id: str) -> Me:
    row = conn.execute(
        "SELECT coalesce(sum(delta), 0) FROM credit_ledger WHERE user_id = %s",
        (user_id,),
    ).fetchone()
    return Me(user_id=user_id, credits_left=int(row[0]))


def _upsert_user(conn, identity: AppleIdentity) -> tuple[str, bool]:
    row = conn.execute(
        "INSERT INTO users (apple_sub) VALUES (%s) ON CONFLICT (apple_sub) DO NOTHING RETURNING id",
        (identity.sub,),
    ).fetchone()
    if row is not None:
        return str(row[0]), True
    existing = conn.execute("SELECT id FROM users WHERE apple_sub = %s", (identity.sub,)).fetchone()
    return str(existing[0]), False


def _issue(conn, user_id: str, secret: str, access_ttl_s: int, refresh_ttl_s: int) -> Tokens:
    access, expires_in = tok.issue_access(user_id, secret, access_ttl_s)
    raw_refresh = tok.new_refresh_token()
    conn.execute(
        "INSERT INTO refresh_tokens (user_id, token_hash, expires_at) "
        "VALUES (%s, %s, now() + make_interval(secs => %s))",
        (user_id, tok.hash_refresh_token(raw_refresh), refresh_ttl_s),
    )
    return Tokens(access_token=access, refresh_token=raw_refresh, expires_in=expires_in)
