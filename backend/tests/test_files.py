from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from app import files

SECRET = "file-url-secret-value"


def _parts(url: str):
    q = parse_qs(urlparse(url).query)
    return int(q["exp"][0]), q["sig"][0]


def test_signed_url_round_trips():
    url = files.signed_url(
        "http://localhost:8000", "photos", "room/photo.jpg", SECRET, 3600, now=1000
    )
    assert url.startswith("http://localhost:8000/files/photos/room/photo.jpg?")
    exp, sig = _parts(url)
    assert files.verify("photos", "room/photo.jpg", exp, sig, SECRET, now=1000)


def test_expired_url_is_rejected():
    url = files.signed_url("http://x", "photos", "k", SECRET, 10, now=1000)
    exp, sig = _parts(url)
    assert not files.verify("photos", "k", exp, sig, SECRET, now=2000)


def test_tampered_key_is_rejected():
    url = files.signed_url("http://x", "photos", "k", SECRET, 10, now=1000)
    exp, sig = _parts(url)
    assert not files.verify("photos", "other-key", exp, sig, SECRET, now=1000)


def test_scope_is_bound_into_the_signature():
    url = files.signed_url("http://x", "photos", "k", SECRET, 10, now=1000)
    exp, sig = _parts(url)
    assert not files.verify("renders", "k", exp, sig, SECRET, now=1000)


def test_unknown_scope_is_rejected():
    assert not files.verify("secrets", "k", 9_999_999_999, "deadbeef", SECRET)
