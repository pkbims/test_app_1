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

from . import health as health_mod
from . import runtime
from .schemas import (
    AppleSignIn, Error, Health, Inventory, Me, Photo, RefreshRequest,
    Render, RenderCreate, Room, RoomCreate, Tokens,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Opens the pool and runs pending migrations before the first request.
    runtime.start()
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


def _todo():
    raise NotImplementedError("contract only — the backend agent implements this")


# ── auth ──────────────────────────────────────────────────────────────────────
@app.post("/v1/auth/apple", response_model=Tokens, responses=E, tags=["auth"],
          summary="Exchange an Apple identity token for our tokens")
def auth_apple(body: AppleSignIn) -> Tokens:
    """Verifies the token against Apple's keys. Creates the user and grants one free
    room on first sight. Rate limit 10/hr per IP."""
    _todo()


@app.post("/v1/auth/refresh", response_model=Tokens, responses=E, tags=["auth"],
          summary="Trade a refresh token for a new access token")
def auth_refresh(body: RefreshRequest) -> Tokens:
    _todo()


@app.get("/v1/me", response_model=Me, responses=E, tags=["auth"],
         summary="Current user and credits remaining")
def me() -> Me:
    _todo()


# ── rooms ─────────────────────────────────────────────────────────────────────
@app.post("/v1/rooms", response_model=Room, status_code=status.HTTP_201_CREATED,
          responses=E, tags=["rooms"], summary="Create a room")
def create_room(body: RoomCreate) -> Room:
    _todo()


@app.post("/v1/rooms/{room_id}/photos", response_model=Photo, responses=E,
          tags=["rooms"], summary="Upload the room photo")
def upload_photo(room_id: str = Path(...), file: UploadFile = File(...)) -> Photo:
    """One photo per room; we do not ask for more. Max 12 MB.

    HEIC is what iPhones produce by default and the image API does not accept it,
    so the client converts to JPEG before upload. The server rejects anything that
    is not JPEG or PNG with `photo_unsupported`."""
    _todo()


@app.delete("/v1/rooms/{room_id}", status_code=status.HTTP_204_NO_CONTENT,
            responses=E, tags=["rooms"], summary="Delete a room and its photos")
def delete_room(room_id: str = Path(...)) -> Response:
    _todo()


# ── inventory ─────────────────────────────────────────────────────────────────
@app.post("/v1/rooms/{room_id}/inventory", response_model=Inventory, responses=E,
          tags=["inventory"], summary="Find what is in the room")
def create_inventory(room_id: str = Path(...)) -> Inventory:
    """A vision call lists the room's fixed architecture and its moveable objects,
    labelled A, B, C. Architecture is always listed and never removable — it is what
    the generate step must preserve. Takes a few seconds; called once per room."""
    _todo()


@app.get("/v1/rooms/{room_id}/inventory", response_model=Inventory, responses=E,
         tags=["inventory"], summary="Read the inventory")
def get_inventory(room_id: str = Path(...)) -> Inventory:
    _todo()


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
    _todo()


@app.get("/v1/renders/{render_id}", response_model=Render, responses=E,
         tags=["renders"], summary="Poll a render")
def get_render(render_id: str = Path(...)) -> Render:
    _todo()


@app.get("/v1/rooms/{room_id}/renders", response_model=List[Render], responses=E,
         tags=["renders"], summary="Renders for a room")
def list_renders(room_id: str = Path(...)) -> List[Render]:
    _todo()


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
    _todo()
