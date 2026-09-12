"""The shopping pipeline (shopping_proto/HANDOFF.md §5.1): describe, refine,
search, filter, judge, pick, write — plus the grid/crop geometry connecting
describe/refine's grid-cell answers (`judge.py`) to a final crop box.

The job-runner entry point (leasing, retry/backoff, `jobs` bookkeeping) is
`worker/shopping_job.py`, not here — same split as `app/render/prompt.py` vs.
`worker/render_job.py`. This module only ever touches `renders`, `inventories`
and `shopping`, never `jobs`, so it stays a plain dependency of the worker
rather than the other way around.

Geometry: describe answers in cells of a 12×8 grid over the *whole render*.
Refine answers in cells of a 6×6 grid over a *padded crop of the coarse box*
(coarse box + one grid cell of padding on every side). `compose_box` maps the
fine answer back into the original render's own fractions — the coordinate
space `search()`'s `crop` parameter and our own saved crop both need.
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont
from psycopg.types.json import Json

from ..files import signed_url
from ..schemas import InventoryItem
from .judge import DescribedItem, JudgeCandidate, ShoppingModel
from .searchapi import RawMatch, SearchApi, SearchApiError

_log = logging.getLogger("worker.shopping")

Box = tuple[float, float, float, float]  # x0, y0, x1, y1 — fractions of a reference image

_COARSE_COLS, _COARSE_ROWS = 12, 8
_FINE_COLS, _FINE_ROWS = 6, 6
_JUDGE_THRESHOLD = 3  # open question, shopping_proto/HANDOFF.md §7.2 — revisit with batch-run data
_MAX_CANDIDATES = 12
_FINAL_CROP_PAD = 0.02

# Known Canadian/major retailers (HANDOFF §5.1 step 4, verified during research).
# A ".ca" host not on this list is still allowed unless it's one of the excluded
# platforms below — a long tail of small Canadian retailers is the point.
_KNOWN_STORES = (
    "amazon.ca", "wayfair.ca", "walmart.ca", "homedepot.ca", "bouclair.com",
    "ikea.com", "structube.com", "costco.ca", "canadiantire.ca", "westelm.ca",
    "cb2.ca", "article.com", "simons.ca", "jysk.ca", "thebrick.com", "rona.ca",
    "potterybarn.ca", "crateandbarrel.ca", "desenio.ca", "posterstore.ca",
    "michaels.com", "linenchest.com", "urbanbarn.com", "eq3.com",
)
_EXCLUDED_HOST_SUBSTRINGS = ("google.", "pinterest", "facebook", "instagram", "kijiji", "ebay")
# Stores that serve a bot wall to any automated request (D3) — still shown,
# marked verified=false, never actually link-checked.
_UNVERIFIABLE_STORES = (
    "wayfair.ca", "homedepot.ca", "simons.ca", "westelm.ca", "potterybarn.ca",
    "crateandbarrel.ca",
)

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_CELL_RE = re.compile(r"^([A-Za-z])(\d+)$")


# ── geometry ─────────────────────────────────────────────────────────────────
def cells_to_box(cells: list[str] | None, cols: int, rows: int) -> Box | None:
    if not cells:
        return None
    parsed = [_CELL_RE.match(c) for c in cells]
    if not all(parsed):
        return None
    rs = [ord(m.group(1).upper()) - ord("A") for m in parsed]
    cs = [int(m.group(2)) - 1 for m in parsed]
    return (min(cs) / cols, min(rs) / rows, (max(cs) + 1) / cols, (max(rs) + 1) / rows)


def pad_box(box: Box, pad_x: float, pad_y: float) -> Box:
    x0, y0, x1, y1 = box
    return (max(0.0, x0 - pad_x), max(0.0, y0 - pad_y), min(1.0, x1 + pad_x), min(1.0, y1 + pad_y))


def compose_box(region: Box, inner: Box) -> Box:
    """`inner` is expressed as fractions of `region`; returns it mapped into
    whatever outer space `region` itself is a fraction of."""
    rx0, ry0, rx1, ry1 = region
    rw, rh = rx1 - rx0, ry1 - ry0
    ix0, iy0, ix1, iy1 = inner
    return (rx0 + ix0 * rw, ry0 + iy0 * rh, rx0 + ix1 * rw, ry0 + iy1 * rh)


def _crop_fraction(image: Image.Image, box: Box) -> Image.Image:
    w, h = image.size
    x0, y0, x1, y1 = box
    left, top = int(x0 * w), int(y0 * h)
    right, bottom = max(left + 1, int(x1 * w)), max(top + 1, int(y1 * h))
    return image.crop((left, top, min(w, right), min(h, bottom)))


def _draw_grid(image: Image.Image, cols: int, rows: int) -> Image.Image:
    g = image.copy()
    d = ImageDraw.Draw(g)
    w, h = g.size
    cw, ch = w / cols, h / rows
    font = ImageFont.load_default()
    for c in range(cols):
        for r in range(rows):
            x, y = c * cw, r * ch
            label = f"{chr(65 + r)}{c + 1}"
            d.rectangle([x, y, x + cw, y + ch], outline=(255, 0, 0), width=1)
            d.rectangle([x + 2, y + 2, x + 8 + 9 * len(label), y + 16], fill=(255, 255, 255))
            d.text((x + 4, y + 3), label, fill=(200, 0, 0), font=font)
    return g


def _jpeg_bytes(image: Image.Image, *, max_size: int = 1024, quality: int = 88) -> bytes:
    im = image.convert("RGB")
    im.thumbnail((max_size, max_size))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality)
    return buf.getvalue()


# ── item ids ─────────────────────────────────────────────────────────────────
def _slugify(name: str) -> str:
    return _SLUG_RE.sub("_", name.lower()).strip("_") or "item"


def make_item_ids(names: list[str]) -> list[str]:
    """Stable within a render (HANDOFF §4.1) — a slug of the name, disambiguated
    if two items happen to slugify the same."""
    counts: dict[str, int] = {}
    ids = []
    for name in names:
        base = _slugify(name)
        counts[base] = counts.get(base, 0) + 1
        ids.append(base if counts[base] == 1 else f"{base}_{counts[base]}")
    return ids


# ── filter (§5.1 step 4) ─────────────────────────────────────────────────────
def host_of(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _matches_any(host: str, domains: tuple[str, ...]) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def is_known_store(host: str) -> bool:
    if _matches_any(host, _KNOWN_STORES):
        return True
    if host.endswith(".ca") and not any(bad in host for bad in _EXCLUDED_HOST_SUBSTRINGS):
        return True
    return False


def is_unverifiable_store(host: str) -> bool:
    return _matches_any(host, _UNVERIFIABLE_STORES)


def filter_matches(matches: list[RawMatch]) -> list[RawMatch]:
    """Keep a match only if its host is a listed/`.ca` store, it has a price,
    and it isn't a duplicate URL. Capped at 12."""
    seen: set[str] = set()
    out: list[RawMatch] = []
    for m in matches:
        if not m.link or m.price is None or m.link in seen:
            continue
        if not is_known_store(host_of(m.link)):
            continue
        seen.add(m.link)
        out.append(m)
        if len(out) >= _MAX_CANDIDATES:
            break
    return out


