"""Models for requesting and persisting data."""

import enum
import hashlib
import json

from pydantic import BaseModel, model_validator


class ShowSubmission(BaseModel):
    """User-provided show metadata from the /add-show form."""

    artists: list[str]
    venue: str
    date: str
    ticket_url: str | None = None


class LovedTrack(BaseModel):
    """A track the user loved while scouting."""

    uri: str
    name: str
    artist: str


class Artist(BaseModel):
    """An artist performing at a show."""

    name: str
    spotify_id: str | None = None


class Show(BaseModel):
    """A scouted show with Spotify data, ready for persistence.

    Created by enriching a ShowSubmission with Spotify lookup results.
    Shows can belong to multiple playlists via PlaylistShow.
    """

    id: str = ""
    venue: str
    date: str
    ticket_url: str | None = None
    created_at: str
    artists: list[Artist]
    track_uris: list[str] = []

    @model_validator(mode="after")
    def compute_id(self) -> "Show":
        """Generate deterministic ID from natural key.

        Uses sorted artist spotify_ids + date to ensure:
        - Same artists + date = same ID (regardless of import order)
        - Different artist order = same ID (sorted)
        """
        if not self.id:
            valid_ids = [a.spotify_id for a in self.artists if a.spotify_id]
            if not valid_ids:
                raise ValueError("Show requires at least one artist with spotify_id")
            key_parts = sorted(valid_ids) + [self.date]
            self.id = hashlib.sha256(json.dumps(key_parts).encode()).hexdigest()[:16]
        return self

    @classmethod
    def from_submission(
        cls,
        submission: ShowSubmission,
        artist_spotify_ids: list[str],
        track_uris: list[str],
        created_at: str,
    ) -> "Show":
        """Create a Show from a submission and Spotify lookup results."""
        artists = [
            Artist(name=name, spotify_id=sid or None)
            for name, sid in zip(submission.artists, artist_spotify_ids)
        ]
        return cls(
            venue=submission.venue,
            date=submission.date,
            ticket_url=submission.ticket_url,
            created_at=created_at,
            artists=artists,
            track_uris=track_uris,
        )


class Playlist(BaseModel):
    """A user-created collection of shows."""

    id: str
    name: str
    owner_user_id: str
    created_at: str
    spotify_playlist_id: str | None = None


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
    shows: list[str]
    shows_updated: list[ShowLovedCount]


class TrackStatusResponse(BaseModel):
    """Response from track status endpoint."""

    uri: str
    loved: bool
    shows: list[str]
