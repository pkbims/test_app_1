"""SearchApi's `google_lens` engine — the only external caller in the shopping
pipeline (shopping_proto/HANDOFF.md §6.2). One HTTP GET per call: the render's own
signed URL plus a normalised crop box; no `q` (text made Lens match on words over
pixels — proven worse in research) and no `search_type=products` (also worse).

Response shape (real, observed): `visual_matches` and `products` are both lists of
candidates; a candidate's price is `extracted_price` (float or absent — SearchApi's
own numeric parse of the display price), its link is `link`, and `thumbnail` is a
SearchApi-hosted thumbnail image URL (fetching *that* is not scraping — it is the
image the vendor handed us; see HANDOFF §6.2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

_ENDPOINT = "https://www.searchapi.io/api/v1/search"


@dataclass(frozen=True)
class RawMatch:
    link: str
    title: str
    price: float | None
    thumbnail: str | None


@dataclass(frozen=True)
class SearchResult:
    matches: list[RawMatch]
    error: str | None = None


class SearchApiError(Exception):
    """The call failed outright (network, non-200, or an `error` body)."""


class SearchApi(Protocol):
    def search(self, render_url: str, crop: tuple[float, float, float, float]) -> SearchResult: ...

    def check_link(self, url: str) -> bool:
        """One GET, browser UA, short timeout (HANDOFF §5.1 step 4 / §6.2 — the
        one non-SearchApi network call the pipeline makes, and the only thing in
        this file that ever touches a retailer directly)."""

    def fetch_thumbnail(self, url: str) -> str | None:
        """Base64 JPEG, resized, or None if it couldn't be fetched. `url` is a
        thumbnail SearchApi itself handed us — not scraping (HANDOFF §6.2)."""


def _crop_param(crop: tuple[float, float, float, float]) -> str:
    return ";".join(f"{v:.3f}" for v in crop)


def _parse(payload: dict) -> SearchResult:
    if payload.get("error"):
        return SearchResult(matches=[], error=str(payload["error"]))
    raw = list(payload.get("visual_matches", [])) + list(payload.get("products", []))
    matches = [
        RawMatch(
            link=str(m.get("link") or ""),
            title=str(m.get("title") or ""),
            price=_as_float(m.get("extracted_price")),
            thumbnail=m.get("thumbnail"),
        )
        for m in raw
        if m.get("link")
    ]
    return SearchResult(matches=matches)


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


_LINK_UA = "Mozilla/5.0 (compatible; app1-shopping/1.0)"
_LINK_TIMEOUT_S = 6.0


class RealSearchApi:
    def __init__(self, api_key: str, *, timeout: float = 60.0) -> None:
        self._api_key = api_key
        self._timeout = timeout

    def search(self, render_url: str, crop: tuple[float, float, float, float]) -> SearchResult:
        import httpx

        params = {
            "engine": "google_lens",
            "url": render_url,
            "crop": _crop_param(crop),
            "search_type": "all",
            "country": "ca",
            "hl": "en",
            "link": "resolved",
            "api_key": self._api_key,
        }
        try:
            resp = httpx.get(_ENDPOINT, params=params, timeout=self._timeout)
            resp.raise_for_status()
            return _parse(resp.json())
        except httpx.HTTPError as exc:
            raise SearchApiError(f"{type(exc).__name__}: {exc}") from exc

    def check_link(self, url: str) -> bool:
        import httpx

        try:
            with httpx.Client(
                headers={"User-Agent": _LINK_UA}, follow_redirects=True, timeout=_LINK_TIMEOUT_S
            ) as h:
                return h.get(url).status_code == 200
        except httpx.HTTPError:
            return False

    def fetch_thumbnail(self, url: str) -> str | None:
        import base64
        import io

        import httpx
        from PIL import Image

        try:
            with httpx.Client(
                headers={"User-Agent": _LINK_UA}, follow_redirects=True, timeout=8.0
            ) as h:
                resp = h.get(url)
            if resp.status_code != 200 or len(resp.content) < 200:
                return None
            im = Image.open(io.BytesIO(resp.content)).convert("RGB")
            im.thumbnail((320, 320))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=80)
            return base64.b64encode(buf.getvalue()).decode()
        except Exception:  # noqa: BLE001 — a bad thumbnail just means "judge without it"
            return None


class FakeSearchApi:
    """Deterministic two-item-shaped result for `docker compose up` and
    integration tests (`SHOPPING_BACKEND=fake`). Makes no network calls at all —
    `check_link` and `fetch_thumbnail` are as fake as `search`, so a fake-backend
    pipeline run never touches the internet."""

    def search(self, render_url: str, crop: tuple[float, float, float, float]) -> SearchResult:
        return SearchResult(
            matches=[
                RawMatch(
                    link="https://www.walmart.ca/en/ip/fake-match-a",
                    title="Fake matching product A",
                    price=70.00,
                    thumbnail=None,
                ),
                RawMatch(
                    link="https://www.amazon.ca/dp/fakematchb",
                    title="Fake matching product B",
                    price=74.00,
                    thumbnail=None,
                ),
            ]
        )

    def check_link(self, url: str) -> bool:
        return True

    def fetch_thumbnail(self, url: str) -> str | None:
        return None
