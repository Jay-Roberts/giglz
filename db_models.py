"""SQLAlchemy table definitions."""

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, MappedAsDataclass, mapped_column

from extensions import db


class Playlist(MappedAsDataclass, db.Model):
    """A user-created collection of shows.

    Syncs to a Spotify playlist on the host's account.
    All playlists are visible to all users.

    Attributes:
        id: UUID primary key.
        name: Display name (e.g. "all the giglz").
        owner_user_id: Spotify user ID of creator.
        created_at: ISO timestamp.
        spotify_playlist_id: Spotify playlist ID, nullable until first sync.
    """

    __tablename__ = "playlists"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    owner_user_id: Mapped[str]
    created_at: Mapped[str]
    spotify_playlist_id: Mapped[str | None] = mapped_column(default=None)


class Show(MappedAsDataclass, db.Model):
    """A concert show at a venue on a date.

    Artists are stored separately in ShowArtist (normalized).
    Shows can belong to multiple playlists via PlaylistShow.

    Attributes:
        id: UUID primary key.
        venue: Venue name.
        date: Show date in YYYY-MM-DD format.
        created_at: ISO timestamp when imported.
        ticket_url: Optional link to ticket page.
    """

    __tablename__ = "shows"

    id: Mapped[str] = mapped_column(primary_key=True)
    venue: Mapped[str]
    date: Mapped[str]
    created_at: Mapped[str]
    ticket_url: Mapped[str | None] = mapped_column(default=None)


class ShowArtist(MappedAsDataclass, db.Model):
    """An artist performing at a show.

    Normalized from the old denormalized Show table.
    Position determines display order (0 = headliner).

    Attributes:
        id: Auto-increment primary key.
        show_id: Foreign key to shows.id.
        artist_name: Artist name as extracted from source.
        position: Display order, 0 is headliner.
        spotify_id: Spotify artist ID, nullable if not found.
    """

    __tablename__ = "show_artists"

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    show_id: Mapped[str] = mapped_column(ForeignKey("shows.id"), index=True)
    artist_name: Mapped[str]
    position: Mapped[int]
    spotify_id: Mapped[str | None] = mapped_column(default=None)


class PlaylistShow(MappedAsDataclass, db.Model):
    """Links shows to playlists (many-to-many).

    Tracks who added the show and when, for audit purposes.

    Attributes:
        playlist_id: Foreign key to playlists.id.
        show_id: Foreign key to shows.id.
        added_at: ISO timestamp when linked.
        added_by_user_id: Spotify user ID who added this show.
    """

    __tablename__ = "playlist_shows"

    playlist_id: Mapped[str] = mapped_column(
        ForeignKey("playlists.id"), primary_key=True
    )
    show_id: Mapped[str] = mapped_column(ForeignKey("shows.id"), primary_key=True)
    added_at: Mapped[str]
    added_by_user_id: Mapped[str]


class ShowTrack(MappedAsDataclass, db.Model):
    """Tracks per show - normalized for indexed lookups."""

    __tablename__ = "show_tracks"

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    show_id: Mapped[str] = mapped_column(index=True)
    track_uri: Mapped[str] = mapped_column(index=True)


class UserLovedTrack(MappedAsDataclass, db.Model):
    """Loved tracks belong to users, not shows."""

    __tablename__ = "user_loved_tracks"

    user_id: Mapped[str] = mapped_column(primary_key=True)
    track_uri: Mapped[str] = mapped_column(primary_key=True)
    track_name: Mapped[str]
    artist_name: Mapped[str]
    loved_at: Mapped[str]


class ImportedUrl(MappedAsDataclass, db.Model):
    """URL import tracking for deduplication."""

    __tablename__ = "imported_urls"

    url: Mapped[str] = mapped_column(primary_key=True)
    status: Mapped[str]
    attempted_at: Mapped[str]
    show_id: Mapped[str | None] = mapped_column(default=None)
    artist_count: Mapped[int] = mapped_column(default=0)
    track_count: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None] = mapped_column(default=None)
