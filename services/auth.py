import secrets
from datetime import datetime, timedelta, timezone
from db_models import db, User, MagicLinkToken
from services.email import send_magic_link


def _get_settings():
    from flask import current_app
    return current_app.extensions["settings"]


def _utcnow():
    # Use naive UTC for SQLite compatibility
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AuthError(Exception):
    pass


class TokenExpiredError(AuthError):
    pass


class TokenUsedError(AuthError):
    pass


class TokenNotFoundError(AuthError):
    pass


def request_login(email: str) -> None:
    """
    Find or create user, generate magic link token, send email.
    """
    email = email.lower().strip()

    # find or create user
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email)
        db.session.add(user)
        db.session.commit()

    # generate token (secure random, 32 bytes = 43 chars base64)
    token = secrets.token_urlsafe(32)
    expiry_minutes = _get_settings().magic_link_expiry_minutes
    expires_at = _utcnow() + timedelta(minutes=expiry_minutes)

    magic_token = MagicLinkToken(user_id=user.id, token=token, expires_at=expires_at)
    db.session.add(magic_token)
    db.session.commit()

    # send email
    send_magic_link(email, token)


def verify_token(token: str) -> User:
    """
    Verify magic link token. Returns User if valid.
    Raises AuthError subclass if invalid.
    """
    magic_token = MagicLinkToken.query.filter_by(token=token).first()

    if not magic_token:
        raise TokenNotFoundError("Invalid login link")

    if magic_token.used_at is not None:
        raise TokenUsedError("This login link has already been used")

    if _utcnow() > magic_token.expires_at:
        raise TokenExpiredError("This login link has expired")

    # mark as used
    magic_token.used_at = _utcnow()
    db.session.commit()

    return magic_token.user
