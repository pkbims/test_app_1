"""The contract. Both halves of the system build against these shapes.

Neither the iOS agent nor the backend agent may change this file without agreement —
it is the only thing they share, and a unilateral edit silently forks the system.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ── auth ──────────────────────────────────────────────────────────────────────
class AppleSignIn(BaseModel):
    identity_token: str = Field(..., description="The identity token from Sign in with Apple.")


class RefreshRequest(BaseModel):
    refresh_token: str


class Tokens(BaseModel):
    access_token: str = Field(..., description="Short-lived. Hold in memory only.")
    refresh_token: Optional[str] = Field(None, description="30 days. Store in the Keychain.")
    expires_in: int = Field(..., description="Seconds until the access token expires.")


class Me(BaseModel):
    user_id: str
    credits_left: int = Field(..., description="Rooms remaining. One free room at signup.")


# ── rooms and photos ──────────────────────────────────────────────────────────
class RoomCreate(BaseModel):
    label: Optional[str] = Field(None, max_length=80, description="e.g. 'Living room'.")


class Room(BaseModel):
    room_id: str
    label: Optional[str] = None
    created_at: datetime
    has_photo: bool
    has_inventory: bool


class Photo(BaseModel):
    photo_id: str
    room_id: str
    width: int
    height: int
    url: str = Field(..., description="Short-lived read URL for the client.")


# ── inventory: the mechanism the product depends on ───────────────────────────
class ItemKind(str, Enum):
    architecture = "architecture"
    object = "object"


class InventoryItem(BaseModel):
    """One thing found in the room.

    `name` is shown to the user next to its letter. `description` is never shown —
    it goes verbatim into the image prompt, which is why it must be positional and
    specific ("deep rectangular wall alcove centred above and to the right of the
    fireplace"), not a bare noun.
    """
    id: str = Field(..., pattern=r"^[A-Z]{1,2}$", description="A, B, C … shown to the user.")
    kind: ItemKind
    name: str = Field(..., description="Short label for the confirm screen.")
    description: str = Field(..., description="Positional description for the image model.")
    removable: bool = Field(
        ..., description="Architecture is never removable. Objects are."
    )


class Inventory(BaseModel):
    room_id: str
    items: List[InventoryItem]
    created_at: datetime


# ── renders ───────────────────────────────────────────────────────────────────
class RenderStatus(str, Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class RenderCreate(BaseModel):
    style: str = Field(..., description="Preset style id, e.g. 'warm-minimal'.")
    prompt: Optional[str] = Field(
        None, max_length=280, description="Optional free text. Cannot override preservation."
    )
    remove_ids: List[str] = Field(
        default_factory=list,
        description="Inventory ids the user tapped to remove. Everything else is kept.",
    )
    idempotency_key: str = Field(
        ...,
        description="Client-generated. A retry with the same key returns the existing "
                    "render rather than spending a second credit.",
    )


class Render(BaseModel):
    render_id: str
    room_id: str
    status: RenderStatus
    style: str
    remove_ids: List[str]
    before_url: Optional[str] = None
    after_url: Optional[str] = None
    preservation_rate: Optional[float] = Field(
        None, ge=0, le=1,
        description="Share of architectural inventory items still present in the result, "
                    "judged by a vision call. Not a pixel comparison — output is never "
                    "aligned with input.",
    )
    missing_items: Optional[List[str]] = Field(
        None, description="Inventory ids the check could not find in the result."
    )
    error_code: Optional[str] = None
    created_at: datetime
    credits_left: Optional[int] = None


# ── errors and health ─────────────────────────────────────────────────────────
class ErrorCode(str, Enum):
    apple_token_invalid = "apple_token_invalid"
    token_expired = "token_expired"
    no_credits = "no_credits"
    rate_limited = "rate_limited"
    photo_too_large = "photo_too_large"
    photo_unsupported = "photo_unsupported"
    no_photos = "no_photos"
    no_inventory = "no_inventory"
    inventory_failed = "inventory_failed"
    render_failed = "render_failed"
    not_found = "not_found"  # 404: unknown id, or a resource that is not yours (no existence leak)


class Error(BaseModel):
    code: ErrorCode
    message: str = Field(..., description="Shown to the user verbatim. Keep it plain.")


class HealthState(str, Enum):
    ok = "ok"
    degraded = "degraded"
    down = "down"


class HealthCheck(BaseModel):
    name: str
    state: HealthState
    detail: Optional[str] = None


class Health(BaseModel):
    state: HealthState = Field(
        ..., description="down blocks deploys. degraded pages someone. ok does nothing."
    )
    checks: List[HealthCheck]
