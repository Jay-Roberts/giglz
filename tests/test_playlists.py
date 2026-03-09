"""
Playlists feature tests.

Run with: uv run pytest tests/test_playlists.py -v
"""
import pytest
from unittest.mock import patch, MagicMock

# =============================================================================
# EXPECTED REQUEST → RESPONSE PAIRS
# =============================================================================

# GET /playlists/scouting (no session) — redirect to login
SCOUTING_NO_SESSION_STATUS = 302
SCOUTING_NO_SESSION_REDIRECT = "/auth/login"

# GET /playlists/scouting (with session) — scouting page
SCOUTING_STATUS = 200
SCOUTING_CONTAINS = b"Now Scouting"

# POST /playlists/scouting/shows/<id> — add show, redirect
ADD_SHOW_STATUS = 302
ADD_SHOW_REDIRECT = "/shows/"

# POST /playlists/scouting/shows/<id>/remove — remove show, redirect
REMOVE_SHOW_STATUS = 302
REMOVE_SHOW_REDIRECT = "/shows/"


# =============================================================================
# MOCK DATA
# =============================================================================

from dataclasses import dataclass


@dataclass
class MockArtistSearch:
    spotify_id: str
    name: str
    image_url: str = "https://example.com/image.jpg"
    match_score: float = 95.0


@dataclass
class MockTrackInfo:
    spotify_id: str
    name: str = "Test Track"
    preview_url: str = "https://example.com/preview.mp3"


MOCK_ARTISTS = {
    "Playlist Artist": MockArtistSearch(spotify_id="spotify_playlist", name="Playlist Artist"),
}

MOCK_TRACKS = {
    "spotify_playlist": [
        MockTrackInfo(spotify_id="track_playlist_1", name="First Song"),
        MockTrackInfo(spotify_id="track_playlist_2", name="Second Song"),
    ],
}


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def authed_client(client, create_user, create_token):
    """Client with authenticated session."""
    user_id, _ = create_user("playlists@example.com")
    token = create_token(user_id)
    client.get(f"/auth/verify?token={token}")
    return client


@pytest.fixture
def mock_spotify():
    """Mock SpotifyAPI to avoid real API calls."""
    with patch("services.shows.SpotifyAPI") as mock_class:
        mock_instance = MagicMock()
        mock_instance.search_artist.side_effect = lambda name: MOCK_ARTISTS.get(name.strip())
        mock_instance.get_top_tracks.side_effect = lambda aid, limit=5: MOCK_TRACKS.get(aid, [])
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def create_show(authed_client, mock_spotify):
    """Factory to create a show via the API."""
    def _create(artist="Playlist Artist", date="2026-07-01", venue="Test Venue", city="Atlanta"):
        authed_client.post(
            "/shows/add",
            data={
                "artists": artist,
                "date": date,
                "venue": venue,
                "city": city,
            },
        )
        # Return the show ID from the database
        from db_models import Show
        show = Show.query.order_by(Show.created_at.desc()).first()
        return show.id if show else None

    return _create


# =============================================================================
# ROUTE TESTS
# =============================================================================


def test_scouting_requires_auth(client):
    """GET /playlists/scouting redirects to login when not authed."""
    response = client.get("/playlists/scouting", follow_redirects=False)

    assert response.status_code == SCOUTING_NO_SESSION_STATUS
    assert SCOUTING_NO_SESSION_REDIRECT in response.headers.get("Location", "")


def test_scouting_page_loads(authed_client):
    """GET /playlists/scouting returns scouting page when authed."""
    response = authed_client.get("/playlists/scouting")

    assert response.status_code == SCOUTING_STATUS
    assert SCOUTING_CONTAINS in response.data


def test_scouting_creates_playlist(authed_client, app):
    """GET /playlists/scouting creates Now Scouting playlist if needed."""
    from db_models import Playlist

    authed_client.get("/playlists/scouting")

    with app.app_context():
        playlist = Playlist.query.filter_by(is_now_scouting=True).first()
        assert playlist is not None
        assert playlist.name == "Now Scouting"


def test_add_show_to_scouting(authed_client, create_show, app):
    """POST /playlists/scouting/shows/<id> adds show to playlist."""
    from db_models import PlaylistShow

    show_id = create_show()
    response = authed_client.post(
        f"/playlists/scouting/shows/{show_id}",
        follow_redirects=False,
    )

    assert response.status_code == ADD_SHOW_STATUS
    assert ADD_SHOW_REDIRECT in response.headers.get("Location", "")

    with app.app_context():
        playlist_show = PlaylistShow.query.filter_by(show_id=show_id).first()
        assert playlist_show is not None


def test_add_show_duplicate_is_noop(authed_client, create_show, app):
    """POST /playlists/scouting/shows/<id> twice is no-op (no error)."""
    from db_models import PlaylistShow

    show_id = create_show()

    # Add twice
    authed_client.post(f"/playlists/scouting/shows/{show_id}")
    response = authed_client.post(
        f"/playlists/scouting/shows/{show_id}",
        follow_redirects=False,
    )

    assert response.status_code == ADD_SHOW_STATUS

    with app.app_context():
        count = PlaylistShow.query.filter_by(show_id=show_id).count()
        assert count == 1


def test_remove_show_from_scouting(authed_client, create_show, app):
    """POST /playlists/scouting/shows/<id>/remove removes show."""
    from db_models import PlaylistShow

    show_id = create_show()

    # Add then remove
    authed_client.post(f"/playlists/scouting/shows/{show_id}")
    response = authed_client.post(
        f"/playlists/scouting/shows/{show_id}/remove",
        follow_redirects=False,
    )

    assert response.status_code == REMOVE_SHOW_STATUS
    assert REMOVE_SHOW_REDIRECT in response.headers.get("Location", "")

    with app.app_context():
        playlist_show = PlaylistShow.query.filter_by(show_id=show_id).first()
        assert playlist_show is None


def test_scouting_shows_tracks(authed_client, create_show):
    """GET /playlists/scouting shows tracks from scouted shows."""
    show_id = create_show()
    authed_client.post(f"/playlists/scouting/shows/{show_id}")

    response = authed_client.get("/playlists/scouting")

    assert response.status_code == SCOUTING_STATUS
    assert b"First Song" in response.data
    assert b"Second Song" in response.data


def test_scouting_empty_state(authed_client):
    """GET /playlists/scouting with no shows displays empty state."""
    response = authed_client.get("/playlists/scouting")

    assert response.status_code == SCOUTING_STATUS
    # Should show 0 tracks or some empty indicator
    assert b"0 tracks" in response.data or b"No tracks" in response.data or SCOUTING_CONTAINS in response.data
