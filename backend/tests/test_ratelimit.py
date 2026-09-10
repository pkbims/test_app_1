from __future__ import annotations

from app.ratelimit import InProcessRateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def test_allows_up_to_limit_then_denies():
    rl = InProcessRateLimiter(clock=FakeClock())
    for _ in range(3):
        assert rl.check("ip:1.2.3.4", limit=3, window_s=3600).allowed
    denied = rl.check("ip:1.2.3.4", limit=3, window_s=3600)
    assert not denied.allowed
    assert denied.retry_after_s > 0


def test_window_resets_after_it_elapses():
    clock = FakeClock()
    rl = InProcessRateLimiter(clock=clock)
    for _ in range(3):
        rl.check("k", 3, 60)
    assert not rl.check("k", 3, 60).allowed
    clock.advance(61)
    assert rl.check("k", 3, 60).allowed


def test_keys_are_independent():
    rl = InProcessRateLimiter(clock=FakeClock())
    for _ in range(3):
        rl.check("a", 3, 60)
    assert rl.check("b", 3, 60).allowed


def test_retry_after_counts_down():
    clock = FakeClock()
    rl = InProcessRateLimiter(clock=clock)
    rl.check("k", 1, 100)
    first = rl.check("k", 1, 100).retry_after_s
    clock.advance(30)
    second = rl.check("k", 1, 100).retry_after_s
    assert second < first


def test_stale_keys_are_swept():
    clock = FakeClock()
    rl = InProcessRateLimiter(clock=clock)
    for i in range(1000):  # first sweep fires here; nothing is stale yet
        rl.check(f"old:{i}", 5, 1)
    clock.advance(5)
    for i in range(1000):  # 1000th check triggers the next sweep
        rl.check(f"new:{i}", 5, 100)
    assert not any(k.startswith("old:") for k in rl._windows)
    assert any(k.startswith("new:") for k in rl._windows)