# ── pick (§5.1 step 6) ───────────────────────────────────────────────────────
@dataclass(frozen=True)
class Candidate:
    store: str
    title: str
    price: float
    url: str
    thumbnail: str | None
    verified: bool


def pick_options(scored: list[tuple[Candidate, int]]) -> list[Candidate]:
    """Two cheapest survivors (score >= threshold) from different stores —
    "different" meaning a different registrable-domain base, so walmart.ca and
    walmart.com would still count as one store."""
    survivors = [c for c, score in scored if score >= _JUDGE_THRESHOLD]
    survivors.sort(key=lambda c: c.price)
    chosen: list[Candidate] = []
    seen_bases: set[str] = set()
    for c in survivors:
        base = c.store.split(".")[0]
        if base in seen_bases:
            continue
        seen_bases.add(base)
        chosen.append(c)
        if len(chosen) == 2:
            break
    return chosen


def total_from(items: list[dict]) -> float | None:
    priced = [min(opt["price"] for opt in it["options"]) for it in items if it["options"]]
    if not priced:
        return None
    return round(sum(priced), 2)


# ── the pipeline itself ──────────────────────────────────────────────────────
@dataclass(frozen=True)
class ShoppingConfig:
    max_items: int
    search_url_ttl_s: int
    public_base_url: str
    file_url_secret: str
    # TEMPORARY, dev-only (ORCH-QUESTIONS Q11, HANDOFF §7.3) — "catbox" or "".
    # See the block comment on `_upload_to_catbox` below. Default keeps every
    # existing ShoppingConfig(...) call (tests included) on today's behaviour.
    dev_public_image_host: str = ""


@dataclass(frozen=True)
class RenderInfo:
    after_key: str
    kept: list[tuple[str, str]]  # (name, description) — architecture + kept objects
    removed_names: list[str]  # user-tapped removals


