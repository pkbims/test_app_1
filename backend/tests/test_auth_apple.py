from __future__ import annotations

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth import apple

CLIENT_ID = "com.example.designmyroom"


class FakeSigningKey:
    def __init__(self, key) -> None:
        self.key = key


class FakeJWKClient:
    """Stands in for PyJWKClient — hands back one known public key."""

    def __init__(self, public_key) -> None:
        self._public_key = public_key

    def get_signing_key_from_jwt(self, _token: str) -> FakeSigningKey:
        return FakeSigningKey(self._public_key)


@pytest.fixture(scope="module")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _apple_token(rsa_key, **overrides) -> str:
    now = int(time.time())
    claims = {
        "iss": apple.APPLE_ISSUER,
        "aud": CLIENT_ID,
        "sub": "001234.abcdef.5678",
        "iat": now,
        "exp": now + 600,
    }
    claims.update(overrides)
    return jwt.encode(claims, rsa_key, algorithm="RS256")


def test_valid_token_yields_sub(rsa_key):
    client = FakeJWKClient(rsa_key.public_key())
    identity = apple.verify_identity_token(
        _apple_token(rsa_key), client_id=CLIENT_ID, jwk_client=client
    )
    assert identity.sub == "001234.abcdef.5678"


def test_wrong_audience_rejected(rsa_key):
    client = FakeJWKClient(rsa_key.public_key())
    with pytest.raises(apple.AppleAuthError):
        apple.verify_identity_token(
            _apple_token(rsa_key, aud="someone.else"), client_id=CLIENT_ID, jwk_client=client
        )


def test_wrong_issuer_rejected(rsa_key):
    client = FakeJWKClient(rsa_key.public_key())
    with pytest.raises(apple.AppleAuthError):
        apple.verify_identity_token(
            _apple_token(rsa_key, iss="https://evil.example"),
            client_id=CLIENT_ID,
            jwk_client=client,
        )


def test_expired_token_rejected(rsa_key):
    client = FakeJWKClient(rsa_key.public_key())
    with pytest.raises(apple.AppleAuthError):
        apple.verify_identity_token(
            _apple_token(rsa_key, exp=int(time.time()) - 10),
            client_id=CLIENT_ID,
            jwk_client=client,
        )


def test_token_signed_with_other_key_rejected(rsa_key):
    attacker = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    client = FakeJWKClient(rsa_key.public_key())
    forged = jwt.encode(
        {"iss": apple.APPLE_ISSUER, "aud": CLIENT_ID, "sub": "x", "exp": int(time.time()) + 60},
        attacker,
        algorithm="RS256",
    )
    with pytest.raises(apple.AppleAuthError):
        apple.verify_identity_token(forged, client_id=CLIENT_ID, jwk_client=client)


# ── dev fallback ─────────────────────────────────────────────────────────────
def test_dev_token_accepts_our_hs256_jwt():
    token = jwt.encode({"sub": "dev-user-1"}, "dev-secret", algorithm="HS256")
    assert apple.verify_dev_token(token, secret="dev-secret").sub == "dev-user-1"


def test_dev_token_rejects_wrong_secret():
    token = jwt.encode({"sub": "u"}, "dev-secret", algorithm="HS256")
    with pytest.raises(apple.AppleAuthError):
        apple.verify_dev_token(token, secret="not-it")


def test_dev_token_respects_exp():
    token = jwt.encode({"sub": "u", "exp": int(time.time()) - 5}, "dev-secret", algorithm="HS256")
    with pytest.raises(apple.AppleAuthError):
        apple.verify_dev_token(token, secret="dev-secret")
