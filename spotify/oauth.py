"""
Spotify OAuth helpers — authorization URL, code exchange, token refresh.
"""
from spotipy.oauth2 import SpotifyOAuth as SpotipyOAuth
from schemas import SpotifyTokenInfo

SCOPES = [
    "user-read-playback-state",
    "user-read-currently-playing",
    "user-library-modify",
    "playlist-modify-public",
]


def _get_settings():
    from flask import current_app
    return current_app.extensions["settings"]


def _get_oauth() -> SpotipyOAuth:
    """Create SpotifyOAuth instance with current app config."""
    settings = _get_settings()
    return SpotipyOAuth(
        client_id=settings.spotify_client_id,
        client_secret=settings.spotify_client_secret,
        redirect_uri=settings.spotify_redirect_uri,
        scope=" ".join(SCOPES),
    )


def get_auth_url() -> str:
    """Generate Spotify authorize URL with scopes."""
    oauth = _get_oauth()
    return oauth.get_authorize_url()


def exchange_code(code: str) -> SpotifyTokenInfo:
    """Exchange auth code for tokens."""
    oauth = _get_oauth()
    token_info = oauth.get_access_token(code, as_dict=True, check_cache=False)
    return SpotifyTokenInfo(**token_info)


def refresh_access_token(refresh_token: str) -> SpotifyTokenInfo:
    """Refresh access token."""
    oauth = _get_oauth()
    token_info = oauth.refresh_access_token(refresh_token)
    return SpotifyTokenInfo(**token_info)
