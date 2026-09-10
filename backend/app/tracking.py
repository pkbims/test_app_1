"""Error tracking (PRD §17, build-order step 11).

**Sentry SDK, not a self-hosted GlitchTip.** GlitchTip is Sentry-compatible and
keeps the data on our box, but it is four more containers (its own Postgres, Redis,
web, worker). The SDK talks the same protocol to either, so this is one env var
now and a DSN swap later if "errors leave the building" becomes a problem.

No DSN → a no-op, which is the default in dev. `send_default_pii=False` keeps IPs,
headers and cookies out of events; we never pass photos, prompts or tokens to it.
"""

from __future__ import annotations


def configure(dsn: str, environment: str, release: str = "app_1@0.1.0") -> None:
    if not dsn:
        return
    import sentry_sdk

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        traces_sample_rate=0.0,
        send_default_pii=False,
    )


def capture(exc: BaseException) -> None:
    try:
        import sentry_sdk

        sentry_sdk.capture_exception(exc)
    except Exception:  # noqa: BLE001 — tracking must never break the caller
        pass
