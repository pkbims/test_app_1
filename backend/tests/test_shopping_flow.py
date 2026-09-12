"""Shopping end to end with the fake backend (shopping_proto/HANDOFF.md §6.4):
render done -> shopping row pending -> job runs -> ready with the fixture items;
`off` -> none; a failed job after 2 attempts -> none, render untouched.
"""

from __future__ import annotations

import io

import psycopg
import pytest
from PIL import Image

from .conftest import sign_in

pytestmark = pytest.mark.integration


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1024, 768), (190, 175, 165)).save(buf, format="JPEG")
    return buf.getvalue()


def _done_render(api, headers, run_worker, **worker_kwargs) -> str:
    """Create a room, submit a render, and run the render job to completion.
    Returns the render_id. The shopping job is queued but NOT yet run."""
    room_id = api.post("/v1/rooms", json={"label": "Lounge"}, headers=headers).json()["room_id"]
    api.post(
        f"/v1/rooms/{room_id}/photos",
        files={"file": ("r.jpg", _jpeg(), "image/jpeg")},
        headers=headers,
    )
    api.post(f"/v1/rooms/{room_id}/inventory", headers=headers)
    render_id = api.post(
        f"/v1/rooms/{room_id}/renders",
        json={"style": "warm-minimal", "remove_ids": [], "idempotency_key": "shop-1"},
        headers=headers,
    ).json()["render_id"]
    assert run_worker(**worker_kwargs) == "done"
    return render_id


def test_shopping_is_pending_after_render_done_before_its_own_job_runs(api, run_worker):
    headers = sign_in(api)
    render_id = _done_render(api, headers, run_worker)
    body = api.get(f"/v1/renders/{render_id}/shopping", headers=headers).json()
    assert body["status"] == "pending"
    assert body["items"] == []
    assert body["total_from"] is None


def test_shopping_becomes_ready_with_the_fake_items(api, run_worker):
    headers = sign_in(api)
    render_id = _done_render(api, headers, run_worker)
    assert run_worker() == "done"  # the shopping job itself

    body = api.get(f"/v1/renders/{render_id}/shopping", headers=headers).json()
    assert body["render_id"] == render_id
    assert body["status"] == "ready"
    assert body["currency"] == "CAD"
    assert body["total_from"] == 140.0
    assert body["prices_as_of"] is not None
    assert [i["name"] for i in body["items"]] == [
        "Olive tree in a woven basket", "Stack of decorative books",
    ]
    for item in body["items"]:
        assert len(item["options"]) == 2
        got = api.get(item["crop_url"])
        assert got.status_code == 200
        assert got.headers["content-type"] == "image/jpeg"
        for opt in item["options"]:
            assert opt["price"] > 0
            assert opt["verified"] is True


def test_shopping_off_backend_writes_none_and_calls_nothing(api, run_worker):
    headers = sign_in(api)
    render_id = _done_render(api, headers, run_worker)
    assert run_worker(shopping_model=None, shopping_searchapi=None) == "done"

    body = api.get(f"/v1/renders/{render_id}/shopping", headers=headers).json()
    assert body["status"] == "none"
    assert body["items"] == []


def test_shopping_failed_job_after_two_attempts_is_none_and_render_untouched(api, run_worker, pg_url):
    class _BoomModel:
        def describe(self, *a):
            raise RuntimeError("model exploded")

        def refine(self, *a):
            return None

        def judge(self, *a):
            return {}

    headers = sign_in(api)
    render_id = _done_render(api, headers, run_worker)

    assert run_worker(shopping_model=_BoomModel()) == "retry"
    assert run_worker(shopping_model=_BoomModel()) == "failed"

    body = api.get(f"/v1/renders/{render_id}/shopping", headers=headers).json()
    assert body["status"] == "none"
    assert body["items"] == []

    render = api.get(f"/v1/renders/{render_id}", headers=headers).json()
    assert render["status"] == "done"
    assert render["after_url"]


def test_shopping_with_no_row_at_all_is_none(api, run_worker, pg_url):
    """A render that predates the feature (or any other reason its shopping row
    is missing) reads as `none`, not an error."""
    headers = sign_in(api)
    render_id = _done_render(api, headers, run_worker)
    with psycopg.connect(pg_url, autocommit=True) as conn:
        conn.execute("DELETE FROM shopping WHERE render_id = %s", (render_id,))

    body = api.get(f"/v1/renders/{render_id}/shopping", headers=headers).json()
    assert body["status"] == "none"


def test_get_shopping_requires_a_token(api, run_worker):
    headers = sign_in(api)
    render_id = _done_render(api, headers, run_worker)
    assert api.get(f"/v1/renders/{render_id}/shopping").status_code == 401


def test_get_shopping_on_another_users_render_is_404(api, run_worker):
    owner = sign_in(api, sub="shopping.owner")
    render_id = _done_render(api, owner, run_worker)

    intruder = sign_in(api, sub="shopping.intruder")
    assert api.get(f"/v1/renders/{render_id}/shopping", headers=intruder).status_code == 404


def test_get_shopping_on_unknown_render_is_404(api):
    headers = sign_in(api)
    assert (
        api.get(
            "/v1/renders/00000000-0000-0000-0000-000000000000/shopping", headers=headers
        ).status_code
        == 404
    )
