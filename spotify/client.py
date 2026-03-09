import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from rapidfuzz import fuzz
from flask import current_app

from spotify.models import ArtistSearch, TrackInfo

MATCH_REJECT_THRESHOLD = 75
MATCH_REVIEW_THRESHOLD = 85


class SpotifyAPI:
    """Spotify API wrapper using client credentials (no user auth needed)."""

    def __init__(self):
        auth_manager = SpotifyClientCredentials(
            client_id=current_app.config["SPOTIFY_CLIENT_ID"],
            client_secret=current_app.config["SPOTIFY_CLIENT_SECRET"],
        )
        self._sp = spotipy.Spotify(auth_manager=auth_manager)

    def search_artist(self, name: str) -> ArtistSearch | None:
        """Search for artist, return best fuzzy match or None."""
        results = self._sp.search(q=name, type="artist", limit=5)
        if not results:
            return None

        items = results["artists"]["items"]
        if not items:
            return None

        # score candidates
        scored = [
            (artist, fuzz.ratio(name.lower(), artist["name"].lower()))
            for artist in items
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        best, score = scored[0]

        if score < MATCH_REJECT_THRESHOLD:
            return None

        images = best.get("images", [])
        image_url = images[0]["url"] if images else None

        return ArtistSearch(
            spotify_id=best["id"],
            name=best["name"],
            image_url=image_url,
            match_score=score,
        )

    def get_top_tracks(self, artist_spotify_id: str, limit: int = 5) -> list[TrackInfo]:
        """Get artist's top tracks."""
        results = self._sp.artist_top_tracks(artist_spotify_id)
        if not results:
            return []

        tracks = results["tracks"][:limit]
        return [
            TrackInfo(
                spotify_id=t["id"],
                name=t["name"],
                preview_url=t.get("preview_url"),
            )
            for t in tracks
        ]
