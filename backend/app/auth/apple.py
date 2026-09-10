"""Verify a Sign in with Apple identity token.

Real path: fetch Apple's public keys (JWKS), check the token's RS256 signature,
issuer (`https://appleid.apple.com`), audience (our bundle id) and expiry, and
take the `sub` claim as the stable user id.

Dev path: when `APPLE_CLIENT_ID` is unset (local, tests, and the iOS client before
it has the Apple entitlement), accept an HS256 token signed with our own
`JWT_SECRET` carrying a `sub`. Never enabled when `APP_ENV=production`.
"""

from __future__ import annotations

from dataclasses import dataclass

import jwt
from jwt import PyJWKClient

APPLE_ISSUER = "https://appleid.apple.com"
APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"


@dataclass(frozen=True)
class AppleIdentity:
    sub: str


class AppleAuthError(Exception):
    """The identity token failed verification."""


def verify_identity_token(token: str, *, client_id: str, jwk_client: PyJWKClient) -> AppleIdentity:
    try:
        key = jwk_client.get_signing_key_from_jwt(token).key
        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=APPLE_ISSUER,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    except (jwt.InvalidTokenError, jwt.PyJWKClientError) as exc:
        raise AppleAuthError(str(exc)) from exc
    return AppleIdentity(sub=str(payload["sub"]))


def verify_dev_token(token: str, *, secret: str) -> AppleIdentity:
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"require": ["sub"], "verify_aud": False},
        )
    except jwt.InvalidTokenError as exc:
        raise AppleAuthError(str(exc)) from exc
    return AppleIdentity(sub=str(payload["sub"]))
