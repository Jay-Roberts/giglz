"""Spotify API client.

Stateless wrapper around spotipy. Takes a token at construction,
doesn't manage auth. Token management is handled by TokenManager.
"""

import logging
import time
from typing import Any

import spotipy
from rapidfuzz import fuzz

from spotify.models import (
    ArtistSearch,
    ArtistTopTrack,
    CurrentlyPlaying,
    SpotifyPlaylist,
)

logger = logging.getLogger(__name__)

# Default fuzzy match thresholds (0-100)
DEFAULT_ARTIST_MATCH_REJECT_THRESHOLD = 75  # Below this: return None
DEFAULT_ARTIST_MATCH_REVIEW_THRESHOLD = 85  # Below this: log for review

USER_PLAYLIST_FETCH_LIMIT = 50
USER_PLAYLIST_MAX_PAGES = 3


class PlaylistCache:
    """Simple TTL cache for user playlists.

    Avoids refetching playlists on every request while still
    allowing updates to propagate within a reasonable time.
    """

    def __init__(self, ttl_seconds: int = 300) -> None:
        self._cache: dict[str, tuple[list[SpotifyPlaylist], float]] = {}
        self._ttl = ttl_seconds

    def get(self, user_id: str) -> list[SpotifyPlaylist] | None:
        """Get cached playlists for user, or None if expired/missing."""
        if user_id not in self._cache:
            return None
        playlists, timestamp = self._cache[user_id]
        if time.time() - timestamp > self._ttl:
            del self._cache[user_id]
            return None
        return playlists

    def set(self, user_id: str, playlists: list[SpotifyPlaylist]) -> None:
        """Cache playlists for user."""
        self._cache[user_id] = (playlists, time.time())

    def invalidate(self, user_id: str) -> None:
        """Remove user's playlists from cache."""
        self._cache.pop(user_id, None)


# Global playlist cache (shared across requests)
_playlist_cache = PlaylistCache()


