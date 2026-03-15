"""
Database models for Giglz.

Core entities: User, Show, Artist, Venue, City, Track, Playlist
Join tables: ShowArtist, PlaylistShow (many-to-many)
Auth: MagicLinkToken, SpotifyToken

All IDs are UUIDs stored as strings. Timestamps are naive UTC for SQLite compatibility.
"""
from datetime import datetime, timezone
import enum

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


class ShowSource(enum.Enum):
    MANUAL = "manual"
    CSV = "csv"
    URL = "url"


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