@dataclass
class PipelineResult:
    items: list[dict]
    total_from: float | None
    cost_cents: float
    searchapi_calls: int
    searchapi_errors: int


def generate(storage, model: ShoppingModel, searchapi: SearchApi, render_id: str,
             info: RenderInfo, config: ShoppingConfig, log) -> PipelineResult:
    """Run the full pipeline for one render. Raises on any step that can't be
    recovered from (a describe/judge model call failing outright, storage
    errors) — the caller (`worker/shopping_job.py`) owns retry/backoff."""
    render_bytes = storage.get(f"renders/{info.after_key}")
    image = Image.open(io.BytesIO(render_bytes)).convert("RGB")

    described = model.describe(
        _jpeg_bytes(_draw_grid(image, _COARSE_COLS, _COARSE_ROWS), max_size=1600),
        info.kept,
        info.removed_names,
    )
    if described.removed_items_visible:
        log.info(
            "removed items still visible in the render",
            extra={"removed_items_visible": described.removed_items_visible},
        )

    picked_items = described.items[: config.max_items]
    ids = make_item_ids([it.name for it in picked_items])
    render_url = signed_url(
        config.public_base_url, "renders", info.after_key,
        config.file_url_secret, config.search_url_ttl_s,
    )
    if config.dev_public_image_host == "catbox":
        # TEMPORARY, dev-only — see `_upload_to_catbox` below. Uploaded once per
        # job, not once per item: every item's SearchApi call shares this URL.
        log.warning(
            "SHOPPING_DEV_IMAGE_HOST=catbox is active: uploading this render to "
            "catbox.moe, a public host outside our control, instead of using "
            "our own signed URL. Dev-only — must never run in production "
            "(HANDOFF §7.3, ORCH-QUESTIONS Q11)."
        )
        render_url = _upload_to_catbox(render_bytes)

    items_out: list[dict] = []
    searchapi_calls = 0
    searchapi_errors = 0
    judge_calls = 0

    for item_id, item in zip(ids, picked_items):
        final_box = _item_box(image, model, item)
        crop_bytes = _jpeg_bytes(_crop_fraction(image, final_box), max_size=640)
        crop_key = f"{render_id}/{item_id}.jpg"
        storage.put(f"crops/{crop_key}", crop_bytes, "image/jpeg")

        matches: list[RawMatch] = []
        for _attempt in range(2):
            searchapi_calls += 1
            try:
                result = searchapi.search(render_url, final_box)
            except SearchApiError as exc:
                searchapi_errors += 1
                log.warning("searchapi call failed: %s", exc)
                continue
            if result.error:
                searchapi_errors += 1
            if result.matches:
                matches = result.matches
                break

        candidates = _verify(filter_matches(matches), searchapi)
        options: list[dict] = []
        if candidates:
            judge_calls += 1
            scores = model.judge(
                crop_bytes, item.name, item.visual,
                [
                    JudgeCandidate(i, c.store, c.title, c.price, _thumb(c, searchapi))
                    for i, c in enumerate(candidates)
                ],
            )
            chosen = pick_options([(c, scores.get(i, 0)) for i, c in enumerate(candidates)])
            options = [
                {"store": c.store, "title": c.title, "price": c.price, "url": c.url,
                 "verified": c.verified}
                for c in chosen
            ]

        items_out.append({"item_id": item_id, "name": item.name, "crop_key": crop_key,
                           "options": options})

    cost_cents = round(0.3 + searchapi_calls * 0.4 + judge_calls * 1.0, 3)
    return PipelineResult(
        items=items_out, total_from=total_from(items_out), cost_cents=cost_cents,
        searchapi_calls=searchapi_calls, searchapi_errors=searchapi_errors,
    )


def _item_box(image: Image.Image, model: ShoppingModel, item: DescribedItem) -> Box:
    coarse_box = cells_to_box(item.cells, _COARSE_COLS, _COARSE_ROWS) or (0.0, 0.0, 1.0, 1.0)
    region = pad_box(coarse_box, 1 / _COARSE_COLS, 1 / _COARSE_ROWS)
    coarse_crop = _crop_fraction(image, region)
    fine_cells = model.refine(
        _jpeg_bytes(_draw_grid(coarse_crop, _FINE_COLS, _FINE_ROWS)), item.name, item.visual
    )
    fine_box = cells_to_box(fine_cells, _FINE_COLS, _FINE_ROWS)
    if fine_box is None:
        return coarse_box
    return pad_box(compose_box(region, fine_box), _FINAL_CROP_PAD, _FINAL_CROP_PAD)


