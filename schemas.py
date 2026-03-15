# schemas.py
"""Pydantic models for request/response contracts."""
from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, EmailStr, field_validator, Field


# =============================================================================
# AUTH
# =============================================================================

class LoginRequest(BaseModel):
    """POST /auth/login form data."""
    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


# =============================================================================
# SHOWS
# =============================================================================

class AddShowRequest(BaseModel):
    """POST /shows/add form data."""

    artists: str = Field(min_length=1)
    date: date
    venue: str = Field(min_length=1)
    city: str = Field(min_length=1)
    ticket_url: str | None = None

    @classmethod
    def from_form(cls, form) -> "AddShowRequest":
        """Create from Flask request.form MultiDict."""
        return cls(
            artists=form.get("artists", ""),
            date=form.get("date", ""),  # type: ignore[arg-type]
            venue=form.get("venue", ""),
            city=form.get("city", ""),
            ticket_url=form.get("ticket_url"),
        )

    @field_validator("artists", "venue", "city", mode="before")
    @classmethod
    def strip_and_validate(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field cannot be empty")
        return stripped

    @field_validator("ticket_url", mode="before")
    @classmethod
    def empty_to_none(cls, v: str | None) -> str | None:
        if v is None or v.strip() == "":
            return None
        return v.strip()

    @property
    def artist_names(self) -> list[str]:
        """Parse comma-separated artists into list. Strips whitespace, removes empties."""
        return [a.strip() for a in self.artists.split(",") if a.strip()]


# =============================================================================
# SPOTIFY
# =============================================================================

class SpotifyTokenInfo(BaseModel):
    """Token response from Spotify OAuth."""
    access_token: str
    refresh_token: str
    expires_at: int
    expires_in: int

    @property
    def expires_at_datetime(self) -> datetime:
        # Import here to avoid shadowing module-level datetime import
        from datetime import timezone
        return datetime.fromtimestamp(self.expires_at, tz=timezone.utc).replace(tzinfo=None)


class PlaybackState(BaseModel):
    """Parsed Spotify playback data."""
    track_id: str
    track_name: str
    artist_name: str
    album_art: str | None
    is_playing: bool
    progress_ms: int
    duration_ms: int


# =============================================================================
# API RESPONSES
# =============================================================================

class TrackState(BaseModel):
    """Currently playing track info for API."""
    id: str
    name: str
    artist: str
    album_art: str | None
    progress_ms: int
    duration_ms: int
    loved: bool = False


class ShowContext(BaseModel):
    """Show context for a track."""
    show_id: str
    show_name: str


class NowPlayingResponse(BaseModel):
    """GET /api/now-playing response."""
    connected: bool
    playing: bool = False
    track: TrackState | None = None
    show_context: ShowContext | None = None


# =============================================================================
# LOVE
# =============================================================================

class LoveTrackRequest(BaseModel):
    """POST /api/love request."""
    spotify_track_id: str


class LoveTrackResponse(BaseModel):
    """POST /api/love response."""
    loved: bool
    spotify_track_id: str


# =============================================================================
# SHOW STATUS
# =============================================================================

class SetShowStatusRequest(BaseModel):
    """POST /api/shows/{id}/status request."""
    status: Literal["going", "skipping"] | None  # None = clear


class ShowStatusResponse(BaseModel):
    """POST /api/shows/{id}/status response."""
    show_id: str
    status: str | None


# =============================================================================
# SHOWS FILTERING
# =============================================================================

class ShowsFilterRequest(BaseModel):
    """Query params for /shows/ filtering."""
    status: Literal["going", "skipping"] | None = None
    date_from: date | None = None
    date_to: date | None = None
    heat_min: int = 0

    @classmethod
    def from_args(cls, args) -> "ShowsFilterRequest":
        """Parse from Flask request.args."""
        date_from = None
        date_to = None

        if args.get("date_from"):
            try:
                date_from = date.fromisoformat(args.get("date_from"))
            except ValueError:
                pass

        if args.get("date_to"):
            try:
                date_to = date.fromisoformat(args.get("date_to"))
            except ValueError:
                pass

        return cls(
            status=args.get("status") or None,
            date_from=date_from,
            date_to=date_to,
            heat_min=args.get("heat_min", 0, type=int),
        )
