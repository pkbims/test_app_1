from __future__ import annotations

import pytest

from app.storage import LocalDiskStorage


def test_put_get_roundtrip(tmp_path):
    s = LocalDiskStorage(tmp_path)
    s.put("rooms/r1/photo.jpg", b"\xff\xd8bytes", "image/jpeg")
    assert s.get("rooms/r1/photo.jpg") == b"\xff\xd8bytes"
    assert s.exists("rooms/r1/photo.jpg")


def test_delete(tmp_path):
    s = LocalDiskStorage(tmp_path)
    s.put("a", b"x")
    s.delete("a")
    assert not s.exists("a")
    s.delete("a")  # idempotent


def test_missing_key_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        LocalDiskStorage(tmp_path).get("nope")


def test_key_cannot_escape_root(tmp_path):
    s = LocalDiskStorage(tmp_path / "store")
    with pytest.raises(ValueError):
        s.put("../escape", b"x")


def test_healthcheck_passes_on_writable_dir(tmp_path):
    LocalDiskStorage(tmp_path).healthcheck()  # no raise


def test_healthcheck_leaves_nothing_behind(tmp_path):
    s = LocalDiskStorage(tmp_path)
    s.healthcheck()
    assert list((tmp_path / ".health").glob("*")) == []


def test_put_is_atomic_no_tmp_left(tmp_path):
    s = LocalDiskStorage(tmp_path)
    s.put("x/y.bin", b"data")
    leftovers = [p.name for p in (tmp_path / "x").iterdir() if p.name.endswith(".tmp")]
    assert leftovers == []
