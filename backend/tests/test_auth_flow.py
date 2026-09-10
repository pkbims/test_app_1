"""Sign in with Apple end to end (build-order step 3), via the real ASGI app and
a real Postgres. The dev token path stands in for Apple (APPLE_CLIENT_ID unset)."""

from __future__ import annotations

import jwt
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

SECRET = "flow-test-secret"


@pytest.fixture
def client(pg_url, tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", pg_url)
    monkeypatch.setenv("PHOTO_DIR", str(tmp_path))
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("APPLE_CLIENT_ID", "")
    from app.main import app

    with TestClient(app) as c:
        yield c


def _dev_token(sub: str) -> str:
    return jwt.encode({"sub": sub}, SECRET, algorithm="HS256")


def _sign_in(client, sub="000111.aaa.222"):
    r = client.post("/v1/auth/apple", json={"identity_token": _dev_token(sub)})
    assert r.status_code == 200, r.text
    return r.json()


def test_first_sign_in_grants_one_credit(client):
    tokens = _sign_in(client)
    assert tokens["access_token"] and tokens["refresh_token"]
    assert tokens["expires_in"] == 900

    me = client.get("/v1/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    assert me.json()["credits_left"] == 1


def test_second_sign_in_same_user_does_not_re_grant(client):
    _sign_in(client, sub="repeat.user")
    tokens = _sign_in(client, sub="repeat.user")
    me = client.get("/v1/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.json()["credits_left"] == 1


def test_me_requires_a_token(client):
    r = client.get("/v1/me")
    assert r.status_code == 401
    assert r.json()["code"] == "apple_token_invalid"


def test_me_rejects_garbage_token(client):
    r = client.get("/v1/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401
    assert r.json()["code"] == "apple_token_invalid"


def test_me_reports_expired_access_token_distinctly(client):
    from app.auth.tokens import issue_access

    dead, _ = issue_access("someone", SECRET, ttl_s=-1)
    r = client.get("/v1/me", headers={"Authorization": f"Bearer {dead}"})
    assert r.status_code == 401
    assert r.json()["code"] == "token_expired"


def test_refresh_rotates_and_revokes_the_old_token(client):
    tokens = _sign_in(client, sub="refresh.user")
    first = tokens["refresh_token"]

    r = client.post("/v1/auth/refresh", json={"refresh_token": first})
    assert r.status_code == 200, r.text
    rotated = r.json()
    assert rotated["refresh_token"] != first

    # the old refresh token no longer works
    again = client.post("/v1/auth/refresh", json={"refresh_token": first})
    assert again.status_code == 401
    assert again.json()["code"] == "apple_token_invalid"

    # the new one does
    ok = client.post("/v1/auth/refresh", json={"refresh_token": rotated["refresh_token"]})
    assert ok.status_code == 200


def test_apple_endpoint_is_rate_limited_per_ip(client):
    codes = [
        client.post("/v1/auth/apple", json={"identity_token": _dev_token("rl.user")}).status_code
        for _ in range(12)
    ]
    assert codes[:10] == [200] * 10
    assert 429 in codes[10:]
    limited = client.post("/v1/auth/apple", json={"identity_token": _dev_token("rl.user")})
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers


def test_request_id_is_returned_and_propagated(client):
    r = client.get("/v1/me", headers={"X-Request-Id": "trace-abc"})
    assert r.headers.get("x-request-id") == "trace-abc"
