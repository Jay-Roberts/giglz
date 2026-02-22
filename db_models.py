"""SQLAlchemy table definitions."""

from sqlalchemy.orm import Mapped, MappedAsDataclass, mapped_column

from extensions import db


class Show(MappedAsDataclass, db.Model):
    """Shows table - one row per artist (denormalized).

    A show with 3 artists = 3 rows with the same show_id.
    Use GROUP BY or DISTINCT when querying for unique shows.
    """

    __tablename__ = "shows"

    # init=False excludes from constructor (auto-generated)
    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    show_id: Mapped[str] = mapped_column(index=True)
    venue: Mapped[str]
    date: Mapped[str]
    playlist_name: Mapped[str]
    playlist_id: Mapped[str]  # Spotify playlist ID
    created_at: Mapped[str]
    artist_name: Mapped[str]
    # Optional fields last (they have defaults)
    ticket_url: Mapped[str | None] = mapped_column(default=None)
    spotify_id: Mapped[str | None] = mapped_column(default=None)


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
    """URL import tracking."""

    __tablename__ = "imported_urls"

    url: Mapped[str] = mapped_column(primary_key=True)
    status: Mapped[str]  # SUCCESS, FAILED, SKIPPED
    attempted_at: Mapped[str]
    # Optional fields last
    show_id: Mapped[str | None] = mapped_column(default=None)
    artist_count: Mapped[int] = mapped_column(default=0)
    track_count: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None] = mapped_column(default=None)
