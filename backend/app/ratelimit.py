"""Rate limiting, behind one interface (PRD §16 limits, build-order step 8).

`InProcessRateLimiter` is fixed-window counters in a dict. Deliberately simple and
deliberately limited:

- counters reset when the process restarts;
- behind more than one API replica each replica counts on its own, so the real
  limit is `N × replicas`;
- a client can get up to `2 × limit` across a window boundary.

At ~10k users on one replica none of that bites. When it does, a Redis-backed
`RateLimiter` is a drop-in — nothing outside this file knows which is running.
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass

_SWEEP_EVERY = 1000


@dataclass(frozen=True)
class Decision:
    allowed: bool
    retry_after_s: int  # 0 when allowed


class RateLimiter(ABC):
    @abstractmethod
    def check(self, key: str, limit: int, window_s: int) -> Decision:
        """Count one request against `key`. Does not block."""


def enforce(limiter: RateLimiter, key: str, limit: int, window_s: int) -> None:
    """Count one request; raise `ApiError(rate_limited)` with `Retry-After` if over."""
    decision = limiter.check(key, limit, window_s)
    if not decision.allowed:
        from .errors import ApiError
        from .schemas import ErrorCode

        raise ApiError(
            ErrorCode.rate_limited,
            "You're going a little fast. Try again in a moment.",
            headers={"Retry-After": str(decision.retry_after_s)},
        )


class InProcessRateLimiter(RateLimiter):
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._windows: dict[str, tuple[float, int]] = {}  # key -> (reset_at, count)
        self._since_sweep = 0

    def check(self, key: str, limit: int, window_s: int) -> Decision:
        now = self._clock()
        with self._lock:
            self._maybe_sweep(now)
            entry = self._windows.get(key)
            if entry is None or now >= entry[0]:
                self._windows[key] = (now + window_s, 1)
                return Decision(True, 0)
            reset_at, count = entry
            if count >= limit:
                return Decision(False, int(reset_at - now) + 1)
            self._windows[key] = (reset_at, count + 1)
            return Decision(True, 0)

    def _maybe_sweep(self, now: float) -> None:
        self._since_sweep += 1
        if self._since_sweep < _SWEEP_EVERY:
            return
        self._since_sweep = 0
        self._windows = {k: v for k, v in self._windows.items() if v[0] > now}
