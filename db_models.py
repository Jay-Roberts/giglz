"""
Database models for Giglz.

Core entities: User, Show, Artist, Venue, City, Track, Playlist
Join tables: ShowArtist, PlaylistShow (many-to-many)
Auth: MagicLinkToken, SpotifyToken

All IDs are UUIDs stored as strings. Timestamps are naive UTC for SQLite compatibility.
"""
from datetime import datetime, timezone
from enum import StrEnum, auto

from flask_sqlalchemy import SQLAlchemy
import uuid

db = SQLAlchemy()


def _utcnow():
    # Use naive UTC for SQLite compatibility
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(255), unique=True, nullable=False)
    display_name = db.Column(db.String(255), nullable=True)
    spotify_id = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow)

    magic_link_tokens = db.relationship("MagicLinkToken", back_populates="user")
    spotify_token = db.relationship("SpotifyToken", back_populates="user", uselist=False)
    playlists = db.relationship("Playlist", back_populates="user")
    loved_tracks = db.relationship("Track", secondary="user_track_love", back_populates="loved_by")
    show_statuses = db.relationship("UserShowStatus", back_populates="user", cascade="all, delete-orphan")


class MagicLinkToken(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("user.id"), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow)

    user = db.relationship("User", back_populates="magic_link_tokens")


class SpotifyToken(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("user.id"), nullable=False, unique=True)
    access_token = db.Column(db.String(512), nullable=False)
    refresh_token = db.Column(db.String(512), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow)

    user = db.relationship("User", back_populates="spotify_token")


class ShowSource(StrEnum):
    MANUAL = auto()
    CSV = auto()
    URL = auto()


class ImportStatus(StrEnum):
    PENDING = auto()
    SUCCESS = auto()
    FAILED = auto()
    SKIPPED = auto()


class ImportSourceType(StrEnum):
    CSV_STRUCTURED = auto()
    URL = auto()  # phase 2


class ShowStatus(StrEnum):
    """User's attendance status for a show."""
    GOING = auto()
    SKIPPING = auto()


class City(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), unique=True, nullable=False)

    venues = db.relationship("Venue", back_populates="city")


class Venue(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    city_id = db.Column(db.String(36), db.ForeignKey("city.id"), nullable=False)

    city = db.relationship("City", back_populates="venues")
    shows = db.relationship("Show", back_populates="venue")
    # Enforced at DB level — INSERT/UPDATE with duplicate name+city raises IntegrityError
    __table_args__ = (
        db.UniqueConstraint("name", "city_id", name="uq_venue_name_city"),
    )


class Artist(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    spotify_id = db.Column(db.String(255), nullable=True, unique=True)
    name = db.Column(db.String(255), nullable=False)
    image_url = db.Column(db.String(512), nullable=True)
    love_count = db.Column(db.Integer, default=0)

    tracks = db.relationship("Track", back_populates="artist")
    shows = db.relationship("Show", secondary="show_artist", back_populates="artists")


class Track(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    spotify_id = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    artist_id = db.Column(db.String(36), db.ForeignKey("artist.id"), nullable=False)
    preview_url = db.Column(db.String(512), nullable=True)

    artist = db.relationship("Artist", back_populates="tracks")
    loved_by = db.relationship("User", secondary="user_track_love", back_populates="loved_tracks")


class Show(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    date = db.Column(db.Date, nullable=False)
    venue_id = db.Column(db.String(36), db.ForeignKey("venue.id"), nullable=False)
    ticket_url = db.Column(db.String(512), nullable=True)
    source = db.Column(db.Enum(ShowSource), default=ShowSource.MANUAL)
    created_at = db.Column(db.DateTime, default=_utcnow)

    venue = db.relationship("Venue", back_populates="shows")
    artists = db.relationship("Artist", secondary="show_artist", back_populates="shows")
    playlists = db.relationship("Playlist", secondary="playlist_show", back_populates="shows")
    user_statuses = db.relationship("UserShowStatus", back_populates="show", cascade="all, delete-orphan")


class ShowArtist(db.Model):
    __tablename__ = "show_artist"
    show_id = db.Column(db.String(36), db.ForeignKey("show.id"), primary_key=True)
    artist_id = db.Column(db.String(36), db.ForeignKey("artist.id"), primary_key=True)


class Playlist(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    spotify_playlist_id = db.Column(db.String(255), nullable=True)
    is_now_scouting = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=_utcnow)

    user = db.relationship("User", back_populates="playlists")
    shows = db.relationship("Show", secondary="playlist_show", back_populates="playlists")


class PlaylistShow(db.Model):
    __tablename__ = "playlist_show"
    playlist_id = db.Column(db.String(36), db.ForeignKey("playlist.id"), primary_key=True)
    show_id = db.Column(db.String(36), db.ForeignKey("show.id"), primary_key=True)
    added_at = db.Column(db.DateTime, default=_utcnow)


class UserTrackLove(db.Model):
    """User loved a track. M2M join table."""
    __tablename__ = "user_track_love"
    user_id = db.Column(db.String(36), db.ForeignKey("user.id"), primary_key=True)
    track_id = db.Column(db.String(36), db.ForeignKey("track.id"), primary_key=True)
    loved_at = db.Column(db.DateTime, default=_utcnow)


class UserShowStatus(db.Model):
    """User's attendance status for a show."""
    __tablename__ = "user_show_status"
    user_id = db.Column(db.String(36), db.ForeignKey("user.id"), primary_key=True)
    show_id = db.Column(db.String(36), db.ForeignKey("show.id"), primary_key=True)
    status = db.Column(db.Enum(ShowStatus), nullable=False)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    user = db.relationship("User", back_populates="show_statuses")
    show = db.relationship("Show", back_populates="user_statuses")


class ImportBatch(db.Model):
    __tablename__ = "import_batch"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow)

    user = db.relationship("User")
    records = db.relationship("ImportRecord", back_populates="batch")


class ImportRecord(db.Model):
    __tablename__ = "import_record"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_id = db.Column(db.String(36), db.ForeignKey("import_batch.id"), nullable=False)
    source_type = db.Column(db.Enum(ImportSourceType), default=ImportSourceType.CSV_STRUCTURED)
    input_data = db.Column(db.JSON, nullable=False)
    status = db.Column(db.Enum(ImportStatus), default=ImportStatus.PENDING)
    error = db.Column(db.String(512), nullable=True)
    show_id = db.Column(db.String(36), db.ForeignKey("show.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow)

    batch = db.relationship("ImportBatch", back_populates="records")
    show = db.relationship("Show")
