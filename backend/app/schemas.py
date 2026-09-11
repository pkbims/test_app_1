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
    thumbnail_url: Optional[str] = Field(
        None,
        description="Signed read URL for the room's latest done render's after-image, "
                    "or its original photo if no render has finished yet. Null if the "
                    "room has no photo. Same short-lived /files/... scheme as Photo.url "
                    "and Render.after_url — never cached by key, reissued on every read.",
    )


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


class RoomType(str, Enum):
    """The 12 room types from the options-round handoff (options_review/HANDOFF.md
    §7.1). Detected by the inventory vision call; the user may confirm or change it
    on the render request. The wire value is also what the prompt names as `where`."""
    living_room = "living_room"
    bedroom = "bedroom"
    kitchen = "kitchen"
    dining_room = "dining_room"
    home_office = "home_office"
    kids_room = "kids_room"
    nursery = "nursery"
    bathroom = "bathroom"
    hallway = "hallway"
    studio = "studio"
    workshop = "workshop"
    server_room = "server_room"


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
    room_type: Optional[RoomType] = Field(
        None, description="The vision call's best guess. Null if it could not say — "
                          "the client then asks rather than pre-selecting."
    )


# ── renders ───────────────────────────────────────────────────────────────────
class RenderStatus(str, Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class WallsOption(str, Enum):
    repaint = "repaint"
    leave = "leave"


class FurnitureOption(str, Enum):
    keep_only = "keep_only"
    add = "add"


class DecorLevel(str, Enum):
    minimal = "minimal"
    as_style = "as_style"
    plenty = "plenty"


class PaletteOption(str, Enum):
    as_style = "as_style"
    neutral = "neutral"
    warm = "warm"
    cool = "cool"
    bold = "bold"


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
    room_type: Optional[RoomType] = Field(
        None, description="The user's confirmed room type. Null means: use whatever "
                          "the inventory detected, falling back to the room's label, "
                          "falling back to the word 'room'."
    )
    walls: WallsOption = Field(
        WallsOption.leave, description="Whether the wall colour may change. Defaults "
                                       "to leaving it — the one field whose default is "
                                       "not today's behaviour (options_review/HANDOFF.md §1.1)."
    )
    furniture: FurnitureOption = Field(
        FurnitureOption.keep_only, description="Whether new furniture may be introduced."
    )
    add_furniture: List[str] = Field(
        default_factory=list, max_length=8,
        description="Furniture-type ids to add, from the list for the room's `room_type` "
                    "(options_review/HANDOFF.md §7.2). Only read when furniture=='add'. "
                    "The backend validates ids against that room type's list (422 if unknown)."
    )
    decor: DecorLevel = Field(DecorLevel.as_style, description="How much decor to add.")
    plants: bool = Field(False, description="Add a few plants.")
    palette: PaletteOption = Field(
        PaletteOption.as_style, description="Colour family override. 'as_style' leaves "
                                            "the chosen style's own palette line as-is."
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
    room_type: Optional[RoomType] = Field(
        None, description="What was actually used for this render (request value, else "
                          "detected, else null) — echoed so history is self-describing."
    )
    walls: WallsOption = WallsOption.leave
    furniture: FurnitureOption = FurnitureOption.keep_only
    add_furniture: List[str] = Field(default_factory=list)
    decor: DecorLevel = DecorLevel.as_style
    plants: bool = False
    palette: PaletteOption = PaletteOption.as_style


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
