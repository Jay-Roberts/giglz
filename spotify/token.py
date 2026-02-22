"""Spotify OAuth token management.

Handles authentication, token storage, and refresh.
"""

import logging
import os

import dotenv
import spotipy

logger = logging.getLogger(__name__)

SPOTIFY_SCOPE = (
    "streaming"
    " user-read-email"
    " user-read-private"
    " user-read-currently-playing"
    " user-modify-playback-state"
    " user-read-playback-state"
    " playlist-modify-public"
    " playlist-modify-private"
    " playlist-read-private"
    " user-library-modify"
)
# playlist-read-private: needed to list user's playlists
# user-library-modify: needed to follow playlists


dotenv.load_dotenv(".env")


class TokenManager:
    """Manages Spotify OAuth tokens.

    Handles authentication flow, token caching, and refresh.
    Separate from API operations — use SpotifyAPI for that.

    Args:
        user_id: Optional Spotify user ID for per-user token storage.
                 If provided, tokens are stored in `.cache-{user_id}`.
                 If None, uses default `.cache` file.
    """

    def __init__(self, user_id: str | None = None) -> None:
        cache_path = f".cache-{user_id}" if user_id else ".cache"
        self._user_id = user_id
        self._oauth = spotipy.SpotifyOAuth(
            client_id=os.environ.get("SPOTIFY_CLIENT_ID"),
            client_secret=os.environ.get("SPOTIFY_CLIENT_SECRET"),
            redirect_uri=os.environ.get("SPOTIFY_REDIRECT_URI"),
            scope=SPOTIFY_SCOPE,
            cache_path=cache_path,
        )

    def get_token(self) -> str | None:
        """Get a valid access token, refreshing if needed.

        Returns:
            Access token string, or None if not authenticated.
        """
        token_info = self._oauth.get_cached_token()
        if token_info is None:
            return None
        return token_info["access_token"]

    def get_token_info(self) -> dict | None:
        """Get full token info dict, refreshing if needed.

        Returns:
            Token info dict with access_token, refresh_token, etc.
        """
        return self._oauth.get_cached_token()

    def is_authenticated(self) -> bool:
        """Check if we have a cached token."""
        return self._oauth.get_cached_token() is not None

    def get_auth_url(self, state: str | None = None) -> str:
        """Get Spotify OAuth authorization URL.

        Args:
            state: Optional state parameter for CSRF protection.

        Returns:
            URL to redirect user to for Spotify login.
        """
        return self._oauth.get_authorize_url(state=state)

    def exchange_code(self, code: str) -> dict:
        """Exchange authorization code for access token.

        Args:
            code: Authorization code from Spotify callback.

        Returns:
            Token info dict with access_token, refresh_token, etc.
        """
        # check_cache=False ensures we actually exchange the code
        # instead of returning a cached token from a different user
        return self._oauth.get_access_token(code, as_dict=True, check_cache=False)

    def save_token(self, token_info: dict) -> None:
        """Save token info to cache file.

        Args:
            token_info: Token dict from exchange_code() or refresh.
        """
        self._oauth.cache_handler.save_token_to_cache(token_info)
