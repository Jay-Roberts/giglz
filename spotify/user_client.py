"""
Spotify user client — user-authenticated API calls with auto-refresh.
"""
from datetime import datetime, timezone
import spotipy
from db_models import db, SpotifyToken
from spotify.oauth import refresh_access_token
from schemas import PlaybackState


class SpotifyNotConnectedError(Exception):
    """User has not connected Spotify."""
    pass


class SpotifyUserClient:
    """Wrapper around spotipy for user-authenticated calls."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self._token = None
        self._sp = None
        self._load_token()

    def _load_token(self) -> None:
        """Load token from DB."""
        self._token = SpotifyToken.query.filter_by(user_id=self.user_id).first()
        if not self._token:
            raise SpotifyNotConnectedError("User has not connected Spotify")
        self._refresh_if_needed()
        self._sp = spotipy.Spotify(auth=self._token.access_token)

    def _refresh_if_needed(self) -> None:
        """Refresh access token if expired."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if self._token.expires_at <= now:
            token_info = refresh_access_token(self._token.refresh_token)

            self._token.access_token = token_info.access_token
            self._token.expires_at = token_info.expires_at_datetime
            db.session.commit()

    def get_currently_playing(self) -> PlaybackState | None:
        """Get current playback state."""
        self._refresh_if_needed()
        self._sp = spotipy.Spotify(auth=self._token.access_token)

        result = self._sp.current_playback()
        if not result or not result.get("item"):
            return None

        item = result["item"]
        artists = item.get("artists", [])
        artist_name = artists[0]["name"] if artists else "Unknown Artist"

        album = item.get("album", {})
        images = album.get("images", [])
        album_art = images[0]["url"] if images else None

        return PlaybackState(
            track_id=item["id"],
            track_name=item["name"],
            artist_name=artist_name,
            album_art=album_art,
            is_playing=result.get("is_playing", False),
            progress_ms=result.get("progress_ms", 0),
            duration_ms=item.get("duration_ms", 0),
        )

    def save_track(self, spotify_track_id: str) -> None:
        """Add track to user's Saved Tracks (Liked Songs)."""
        self._refresh_if_needed()
        self._sp = spotipy.Spotify(auth=self._token.access_token)
        self._sp.current_user_saved_tracks_add([spotify_track_id])
