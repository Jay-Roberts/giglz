"""
Shows feature tests.

Run with: uv run pytest tests/test_shows.py -v
"""
from dataclasses import dataclass
from unittest.mock import patch, MagicMock

# =============================================================================
# EXPECTED REQUEST → RESPONSE PAIRS
# =============================================================================

# GET /shows (no session) — redirect to login
SHOWS_NO_SESSION_STATUS = 302
SHOWS_NO_SESSION_REDIRECT = "/auth/login"

# GET /shows (with session) — shows list
SHOWS_LIST_STATUS = 200
SHOWS_LIST_CONTAINS = b"Shows"

# GET /shows/add (no session) — redirect to login
ADD_FORM_NO_SESSION_STATUS = 302

# GET /shows/add (with session) — add form
ADD_FORM_STATUS = 200
ADD_FORM_CONTAINS = b"Add Show"

# POST /shows/add (success) — redirect to list
ADD_SUCCESS_STATUS = 302
ADD_SUCCESS_REDIRECT = "/shows/"

# POST /shows/add (missing artists) — error
ADD_MISSING_ARTISTS_STATUS = 400
ADD_MISSING_ARTISTS_CONTAINS = b"artist"

# POST /shows/add (missing date) — error
ADD_MISSING_DATE_STATUS = 400
ADD_MISSING_DATE_CONTAINS = b"Date"

# POST /shows/add (missing venue) — error
ADD_MISSING_VENUE_STATUS = 400
ADD_MISSING_VENUE_CONTAINS = b"Venue"

# POST /shows/add (missing city) — error
ADD_MISSING_CITY_STATUS = 400
ADD_MISSING_CITY_CONTAINS = b"City"

# POST /shows/add (invalid date) — error
ADD_INVALID_DATE_STATUS = 400
ADD_INVALID_DATE_CONTAINS = b"Invalid date"

# POST /shows/add (duplicate) — error
ADD_DUPLICATE_STATUS = 400
ADD_DUPLICATE_CONTAINS = b"already exists"


# =============================================================================
# MOCK DATA
# =============================================================================




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


# Explicit mock data — same input → same output
MOCK_ARTISTS = {
    "Test Artist": MockArtistSearch(spotify_id="spotify_test", name="Test Artist"),
    "Artist One": MockArtistSearch(spotify_id="spotify_one", name="Artist One"),
    "Artist Two": MockArtistSearch(spotify_id="spotify_two", name="Artist Two"),
    "Visible Artist": MockArtistSearch(
        spotify_id="spotify_visible", name="Visible Artist"
    ),
}

MOCK_TRACKS = {
    "spotify_test": [MockTrackInfo(spotify_id="track_test")],
    "spotify_one": [MockTrackInfo(spotify_id="track_one")],
    "spotify_two": [MockTrackInfo(spotify_id="track_two")],
    "spotify_visible": [MockTrackInfo(spotify_id="track_visible")],
}


# =============================================================================
# FIXTURES
# =============================================================================

import pytest


@pytest.fixture
def authed_client(client, create_user, create_token):
    """Client with authenticated session."""
    user_id, _ = create_user("shows@example.com")
    token = create_token(user_id)
    client.get(f"/auth/verify?token={token}")
    return client


@pytest.fixture
def mock_spotify():
    """Mock SpotifyAPI to avoid real API calls."""
    with patch("services.shows.SpotifyAPI") as mock_class:
        mock_instance = MagicMock()
        mock_instance.search_artist.side_effect = lambda name: MOCK_ARTISTS.get(
            name.strip()
        )
        mock_instance.get_top_tracks.side_effect = lambda aid, limit=5: MOCK_TRACKS.get(
            aid, []
        )
        mock_class.return_value = mock_instance
        yield mock_instance


# =============================================================================
# ROUTE TESTS
# =============================================================================


def test_shows_list_requires_auth(client):
    """GET /shows redirects to login when not authed."""
    response = client.get("/shows/", follow_redirects=False)

    assert response.status_code == SHOWS_NO_SESSION_STATUS
    assert SHOWS_NO_SESSION_REDIRECT in response.headers.get("Location", "")


def test_shows_list_loads(authed_client):
    """GET /shows returns shows list when authed."""
    response = authed_client.get("/shows/")

    assert response.status_code == SHOWS_LIST_STATUS
    assert SHOWS_LIST_CONTAINS in response.data


def test_add_form_requires_auth(client):
    """GET /shows/add redirects to login when not authed."""
    response = client.get("/shows/add", follow_redirects=False)

    assert response.status_code == ADD_FORM_NO_SESSION_STATUS


def test_add_form_loads(authed_client):
    """GET /shows/add returns form when authed."""
    response = authed_client.get("/shows/add")

    assert response.status_code == ADD_FORM_STATUS
    assert ADD_FORM_CONTAINS in response.data


