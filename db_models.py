"""
Database models for Giglz.

Core entities: User, Show, Artist, Venue, City, Track
Join tables: ShowArtist (many-to-many)
Auth: MagicLinkToken

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


class MagicLinkToken(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("user.id"), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow)

    user = db.relationship("User", backref="magic_link_tokens")


class ShowSource(enum.Enum):
    MANUAL = "manual"
    CSV = "csv"
    URL = "url"


class City(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), unique=True, nullable=False)

    venues = db.relationship("Venue", backref="city")


class Venue(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    city_id = db.Column(db.String(36), db.ForeignKey("city.id"), nullable=False)

    shows = db.relationship("Show", backref="venue")
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

    tracks = db.relationship("Track", backref="artist")


class Track(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    spotify_id = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    artist_id = db.Column(db.String(36), db.ForeignKey("artist.id"), nullable=False)
    preview_url = db.Column(db.String(512), nullable=True)


class Show(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    date = db.Column(db.Date, nullable=False)
    venue_id = db.Column(db.String(36), db.ForeignKey("venue.id"), nullable=False)
    ticket_url = db.Column(db.String(512), nullable=True)
    source = db.Column(db.Enum(ShowSource), default=ShowSource.MANUAL)
    created_at = db.Column(db.DateTime, default=_utcnow)

    artists = db.relationship("Artist", secondary="show_artist", backref="shows")


class ShowArtist(db.Model):
    __tablename__ = "show_artist"
    show_id = db.Column(db.String(36), db.ForeignKey("show.id"), primary_key=True)
    artist_id = db.Column(db.String(36), db.ForeignKey("artist.id"), primary_key=True)
