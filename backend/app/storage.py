"""Photo and render-image storage, behind one small interface.

Photos live in a folder on the server for now (PRD T3) — a deliberate, temporary
choice. Everything goes through `Storage`, so swapping to S3-compatible object
storage later is a new implementation of five methods, not a rewrite.
"""

from __future__ import annotations

import os
import pathlib
import secrets
from abc import ABC, abstractmethod


class Storage(ABC):
    @abstractmethod
    def put(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None: ...

    @abstractmethod
    def get(self, key: str) -> bytes: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def healthcheck(self) -> None:
        """Write, read back, and delete a probe object. Raises on any failure."""
        ...


class LocalDiskStorage(Storage):
    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = pathlib.Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> pathlib.Path:
        p = (self.root / key).resolve()
        if p != self.root and self.root not in p.parents:
            raise ValueError(f"key escapes storage root: {key!r}")
        return p

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temp name and rename, so a reader never sees a half-written file.
        tmp = p.with_name(f"{p.name}.{secrets.token_hex(6)}.tmp")
        tmp.write_bytes(data)
        tmp.replace(p)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def healthcheck(self) -> None:
        key = f".health/{secrets.token_hex(8)}"
        self.put(key, b"ok")
        try:
            if self.get(key) != b"ok":
                raise RuntimeError("storage read-back mismatch")
        finally:
            self.delete(key)
