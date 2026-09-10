"""Route signatures for app_1. Bodies are unimplemented on purpose.

This file exists to generate `contract/openapi.json`. The backend agent fills the
bodies in; the iOS agent codes against the generated spec. Neither changes the
shapes without agreement.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, File, Path, Response, UploadFile, status
from fastapi.responses import JSONResponse

from . import context, errors, health as health_mod, logs, ratelimit, runtime, tracking
from . import metrics as metrics_mod
from .auth import service as auth_service
from .files_route import router as files_router
from .inventory import service as inventory_service
from .middleware import RequestMiddleware
from .render import service as render_service
from .render.service import RenderUrls
from .rooms import service as rooms_service
from .schemas import (
    AppleSignIn, Error, Health, Inventory, Me, Photo, RefreshRequest,
    Render, RenderCreate, Room, RoomCreate, Tokens,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Opens the pool, runs pending migrations, wires logging and the DB-backed
    # metrics collector — all before the first request.
    rt = runtime.start()
    logs.configure(rt.settings.log_level)
    tracking.configure(rt.settings.sentry_dsn, rt.settings.app_env)
    metrics_mod.install(rt.pool)
    try:
        yield
    finally:
        runtime.stop()


app = FastAPI(
    title="app_1 API",
    version="0.1.0",
    description=(
        "Restyles a photo of a room without changing the room.\n\n"
        "The mechanism is two calls: a vision pass inventories what is in the photo, "
        "and a generate pass names those items verbatim so the model knows what to "
        "preserve. There is no mask — masking was tested and does not preserve "
        "anything. See PRD.md."
    ),
    lifespan=lifespan,
)

E = {400: {"model": Error}, 401: {"model": Error}, 402: {"model": Error},
     413: {"model": Error}, 429: {"model": Error}, 500: {"model": Error}}

# Cross-cutting wiring (not part of the contract): the ApiError -> Error handler,
# and one middleware that stamps a request id and enforces auth on /v1/* (except
# /v1/auth/*). See ORCH-QUESTIONS Q3.
errors.install(app)
app.include_router(files_router)
app.add_middleware(
    RequestMiddleware,
    secret_provider=lambda: runtime.get().settings.jwt_secret,
)


def _todo():
    raise NotImplementedError("contract only — the backend agent implements this")


def _render_urls() -> RenderUrls:
    s = runtime.get().settings
    return RenderUrls(s.public_base_url, s.file_url_secret, s.file_url_ttl_s)


# ── auth ──────────────────────────────────────────────────────────────────────
@app.post("/v1/auth/apple", response_model=Tokens, responses=E, tags=["auth"],
          summary="Exchange an Apple identity token for our tokens")
def auth_apple(body: AppleSignIn) -> Tokens:
    """Verifies the token against Apple's keys. Creates the user and grants one free
    room on first sight. Rate limit 10/hr per IP."""
    rt = runtime.get()
    ctx = context.current()
    ratelimit.enforce(rt.rate_limiter, "auth_apple", ctx.client_ip)
    with rt.pool.connection() as conn:
        issued = auth_service.authenticate(
            conn,
            body.identity_token,
            rt.apple_verifier,
            secret=rt.settings.jwt_secret,
            access_ttl_s=rt.settings.access_ttl_s,
            refresh_ttl_s=rt.settings.refresh_ttl_s,
            signup_free_credits=rt.settings.signup_free_credits,
        )
    return issued.tokens


@app.post("/v1/auth/refresh", response_model=Tokens, responses=E, tags=["auth"],
          summary="Trade a refresh token for a new access token")
def auth_refresh(body: RefreshRequest) -> Tokens:
    rt = runtime.get()
    ctx = context.current()
    ratelimit.enforce(rt.rate_limiter, "auth_refresh", ctx.client_ip)
    with rt.pool.connection() as conn:
        return auth_service.refresh(
            conn,
            body.refresh_token,
            secret=rt.settings.jwt_secret,
            access_ttl_s=rt.settings.access_ttl_s,
            refresh_ttl_s=rt.settings.refresh_ttl_s,
        )


@app.get("/v1/me", response_model=Me, responses=E, tags=["auth"],
         summary="Current user and credits remaining")
def me() -> Me:
    rt = runtime.get()
    ctx = context.current()
    ratelimit.enforce(rt.rate_limiter, "me", ctx.user_id)
    with rt.pool.connection() as conn:
        return auth_service.current_user(conn, ctx.user_id)


# ── rooms ─────────────────────────────────────────────────────────────────────
@app.post("/v1/rooms", response_model=Room, status_code=status.HTTP_201_CREATED,
          responses=E, tags=["rooms"], summary="Create a room")
def create_room(body: RoomCreate) -> Room:
    rt = runtime.get()
    ctx = context.current()
    ratelimit.enforce(rt.rate_limiter, "rooms", ctx.user_id)
    with rt.pool.connection() as conn:
        return rooms_service.create_room(conn, ctx.user_id, body.label)


@app.post("/v1/rooms/{room_id}/photos", response_model=Photo, responses=E,
          tags=["rooms"], summary="Upload the room photo")
def upload_photo(room_id: str = Path(...), file: UploadFile = File(...)) -> Photo:
    """One photo per room; we do not ask for more. Max 12 MB.

    HEIC is what iPhones produce by default and the image API does not accept it,
    so the client converts to JPEG before upload. The server rejects anything that
    is not JPEG or PNG with `photo_unsupported`."""
    rt = runtime.get()
    ctx = context.current()
    ratelimit.enforce(rt.rate_limiter, "photos", ctx.user_id)
    if file.size is not None and file.size > rt.settings.max_photo_bytes:
        raise errors.ApiError(
            errors.ErrorCode.photo_too_large, "That photo is over 12 MB. Try a smaller one."
        )
    data = file.file.read()
    with rt.pool.connection() as conn:
        return rooms_service.upload_photo(
            conn,
            rt.storage,
            room_id=room_id,
            user_id=ctx.user_id,
            data=data,
            max_bytes=rt.settings.max_photo_bytes,
            public_base_url=rt.settings.public_base_url,
            url_secret=rt.settings.file_url_secret,
            url_ttl_s=rt.settings.file_url_ttl_s,
        )


@app.delete("/v1/rooms/{room_id}", status_code=status.HTTP_204_NO_CONTENT,
            responses=E, tags=["rooms"], summary="Delete a room and its photos")
def delete_room(room_id: str = Path(...)) -> Response:
    rt = runtime.get()
    ctx = context.current()
    ratelimit.enforce(rt.rate_limiter, "rooms", ctx.user_id)
    with rt.pool.connection() as conn:
        rooms_service.delete_room(conn, rt.storage, room_id, ctx.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── inventory ─────────────────────────────────────────────────────────────────
@app.post("/v1/rooms/{room_id}/inventory", response_model=Inventory, responses=E,
          tags=["inventory"], summary="Find what is in the room")
def create_inventory(room_id: str = Path(...)) -> Inventory:
    """A vision call lists the room's fixed architecture and its moveable objects,
    labelled A, B, C. Architecture is always listed and never removable — it is what
    the generate step must preserve. Takes a few seconds; called once per room."""
    rt = runtime.get()
    ctx = context.current()
    ratelimit.enforce(rt.rate_limiter, "inventory", ctx.user_id)
    with rt.pool.connection() as conn:
        return inventory_service.create_inventory(
            conn, rt.storage, rt.vision, room_id, ctx.user_id
        )


@app.get("/v1/rooms/{room_id}/inventory", response_model=Inventory, responses=E,
         tags=["inventory"], summary="Read the inventory")
def get_inventory(room_id: str = Path(...)) -> Inventory:
    rt = runtime.get()
    ctx = context.current()
    with rt.pool.connection() as conn:
        return inventory_service.get_inventory(conn, room_id, ctx.user_id)


# ── renders ───────────────────────────────────────────────────────────────────
@app.post("/v1/rooms/{room_id}/renders", response_model=Render,
          status_code=status.HTTP_202_ACCEPTED, responses=E, tags=["renders"],
          summary="Restyle the room")
def create_render(body: RenderCreate, room_id: str = Path(...)) -> Render:
    """Queues a render. The prompt is built from the inventory: architecture under
    "must remain exactly where they are", kept objects under "keep in the same
    positions", and `remove_ids` under "remove entirely".

    Spends one credit. Returns immediately with status `queued`; the client polls
    `GET /v1/renders/{id}` every 2 seconds. A failed render refunds its credit."""
    rt = runtime.get()
    ctx = context.current()
    ratelimit.enforce(rt.rate_limiter, "render_create", ctx.user_id)
    with rt.pool.connection() as conn:
        return render_service.create_render(
            conn, room_id=room_id, user_id=ctx.user_id, body=body, urls=_render_urls(),
            request_id=ctx.request_id,
        )


@app.get("/v1/renders/{render_id}", response_model=Render, responses=E,
         tags=["renders"], summary="Poll a render")
def get_render(render_id: str = Path(...)) -> Render:
    rt = runtime.get()
    ctx = context.current()
    ratelimit.enforce(rt.rate_limiter, "render_poll", ctx.user_id)
    with rt.pool.connection() as conn:
        return render_service.get_render(conn, render_id, ctx.user_id, urls=_render_urls())


@app.get("/v1/rooms/{room_id}/renders", response_model=List[Render], responses=E,
         tags=["renders"], summary="Renders for a room")
def list_renders(room_id: str = Path(...)) -> List[Render]:
    rt = runtime.get()
    ctx = context.current()
    ratelimit.enforce(rt.rate_limiter, "render_list", ctx.user_id)
    with rt.pool.connection() as conn:
        return render_service.list_renders(conn, room_id, ctx.user_id, urls=_render_urls())


# ── operations ────────────────────────────────────────────────────────────────
@app.get("/health", response_model=Health, tags=["ops"],
         summary="Liveness with three states")
def health() -> Health:
    """`down` blocks deploys, `degraded` pages someone, `ok` does nothing. Checks the
    database, photo storage, the queue table, worker heartbeat and queue depth."""
    rt = runtime.get()
    report = health_mod.build_health(
        pool=rt.pool,
        storage=rt.storage,
        queue_depth_threshold=rt.settings.queue_depth_degraded,
        heartbeat_timeout_s=rt.settings.worker_heartbeat_timeout_s,
    )
    return JSONResponse(
        status_code=health_mod.http_status_for(report.state),
        content=report.model_dump(mode="json"),
    )


@app.get("/metrics", tags=["ops"], summary="Prometheus metrics",
         response_class=Response)
def metrics() -> Response:
    """Leads with preservation rate (mean and 5th percentile) and inventory failure
    rate — together they say whether the promise is holding."""
    body, content_type = metrics_mod.render()
    return Response(content=body, media_type=content_type)
