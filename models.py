"""Models for requesting and persisting data."""

import enum
import hashlib
import json

from pydantic import BaseModel, model_validator


class ShowSubmission(BaseModel):
    """User-provided show metadata from the /add-show form."""

    artists: list[str]  # artist names as entered
    venue: str
    date: str
    ticket_url: str | None = None


class LovedTrack(BaseModel):
    """A track the user loved while scouting."""

    uri: str
    name: str
    artist: str


class Show(BaseModel):
    """A scouted show with Spotify data, ready for persistence.

    Created by enriching a ShowSubmission with Spotify lookup results.

    NOTE: Multi-show same day not supported (same artists, different times).
    """

    submission: ShowSubmission
    id: str = ""  # computed from natural key
    created_at: str
    # populated after Spotify lookup:
    artist_spotify_ids: list[str]  # parallel to artists list, "" if not found
    track_uris: list[str]  # all track URIs added to playlist
    playlist_id: str  # which playlist these tracks landed in
    playlist_name: str = ""  # human-readable playlist name for URL routing
    # user interactions:
    loved_tracks: list[LovedTrack] = []

    @model_validator(mode="after")
    def compute_id(self) -> "Show":
        """Generate deterministic ID from natural key.

        Uses sorted artist_spotify_ids + date to ensure:
        - Same artists + date = same ID (regardless of import order)
        - Different artist order = same ID (sorted)
        """
        if not self.id:
            # Filter out empty strings (artists not found on Spotify)
            valid_ids = [aid for aid in self.artist_spotify_ids if aid]
            if not valid_ids:
                raise ValueError("Show requires at least one valid artist_spotify_id")
            key_parts = sorted(valid_ids) + [self.submission.date]
            self.id = hashlib.sha256(json.dumps(key_parts).encode()).hexdigest()[:16]
        return self


class ImportStatus(str, enum.Enum):
    """Status of URL import."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ImportedUrl(BaseModel):
    """Record of a URL import attempt and its outcome."""

    url: str
    status: ImportStatus
    show_id: str | None
    artist_count: int = 0
    track_count: int = 0
    error: str | None
    attempted_at: str


# --- API Response Models ---


class ShowLovedCount(BaseModel):
    """Loved count update for a show."""

    id: str
    loved_count: int


class LoveTrackResponse(BaseModel):
    """Response from love/unlove endpoints."""

    loved: bool
    uri: str
    shows: list[str]  # show IDs containing this track
    shows_updated: list[ShowLovedCount]  # for JS to update cards


class TrackStatusResponse(BaseModel):
    """Response from track status endpoint."""

    uri: str
    loved: bool
    shows: list[str]  # show IDs containing this track