def _verify(matches: list[RawMatch], searchapi: SearchApi) -> list[Candidate]:
    out = []
    for m in matches:
        host = host_of(m.link)
        if is_unverifiable_store(host):
            out.append(Candidate(host, m.title, m.price, m.link, m.thumbnail, verified=False))
        elif searchapi.check_link(m.link):
            out.append(Candidate(host, m.title, m.price, m.link, m.thumbnail, verified=True))
    return out


def _thumb(candidate: Candidate, searchapi: SearchApi) -> str | None:
    return searchapi.fetch_thumbnail(candidate.thumbnail) if candidate.thumbnail else None


# ═══════════════════════════════════════════════════════════════════════════
# TEMPORARY, DEV-ONLY — ORCH-QUESTIONS Q11, HANDOFF §7.3.
#
# A laptop's PUBLIC_BASE_URL is not reachable from the internet, so SearchApi
# can never fetch the render and every local run returns zero prices — the
# gap HANDOFF §7.3 named and deferred. This uploads the render, once per job,
# to catbox.moe (a public anonymous host we do not control) and hands
# SearchApi *that* URL instead of our own signed one, purely so a developer
# can see real prices without setting up a tunnel.
#
# MUST NEVER RUN IN PRODUCTION: no deletion guarantee on catbox's side (the
# render — a picture of someone's home — stays there indefinitely, outside
# our retention rules), no terms of service agreed with catbox for this use,
# and it breaks the TR4 promise this whole feature was already scrutinised
# against. `Settings.load()` refuses to start with this set when
# APP_ENV=production. Only reachable via `ShoppingConfig.dev_public_image_host
# == "catbox"`, itself only ever set from `SHOPPING_DEV_IMAGE_HOST` — never on
# by default (empty string).
#
# Delete this function, the `if` block in `generate()` that calls it, the
# `dev_public_image_host` field on `ShoppingConfig`, `Settings.
# shopping_dev_image_host` and its `load()`/`make_shopping_config` wiring
# together, once every developer has a tunnel (§7.3's actual fix). It should
# never outlive that.
_CATBOX_UPLOAD_URL = "https://catbox.moe/user/api.php"


def _upload_to_catbox(image_bytes: bytes) -> str:
    import httpx

    resp = httpx.post(
        _CATBOX_UPLOAD_URL,
        data={"reqtype": "fileupload"},
        files={"fileToUpload": ("render.png", image_bytes, "image/png")},
        timeout=30.0,
    )
    resp.raise_for_status()
    url = resp.text.strip()
    if not url.startswith("https://"):
        raise SearchApiError(f"catbox upload did not return a URL: {url[:200]!r}")
    return url


# ═══════════════════════════════════════════════════════════════════════════


def load_render_info(conn, render_id: str) -> RenderInfo | None:
    row = conn.execute(
        "SELECT r.after_key, r.remove_ids, i.items "
        "FROM renders r LEFT JOIN inventories i ON i.room_id = r.room_id "
        "WHERE r.id = %s",
        (render_id,),
    ).fetchone()
    if row is None or row[0] is None:
        return None
    after_key, remove_ids, raw_items = row
    items = [InventoryItem(**it) for it in (raw_items or [])]
    remove_ids = set(remove_ids or [])
    kept = [
        (it.name, it.description)
        for it in items
        if it.kind == "architecture" or it.id not in remove_ids
    ]
    removed_names = [it.name for it in items if it.kind != "architecture" and it.id in remove_ids]
    return RenderInfo(after_key=after_key, kept=kept, removed_names=removed_names)


def write_ready(conn, render_id: str, result: PipelineResult) -> None:
    import datetime

    with conn.transaction():
        conn.execute(
            "UPDATE shopping SET status = 'ready', items = %s, total_from = %s, "
            "prices_as_of = %s, cost_cents = %s, searchapi_calls = %s, "
            "searchapi_errors = %s, updated_at = now() WHERE render_id = %s",
            (
                Json(result.items),
                result.total_from,
                datetime.date.today(),
                result.cost_cents,
                result.searchapi_calls,
                result.searchapi_errors,
                render_id,
            ),
        )


def write_none(conn, render_id: str, *, error: str | None) -> None:
    with conn.transaction():
        conn.execute(
            "UPDATE shopping SET status = 'none', error = %s, updated_at = now() "
            "WHERE render_id = %s",
            (error, render_id),
        )
