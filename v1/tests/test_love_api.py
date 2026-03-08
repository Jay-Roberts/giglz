"""Tests for the love track API endpoints.

Tests per-user love/unlove functionality via the API.
"""

import pytest

from app import app
from extensions import db as flask_db
from db import Database
from models import Artist, Show


@pytest.fixture
def test_app(tmp_path):
    """Configure the app with a temp SQLite database."""
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_path}/test.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["TESTING"] = True

    with app.app_context():
        flask_db.create_all()
        yield app
        flask_db.drop_all()


@pytest.fixture
def client(test_app):
    """Flask test client (not logged in)."""
    return test_app.test_client()


@pytest.fixture
def logged_in_client(test_app):
    """Flask test client logged in as a user."""
    with test_app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = "test-user-123"
            session["user_name"] = "Test User"
        yield client


@pytest.fixture
def database(test_app) -> Database:
    """Database facade within app context."""
    return Database()


@pytest.fixture
def sample_show(test_app, database):
    """A show with some tracks."""
    show = Show(
        id="show-1",
        venue="The Earl",
        date="2026-03-15",
        created_at="2026-02-14T12:00:00Z",
        artists=[Artist(name="Blondie", spotify_id="abc123")],
        track_uris=[
            "spotify:track:track1",
            "spotify:track:track2",
        ],
    )
    database.save_show(show)
    return show


@pytest.fixture
def two_shows_same_track(test_app, database):
    """Two shows that share a track."""
    show1 = Show(
        id="show-1",
        venue="The Earl",
        date="2026-03-15",
        created_at="2026-02-14T12:00:00Z",
        artists=[Artist(name="Blondie", spotify_id="abc123")],
        track_uris=["spotify:track:shared", "spotify:track:unique1"],
    )
    show2 = Show(
        id="show-2",
        venue="Terminal West",
        date="2026-04-20",
        created_at="2026-02-14T12:00:00Z",
        artists=[Artist(name="Blondie", spotify_id="abc456")],
        track_uris=["spotify:track:shared", "spotify:track:unique2"],
    )
    database.save_show(show1)
    database.save_show(show2)
    return show1, show2


class TestLoveTrack:
    """Tests for POST /api/love-track."""

    def test_love_track_success(self, logged_in_client, sample_show):
        """Loving a track returns show IDs containing it."""
        response = logged_in_client.post(
            "/api/love-track",
            json={
                "uri": "spotify:track:track1",
                "name": "Dreaming",
                "artist": "Blondie",
            },
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["loved"] is True
        assert data["uri"] == "spotify:track:track1"
        assert "show-1" in data["shows"]

    def test_love_track_idempotent(self, logged_in_client, sample_show):
        """Loving the same track twice is idempotent."""
        logged_in_client.post(
            "/api/love-track",
            json={"uri": "spotify:track:track1", "name": "Song", "artist": "Artist"},
        )
        response = logged_in_client.post(
            "/api/love-track",
            json={"uri": "spotify:track:track1", "name": "Song", "artist": "Artist"},
        )

        assert response.status_code == 200
        # Should still work, just doesn't double-love

    def test_love_track_returns_multiple_shows(
        self, logged_in_client, two_shows_same_track
    ):
        """Loving a shared track returns all shows containing it."""
        response = logged_in_client.post(
            "/api/love-track",
            json={"uri": "spotify:track:shared", "name": "Song", "artist": "Artist"},
        )
        data = response.get_json()
        assert len(data["shows"]) == 2
        assert "show-1" in data["shows"]
        assert "show-2" in data["shows"]

    def test_love_track_not_in_any_show(self, logged_in_client, sample_show):
        """Loving a track not in any show returns empty shows."""
        response = logged_in_client.post(
            "/api/love-track",
            json={
                "uri": "spotify:track:nonexistent",
                "name": "Song",
                "artist": "Artist",
            },
        )
        data = response.get_json()
        assert data["loved"] is True
        assert data["shows"] == []

    def test_love_track_requires_auth(self, client, sample_show):
        """Loving a track without auth returns 401."""
        response = client.post(
            "/api/love-track",
            json={"uri": "spotify:track:track1"},
        )
        assert response.status_code == 401


class TestLoveTrackValidation:
    """Validation tests for love track endpoint."""

    def test_love_track_missing_uri(self, logged_in_client):
        """Missing uri returns 400."""
        response = logged_in_client.post("/api/love-track", json={})
        assert response.status_code == 400

    def test_love_track_no_json_body(self, logged_in_client):
        """No JSON body returns 415 (Unsupported Media Type)."""
        response = logged_in_client.post("/api/love-track")
        assert response.status_code == 415


class TestUnloveTrack:
    """Tests for POST /api/unlove-track."""

    def test_unlove_track_success(self, logged_in_client, sample_show, database):
        """Unloving a track removes the love."""
        # First love it
        logged_in_client.post(
            "/api/love-track",
            json={"uri": "spotify:track:track1", "name": "Song", "artist": "Artist"},
        )

        # Then unlove
        response = logged_in_client.post(
            "/api/unlove-track",
            json={"uri": "spotify:track:track1"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["loved"] is False

        # Verify in DB
        assert database.is_track_loved("test-user-123", "spotify:track:track1") is False

    def test_unlove_track_not_loved(self, logged_in_client, sample_show):
        """Unloving a track that wasn't loved is a no-op."""
        response = logged_in_client.post(
            "/api/unlove-track",
            json={"uri": "spotify:track:track1"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["loved"] is False

    def test_unlove_track_requires_auth(self, client, sample_show):
        """Unlove without auth returns 401."""
        response = client.post(
            "/api/unlove-track",
            json={"uri": "spotify:track:track1"},
        )
        assert response.status_code == 401


class TestTrackStatus:
    """Tests for GET /api/track/<uri>/status."""

    def test_track_status_loved(self, logged_in_client, sample_show):
        """Returns loved=True for a loved track."""
        logged_in_client.post(
            "/api/love-track",
            json={"uri": "spotify:track:track1", "name": "Song", "artist": "Artist"},
        )

        response = logged_in_client.get("/api/track/spotify:track:track1/status")
        data = response.get_json()
        assert data["loved"] is True
        assert data["uri"] == "spotify:track:track1"
        assert "show-1" in data["shows"]

    def test_track_status_not_loved(self, logged_in_client, sample_show):
        """Returns loved=False for a track in a show but not loved."""
        response = logged_in_client.get("/api/track/spotify:track:track1/status")
        data = response.get_json()
        assert data["loved"] is False
        assert "show-1" in data["shows"]

    def test_track_status_not_in_any_show(self, logged_in_client, sample_show):
        """Returns loved=False and empty shows for unknown track."""
        response = logged_in_client.get("/api/track/spotify:track:nonexistent/status")
        data = response.get_json()
        assert data["loved"] is False
        assert data["shows"] == []

    def test_track_status_in_multiple_shows(
        self, logged_in_client, two_shows_same_track
    ):
        """Returns all shows containing the track."""
        response = logged_in_client.get("/api/track/spotify:track:shared/status")
        data = response.get_json()
        assert len(data["shows"]) == 2
        assert "show-1" in data["shows"]
        assert "show-2" in data["shows"]

    def test_track_status_without_auth(self, client, sample_show):
        """Track status works without auth (just shows loved=False)."""
        response = client.get("/api/track/spotify:track:track1/status")
        assert response.status_code == 200
        data = response.get_json()
        assert data["loved"] is False  # Not logged in, so can't be loved
        assert "show-1" in data["shows"]  # But still shows which shows have it
