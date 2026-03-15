"""
Spotify OAuth and now-playing tests.

Run with: uv run pytest tests/test_spotify.py -v
"""
import pytest
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
from schemas import SpotifyTokenInfo, PlaybackState

# =============================================================================
# EXPECTED REQUEST → RESPONSE PAIRS
# =============================================================================

# GET /spotify/connect (no session) — redirect to login
CONNECT_NO_SESSION_STATUS = 302
CONNECT_NO_SESSION_REDIRECT = "/auth/login"

# GET /spotify/connect (with session) — redirect to Spotify
CONNECT_STATUS = 302
CONNECT_REDIRECT_CONTAINS = "accounts.spotify.com"

# GET /spotify/callback?error=access_denied — redirect with error
CALLBACK_ERROR_STATUS = 302
CALLBACK_ERROR_REDIRECT = "/shows/"

# GET /spotify/callback?code=xxx — saves tokens, redirects
CALLBACK_SUCCESS_STATUS = 302
CALLBACK_SUCCESS_REDIRECT = "/shows/"

# GET /api/now-playing (no session) — 401
NOW_PLAYING_NO_SESSION_STATUS = 401

# GET /api/now-playing (no spotify) — connected: false
NOW_PLAYING_NOT_CONNECTED = {
    "connected": False,
    "playing": False,
    "track": None,
    "show_context": None,
}

# GET /api/now-playing (not playing) — playing: false
NOW_PLAYING_IDLE = {
    "connected": True,
    "playing": False,
    "track": None,
    "show_context": None,
}


# =============================================================================
# MOCK DATA
# =============================================================================

MOCK_TOKEN_INFO = SpotifyTokenInfo(
    access_token="mock_access_token",
    refresh_token="mock_refresh_token",
    expires_in=3600,
    expires_at=int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
)

MOCK_PLAYBACK = PlaybackState(
    track_id="spotify_track_123",
    track_name="Test Song",
    artist_name="Test Artist",
    album_art="https://example.com/art.jpg",
    is_playing=True,
    progress_ms=30000,
    duration_ms=180000,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def authed_client(client, create_user, create_token):
    """Client with authenticated session."""
    user_id, _ = create_user("spotify@example.com")
    token = create_token(user_id)
    client.get(f"/auth/verify?token={token}")
    return client, user_id


@pytest.fixture
def mock_oauth():
    """Mock Spotify OAuth helpers."""
    with patch("routes.spotify.get_auth_url") as mock_auth_url, \
         patch("routes.spotify.exchange_code") as mock_exchange:
        mock_auth_url.return_value = "https://accounts.spotify.com/authorize?test=1"
        mock_exchange.return_value = MOCK_TOKEN_INFO
        yield {"get_auth_url": mock_auth_url, "exchange_code": mock_exchange}


@pytest.fixture
def connected_client(authed_client, app, mock_oauth):
    """Client with Spotify connected."""
    from db_models import db, SpotifyToken
    from datetime import datetime, timezone, timedelta

    client, user_id = authed_client

    with app.app_context():
        expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
        token = SpotifyToken(
            user_id=user_id,
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            expires_at=expires_at,
        )
        db.session.add(token)
        db.session.commit()

    return client, user_id


# =============================================================================
# OAUTH TESTS
# =============================================================================


def test_connect_requires_auth(client):
    """GET /spotify/connect redirects to login when not authed."""
    response = client.get("/spotify/connect", follow_redirects=False)

    assert response.status_code == CONNECT_NO_SESSION_STATUS
    assert CONNECT_NO_SESSION_REDIRECT in response.headers.get("Location", "")


def test_connect_redirects_to_spotify(authed_client, mock_oauth):
    """GET /spotify/connect redirects to Spotify authorize URL."""
    client, _ = authed_client
    response = client.get("/spotify/connect", follow_redirects=False)

    assert response.status_code == CONNECT_STATUS
    assert CONNECT_REDIRECT_CONTAINS in response.headers.get("Location", "")


def test_callback_handles_error(authed_client):
    """GET /spotify/callback?error=xxx shows error and redirects."""
    client, _ = authed_client
    response = client.get("/spotify/callback?error=access_denied", follow_redirects=False)

    assert response.status_code == CALLBACK_ERROR_STATUS
    assert CALLBACK_ERROR_REDIRECT in response.headers.get("Location", "")


def test_callback_saves_token(authed_client, app, mock_oauth):
    """GET /spotify/callback?code=xxx saves tokens to DB."""
    from db_models import SpotifyToken

    client, user_id = authed_client
    response = client.get("/spotify/callback?code=test_code", follow_redirects=False)

    assert response.status_code == CALLBACK_SUCCESS_STATUS
    assert CALLBACK_SUCCESS_REDIRECT in response.headers.get("Location", "")

    with app.app_context():
        token = SpotifyToken.query.filter_by(user_id=user_id).first()
        assert token is not None
        assert token.access_token == MOCK_TOKEN_INFO.access_token
        assert token.refresh_token == MOCK_TOKEN_INFO.refresh_token


# =============================================================================
# NOW PLAYING TESTS
# =============================================================================


def test_now_playing_requires_auth(client):
    """GET /api/now-playing returns 401 when not authed."""
    response = client.get("/api/now-playing")

    assert response.status_code == NOW_PLAYING_NO_SESSION_STATUS


def test_now_playing_not_connected(authed_client):
    """GET /api/now-playing returns connected:false when no Spotify."""
    client, _ = authed_client
    response = client.get("/api/now-playing")

    assert response.status_code == 200
    assert response.json == NOW_PLAYING_NOT_CONNECTED


def test_now_playing_idle(connected_client):
    """GET /api/now-playing returns playing:false when not playing."""
    client, _ = connected_client

    with patch("spotify.user_client.SpotifyUserClient.get_currently_playing") as mock_playback:
        mock_playback.return_value = None
        response = client.get("/api/now-playing")

    assert response.status_code == 200
    assert response.json == NOW_PLAYING_IDLE


def test_now_playing_active(connected_client):
    """GET /api/now-playing returns track info when playing."""
    client, _ = connected_client

    with patch("spotify.user_client.SpotifyUserClient.get_currently_playing") as mock_playback:
        mock_playback.return_value = MOCK_PLAYBACK
        response = client.get("/api/now-playing")

    assert response.status_code == 200
    data = response.json
    assert data["connected"] is True
    assert data["playing"] is True
    assert data["track"]["name"] == "Test Song"
    assert data["track"]["artist"] == "Test Artist"
