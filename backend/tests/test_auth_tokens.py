from __future__ import annotations

import time

import pytest

from app.auth import tokens as tok

SECRET = "test-secret"


def test_issue_and_decode_roundtrip():
    token, expires_in = tok.issue_access("user-123", SECRET, 900)
    assert expires_in == 900
    claims = tok.decode_access(token, SECRET)
    assert claims.user_id == "user-123"


def test_expired_access_token_raises_token_expired():
    token, _ = tok.issue_access("u", SECRET, ttl_s=-1)
    with pytest.raises(tok.TokenExpired):
        tok.decode_access(token, SECRET)


def test_wrong_secret_raises_token_error():
    token, _ = tok.issue_access("u", SECRET, 900)
    with pytest.raises(tok.TokenError):
        tok.decode_access(token, "other-secret")


def test_tampered_token_raises_token_error():
    token, _ = tok.issue_access("u", SECRET, 900)
    with pytest.raises(tok.TokenError):
        tok.decode_access(token + "x", SECRET)


def test_refresh_token_used_as_access_token_is_rejected():
    # A refresh token is opaque, not a JWT — decode_access must not accept it.
    with pytest.raises(tok.TokenError):
        tok.decode_access(tok.new_refresh_token(), SECRET)


def test_non_access_type_jwt_rejected():
    import jwt

    other = jwt.encode(
        {"sub": "u", "iat": int(time.time()), "exp": int(time.time()) + 60, "type": "refresh"},
        SECRET,
        algorithm="HS256",
    )
    with pytest.raises(tok.TokenError):
        tok.decode_access(other, SECRET)


def test_refresh_tokens_are_unique_and_hash_is_stable():
    a, b = tok.new_refresh_token(), tok.new_refresh_token()
    assert a != b
    assert tok.hash_refresh_token(a) == tok.hash_refresh_token(a)
    assert tok.hash_refresh_token(a) != tok.hash_refresh_token(b)
    assert len(tok.hash_refresh_token(a)) == 64  # sha256 hex