class SpotifyAPI:
    """Stateless Spotify API wrapper.

    Takes a token at construction. Does not manage auth or token refresh.
    Use TokenManager for that.

    Args:
        token: Valid Spotify access token.
        match_reject_threshold: Fuzzy match score below which to reject (0-100).
        match_review_threshold: Fuzzy match score below which to log for review (0-100).
    """

    def __init__(
        self,
        token: str,
        match_reject_threshold: float = DEFAULT_ARTIST_MATCH_REJECT_THRESHOLD,
        match_review_threshold: float = DEFAULT_ARTIST_MATCH_REVIEW_THRESHOLD,
    ) -> None:
        self._token = token
        self._sp = spotipy.Spotify(auth=token)
        self._match_reject_threshold = match_reject_threshold
        self._match_review_threshold = match_review_threshold

        # Cache user info (lightweight, doesn't change)
        self._user = self._sp.current_user()
        if self._user is None:
            raise ValueError("Failed to get user info. Token may be invalid.")
        self._user_id = self._user["id"]

    @property
    def user_id(self) -> str:
        """Spotify user ID for the authenticated user."""
        return self._user_id

    def search_artist(self, artist_name: str) -> ArtistSearch | None:
        """Search Spotify for an artist by name with fuzzy matching.

        Fetches top 5 candidates and returns the best fuzzy match above
        threshold, or None if no confident match found.

        Args:
            artist_name: Artist name as entered by the user.

        Returns:
            The best-match ArtistSearch, or None if not found or below threshold.
        """
        logger.debug("Spotify search query: %r", artist_name)
        results = self._sp.search(q=artist_name, type="artist", limit=5)
        if results is None:
            logger.debug("Spotify returned None for %r", artist_name)
            return None

        items = results["artists"]["items"]
        if not items:
            logger.debug("Spotify returned 0 results for %r", artist_name)
            return None

        scored = [
            (artist, self._score_artist_match(artist_name, artist["name"]))
            for artist in items
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        best_match, best_score = scored[0]

        logger.debug(
            "Spotify candidates for %r: %s",
            artist_name,
            [(a["name"], score) for a, score in scored],
        )

        if best_score < self._match_reject_threshold:
            logger.info(
                "No confident match for %r (best: %r at %.1f)",
                artist_name,
                best_match["name"],
                best_score,
            )
            return None

        if best_score < self._match_review_threshold:
            logger.info(
                "Low confidence match: %r -> %r (%.1f)",
                artist_name,
                best_match["name"],
                best_score,
            )
        # TODO: We should optionally return a list of the ones that need review.
        return ArtistSearch(
            name=best_match["name"],
            id=best_match["id"],
            url=best_match["external_urls"]["spotify"],
            match_score=best_score,
        )

    def _score_artist_match(self, query: str, candidate: str) -> float:
        """Score artist name similarity (0-100)."""
        q = query.lower().strip()
        c = candidate.lower().strip()
        return fuzz.ratio(q, c)

    def get_top_tracks(
        self, artist_id: str, limit: int = 3
    ) -> list[ArtistTopTrack] | None:
        """Get an artist's top tracks on Spotify.

        Note:
            Does not filter by country — results use Spotify's default
            market.  ``artist_name`` on each track is the *primary*
            credited artist, which may differ from the artist searched
            for (e.g. features, collabs).

        Args:
            artist_id: Spotify artist ID.
            limit: Number of tracks to return (max 10, Spotify's limit).

        Returns:
            List of ArtistTopTrack, or None if the lookup fails.

        Raises:
            ValueError: If limit exceeds 10.
        """
        if limit > 10:
            raise ValueError(f"Can only request up to ten tracks but got {limit}.")

        top_tracks_results = self._sp.artist_top_tracks(artist_id)
        if top_tracks_results is None:
            return None

        top_tracks = top_tracks_results["tracks"][:limit]
        return [
            ArtistTopTrack(
                artist_name=track_result["artists"][0]["name"],
                track=track_result["name"],
                uri=track_result["uri"],
                id=track_result["id"],
            )
            for track_result in top_tracks
        ]

    def get_user_playlists(self, use_cache: bool = True) -> list[SpotifyPlaylist]:
        """Fetch the user's playlists from Spotify.

        Args:
            use_cache: Whether to use cached playlists if available.

        Returns:
            List of SpotifyPlaylist objects.
        """
        if use_cache:
            cached = _playlist_cache.get(self._user_id)
            if cached is not None:
                logger.debug("Using cached playlists for user %s", self._user_id)
                return cached

        playlists: list[SpotifyPlaylist] = []
        offset = 0

        while offset < USER_PLAYLIST_MAX_PAGES:
            results = self._sp.current_user_playlists(
                limit=USER_PLAYLIST_FETCH_LIMIT,
                offset=offset * USER_PLAYLIST_FETCH_LIMIT,
            )
            offset += 1

            if not results:
                break

            items = results.get("items") or []
            playlists.extend(SpotifyPlaylist.from_spotify_response(p) for p in items)

            if len(items) < USER_PLAYLIST_FETCH_LIMIT:
                break

        logger.info(
            "Fetched %d playlists for user %s",
            len(playlists),
            self._user_id,
        )

        _playlist_cache.set(self._user_id, playlists)
        return playlists

    def get_user_playlist(
        self, name: str | None = None, playlist_id: str | None = None
    ) -> SpotifyPlaylist | None:
        """Look up a playlist by name or ID.

        If both ``name`` and ``playlist_id`` are given, ``playlist_id``
        takes precedence since it is unique.
        """
        if not name and not playlist_id:
            raise ValueError("At least one of `name` or `playlist_id` must be set.")

        playlists = self.get_user_playlists()

        if playlist_id is not None:
            matches = [p for p in playlists if p.id == playlist_id]
        else:
            matches = [p for p in playlists if p.name == name]

        if not matches:
            return None
        return matches[0]

    def get_or_create_playlist(self, name: str) -> SpotifyPlaylist | None:
        """Return an existing playlist by name, or create a new private one."""
        if user_playlist := self.get_user_playlist(name):
            logger.info("Found existing playlist %r (id=%s)", name, user_playlist.id)
            return user_playlist

        logger.info("Creating new playlist %r", name)
        create_response = self._sp.user_playlist_create(
            self._user_id,
            name=name,
            public=False,
            collaborative=False,
            description="giglz created playlist to help you find shows~~",
        )
        logger.debug("Playlist create response: %s", create_response)
        if create_response is None:
            logger.warning("Playlist creation returned None for %r", name)
            return None

        logger.info(
            "Created playlist %r (id=%s, url=%s)",
            name,
            create_response.get("id"),
            create_response.get("external_urls", {}).get("spotify"),
        )
        created_playlist = SpotifyPlaylist.from_spotify_response(create_response)

        # Invalidate cache so new playlist appears on next fetch
        _playlist_cache.invalidate(self._user_id)

        return created_playlist

    def add_tracks_to_playlist(self, playlist_id: str, track_uris: list[str]) -> bool:
        """Append tracks to a playlist.

        Args:
            playlist_id: Spotify playlist ID.
            track_uris: List of track URIs to add.

        Returns:
            True if successful.
        """
        # Spotify API limit: 100 tracks per request
        batch_size = 100
        for i in range(0, len(track_uris), batch_size):
            batch = track_uris[i : i + batch_size]
            self._sp.playlist_add_items(playlist_id, batch)
        return True

    def clear_playlist(self, playlist_id: str) -> bool:
        """Remove all tracks from a playlist.

        Uses playlist_replace_items with an empty list to clear all tracks
        in a single API call.

        Args:
            playlist_id: Spotify playlist ID.

        Returns:
            True if successful.
        """
        logger.info("Clearing all tracks from playlist %s", playlist_id)
        self._sp.playlist_replace_items(playlist_id, [])
        return True

    def transfer_playback_to_playlist(
        self, playlist_id: str, track_uri: str | None = None
    ) -> bool:
        """Start playing a playlist, optionally from a specific track.

        Args:
            playlist_id: Spotify playlist ID to play.
            track_uri: Optional track URI to start from. If the track is in
                       the playlist, playback starts there. If not provided
                       or not found, starts from the beginning.

        Returns:
            True if successful.

        Note:
            Requires Spotify Premium. Will fail on free accounts.
        """
        context_uri = f"spotify:playlist:{playlist_id}"
        payload: dict[str, Any] = {"context_uri": context_uri}

        if track_uri:
            payload["offset"] = {"uri": track_uri}

        logger.info(
            "Transferring playback to playlist %s (offset: %s)",
            playlist_id,
            track_uri or "start",
        )

        self._sp.start_playback(**payload)
        return True

    def follow_playlist(self, playlist_id: str) -> bool:
        """Follow a playlist (add to user's library).

        Args:
            playlist_id: Spotify playlist ID to follow.

        Returns:
            True if successful.
        """
        logger.info("Following playlist %s", playlist_id)
        self._sp.current_user_follow_playlist(playlist_id)
        return True

    def get_currently_playing(self) -> CurrentlyPlaying | None:
        """Get the user's currently playing track.

        Returns:
            CurrentlyPlaying DTO, or None if nothing playing
            or if playing non-track content (podcasts, ads).
        """
        result = self._sp.currently_playing()
        track = CurrentlyPlaying.from_spotify_response(result)
        if not track:
            logger.debug(
                "Nothing playing or non-track: %s",
                result.get("currently_playing_type") if result else None,
            )
        return track
