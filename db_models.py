from datetime import datetime, timedelta, timezone
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
