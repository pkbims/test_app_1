"""/metrics — Prometheus text (build-order step 9)."""
from __future__ import annotations

import io

import pytest
from PIL import Image

from .conftest import sign_in

pytestmark = pytest.mark.integration


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (900, 700), (170, 160, 150)).save(buf, format="JPEG")
    return buf.getvalue()


def _scrape(api) -> str:
    r = api.get("/metrics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    return r.text


def test_metrics_lead_with_the_promise_and_the_operational_gauges(api):
    body = _scrape(api)
    for name in (
        "app1_preservation_rate_mean",
        "app1_preservation_rate_p5",
        "app1_inventory_attempts_total",
        "app1_inventory_failures_total",
        "app1_queue_depth",
        "app1_workers_active",
        "app1_http_requests_total",
        "app1_render_cost_usd_estimate_total",
    ):
        assert name in body


def test_a_completed_render_shows_up_in_metrics(api, run_worker):
    headers = sign_in(api)
    room_id = api.post("/v1/rooms", json={}, headers=headers).json()["room_id"]
    api.post(
        f"/v1/rooms/{room_id}/photos",
        files={"file": ("r.jpg", _jpeg(), "image/jpeg")},
        headers=headers,
    )
    api.post(f"/v1/rooms/{room_id}/inventory", headers=headers)
    api.post(
        f"/v1/rooms/{room_id}/renders",
        json={"style": "warm-minimal", "remove_ids": [], "idempotency_key": "m1"},
        headers=headers,
    )
    assert run_worker() == "done"

    # These come from the (scratch) database, so the values are exact per test.
    body = _scrape(api)
    assert 'app1_renders_total{status="done"} 1.0' in body
    assert "app1_preservation_rate_mean 1.0" in body
    assert 'app1_preservation_scored_renders 1.0' in body


def test_rate_limit_rejections_are_counted(api):
    for _ in range(12):
        api.post("/v1/auth/apple", json={"identity_token": "x"})
    assert 'app1_rate_limited_total{rule="auth_apple"}' in _scrape(api)
