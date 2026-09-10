"""Sign in with Apple end to end (build-order step 3), via the real ASGI app and
a real Postgres. The dev token path stands in for Apple (APPLE_CLIENT_ID unset)."""

from __future__ import annotations

import jwt
import pytest

from .conftest import TEST_JWT_SECRET, sign_in

pytestmark = pytest.mark.integration


def _dev_token(sub: str) -> str:
    return jwt.encode({"sub": sub}, TEST_JWT_SECRET, algorithm="HS256")


def test_first_sign_in_grants_one_credit(api):
    r = api.post("/v1/auth/apple", json={"identity_token": _dev_token("000111.aaa.222")})
    assert r.status_code == 200, r.text
    tokens = r.json()
    assert tokens["access_token"] and tokens["refresh_token"]
    assert tokens["expires_in"] == 900

    me = api.get("/v1/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    assert me.json()["credits_left"] == 1


def test_second_sign_in_same_user_does_not_re_grant(api):
    sign_in(api, sub="repeat.user")
    headers = sign_in(api, sub="repeat.user")
    assert api.get("/v1/me", headers=headers).json()["credits_left"] == 1


def test_me_requires_a_token(api):
    r = api.get("/v1/me")
    assert r.status_code == 401
    assert r.json()["code"] == "apple_token_invalid"


def test_me_rejects_garbage_token(api):
    r = api.get("/v1/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401
    assert r.json()["code"] == "apple_token_invalid"


def test_me_reports_expired_access_token_distinctly(api):
    from app.auth.tokens import issue_access

    dead, _ = issue_access("someone", TEST_JWT_SECRET, ttl_s=-1)
    r = api.get("/v1/me", headers={"Authorization": f"Bearer {dead}"})
    assert r.status_code == 401
    assert r.json()["code"] == "token_expired"


def test_refresh_rotates_and_revokes_the_old_token(api):
    first = api.post("/v1/auth/apple", json={"identity_token": _dev_token("refresh.user")}).json()[
        "refresh_token"
    ]

    rotated = api.post("/v1/auth/refresh", json={"refresh_token": first})
    assert rotated.status_code == 200, rotated.text
    new_refresh = rotated.json()["refresh_token"]
    assert new_refresh != first

    reused = api.post("/v1/auth/refresh", json={"refresh_token": first})
    assert reused.status_code == 401
    assert reused.json()["code"] == "apple_token_invalid"

    assert api.post("/v1/auth/refresh", json={"refresh_token": new_refresh}).status_code == 200


def test_apple_endpoint_is_rate_limited_per_ip(api):
    codes = [
        api.post("/v1/auth/apple", json={"identity_token": _dev_token("rl.user")}).status_code
        for _ in range(12)
    ]
    assert codes[:10] == [200] * 10
    assert codes[10] == 429
    limited = api.post("/v1/auth/apple", json={"identity_token": _dev_token("rl.user")})
    assert "Retry-After" in limited.headers


def test_request_id_is_echoed(api):
    r = api.get("/v1/me", headers={"X-Request-Id": "trace-abc"})
    assert r.headers.get("x-request-id") == "trace-abc"