def test_add_show_success(authed_client, mock_spotify):
    """POST /shows/add with valid data creates show and redirects."""
    response = authed_client.post(
        "/shows/add",
        data={
            "artists": "Test Artist",
            "date": "2026-06-15",
            "venue": "The Earl",
            "city": "Atlanta",
        },
        follow_redirects=False,
    )

    assert response.status_code == ADD_SUCCESS_STATUS
    assert ADD_SUCCESS_REDIRECT in response.headers.get("Location", "")


def test_add_show_missing_artists(authed_client, mock_spotify):
    """POST /shows/add without artists shows error."""
    response = authed_client.post(
        "/shows/add",
        data={
            "artists": "",
            "date": "2026-06-15",
            "venue": "The Earl",
            "city": "Atlanta",
        },
    )

    assert response.status_code == ADD_MISSING_ARTISTS_STATUS
    assert ADD_MISSING_ARTISTS_CONTAINS in response.data


def test_add_show_missing_date(authed_client, mock_spotify):
    """POST /shows/add without date shows error."""
    response = authed_client.post(
        "/shows/add",
        data={
            "artists": "Test Artist",
            "date": "",
            "venue": "The Earl",
            "city": "Atlanta",
        },
    )

    assert response.status_code == ADD_MISSING_DATE_STATUS
    assert ADD_MISSING_DATE_CONTAINS in response.data


def test_add_show_missing_venue(authed_client, mock_spotify):
    """POST /shows/add without venue shows error."""
    response = authed_client.post(
        "/shows/add",
        data={
            "artists": "Test Artist",
            "date": "2026-06-15",
            "venue": "",
            "city": "Atlanta",
        },
    )

    assert response.status_code == ADD_MISSING_VENUE_STATUS
    assert ADD_MISSING_VENUE_CONTAINS in response.data


def test_add_show_missing_city(authed_client, mock_spotify):
    """POST /shows/add without city shows error."""
    response = authed_client.post(
        "/shows/add",
        data={
            "artists": "Test Artist",
            "date": "2026-06-15",
            "venue": "The Earl",
            "city": "",
        },
    )

    assert response.status_code == ADD_MISSING_CITY_STATUS
    assert ADD_MISSING_CITY_CONTAINS in response.data


def test_add_show_invalid_date(authed_client, mock_spotify):
    """POST /shows/add with invalid date shows error."""
    response = authed_client.post(
        "/shows/add",
        data={
            "artists": "Test Artist",
            "date": "not-a-date",
            "venue": "The Earl",
            "city": "Atlanta",
        },
    )

    assert response.status_code == ADD_INVALID_DATE_STATUS
    assert ADD_INVALID_DATE_CONTAINS in response.data


def test_add_show_duplicate(authed_client, mock_spotify):
    """POST /shows/add with duplicate show shows error."""
    # add first show
    authed_client.post(
        "/shows/add",
        data={
            "artists": "Test Artist",
            "date": "2026-06-15",
            "venue": "The Earl",
            "city": "Atlanta",
        },
    )

    # try to add duplicate
    response = authed_client.post(
        "/shows/add",
        data={
            "artists": "Test Artist",
            "date": "2026-06-15",
            "venue": "The Earl",
            "city": "Atlanta",
        },
    )

    assert response.status_code == ADD_DUPLICATE_STATUS
    assert ADD_DUPLICATE_CONTAINS in response.data


def test_add_show_creates_entities(authed_client, app, mock_spotify):
    """POST /shows/add creates City, Venue, Artist, Tracks, Show."""
    from db_models import City, Venue, Artist, Track, Show

    authed_client.post(
        "/shows/add",
        data={
            "artists": "Test Artist",
            "date": "2026-06-15",
            "venue": "The Earl",
            "city": "Atlanta",
        },
    )

    with app.app_context():
        assert City.query.filter_by(name="Atlanta").first() is not None
        assert Venue.query.filter_by(name="The Earl").first() is not None
        assert Artist.query.filter_by(spotify_id="spotify_test").first() is not None
        assert Track.query.filter_by(spotify_id="track_test").first() is not None
        assert Show.query.count() == 1


def test_add_show_multiple_artists(authed_client, app, mock_spotify):
    """POST /shows/add with comma-separated artists creates multiple."""
    from db_models import Show

    authed_client.post(
        "/shows/add",
        data={
            "artists": "Artist One, Artist Two",
            "date": "2026-06-20",
            "venue": "Terminal West",
            "city": "Atlanta",
        },
    )

    with app.app_context():
        show = Show.query.first()
        assert show is not None
        assert len(show.artists) == 2


def test_shows_list_displays_show(authed_client, mock_spotify):
    """Added show appears in list."""
    # add a show
    authed_client.post(
        "/shows/add",
        data={
            "artists": "Visible Artist",
            "date": "2026-07-01",
            "venue": "Variety Playhouse",
            "city": "Atlanta",
        },
    )

    # check list
    response = authed_client.get("/shows/")

    assert response.status_code == 200
    assert b"Variety Playhouse" in response.data
