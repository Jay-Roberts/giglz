"""Spotify API data transfer object.

These are lightweight models for passing Spotify API data around.
They are not persisted — see models.py for app-level domain models.
"""

import pydantic


class ArtistSearch(pydantic.BaseModel):
    """Best-match result from a Spotify artist search with fuzzy scoring."""

    name: str
    id: str
    url: str
    match_score: float = 100.0  # Fuzzy match confidence (0-100)


class ArtistTopTrack(pydantic.BaseModel):
    """A single track from an artist's top tracks.

    Note:
        ``artist_name`` is taken from the first credited artist on the
        track.  If the searched artist is a feature rather than the
        primary artist, this field will not match the artist you
        searched for.
    """

    artist_name: str
    track: str
    uri: str
    id: str


class UserPlaylist(pydantic.BaseModel):
    """A playlist owned by the authenticated user."""

    user_id: str
    name: str
    id: str
    url: str

    @classmethod
    def from_spotify_playlist(cls, playlist: dict) -> "UserPlaylist":
        """Build from a Spotify playlist dict.

        Works with responses from both ``current_user_playlists`` and
        ``user_playlist_create`` — the fields we need (name, id,
        external_urls, owner) share the same shape.
        """
        return cls(
            user_id=playlist["owner"]["id"],
            name=playlist["name"],
            id=playlist["id"],
            url=playlist["external_urls"]["spotify"],
        )


class CurrentlyPlaying(pydantic.BaseModel):
    """Currently playing track from Spotify."""

    track_name: str
    artist_name: str
    track_id: str
    track_uri: str
    album_art_url: str | None
    is_playing: bool

    @classmethod
    def from_spotify_response(cls, result: dict | None) -> "CurrentlyPlaying | None":
        """Build from Spotify currently_playing response.

        Returns None if nothing playing or if playing non-track content
        (podcasts, ads, etc.).
        """
        if not result or not result.get("item"):
            return None

        if result.get("currently_playing_type") != "track":
            return None

        track = result["item"]
        return cls(
            track_name=track["name"],
            artist_name=track["artists"][0]["name"],
            track_id=track["id"],
            track_uri=track["uri"],
            album_art_url=track["album"]["images"][0]["url"]
            if track["album"].get("images")
            else None,
            is_playing=result.get("is_playing", False),
        )
