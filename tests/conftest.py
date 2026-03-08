"""
Test fixtures for auth tests.
"""

import pytest
from datetime import datetime, timedelta, timezone

from app import create_app
from db_models import db as _db, User, MagicLinkToken


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture
def app():
    """Create app with test config."""
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "DEV_MODE": True,
    })

    with app.app_context():
        yield app
        _db.drop_all()


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def db(app):
    """Database session."""
    with app.app_context():
        yield _db


@pytest.fixture
def create_user(app):
    """Factory to create a user."""

    def _create(email="test@example.com"):
        with app.app_context():
            user = User(email=email)
            _db.session.add(user)
            _db.session.commit()
            return user.id, user.email

    return _create


@pytest.fixture
def create_token(app):
    """Factory to create magic link tokens."""

    def _create(user_id, *, expired=False, used=False):
        with app.app_context():
            import secrets

            token_str = secrets.token_urlsafe(32)

            if expired:
                expires_at = _utcnow() - timedelta(minutes=1)
            else:
                expires_at = _utcnow() + timedelta(minutes=15)

            token = MagicLinkToken(
                user_id=user_id,
                token=token_str,
                expires_at=expires_at,
                used_at=_utcnow() if used else None,
            )
            _db.session.add(token)
            _db.session.commit()
            return token_str

    return _create
