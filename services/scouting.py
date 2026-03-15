"""
Scouting service — handle scouting a show (playlist swap + playback).
"""

from db_models import Show, Artist
from services.playlists import PlaylistService
from spotify.user_client import SpotifyUserClient, SpotifyNotConnectedError
from sqlalchemy.orm import joinedload


class ScoutingService:
    """Handle scouting a show — playlist swap + playback start."""

    def scout_show(self, user_id: str, show_id: str) -> bool:
        """
        Scout a show: swap Now Scouting playlist contents, start playback.
        Returns True if successful, False if no Spotify or no tracks.
        """
        # Get show with artists and tracks
        show = Show.query.options(
            joinedload(Show.artists).joinedload(Artist.tracks)
        ).get(show_id)

        if not show:
            return False

        # Collect all tracks from show's artists
        track_uris = []
        for artist in show.artists:
            for track in artist.tracks:
                if track.spotify_id:
                    track_uris.append(f"spotify:track:{track.spotify_id}")

        if not track_uris:
            return False

        # Get or create Now Scouting playlist (local)
        playlist_service = PlaylistService()
        playlist = playlist_service.get_or_create_now_scouting(user_id)

        # Ensure playlist exists on Spotify (lazy creation)
        spotify_playlist_id = playlist_service.ensure_spotify_playlist(user_id, playlist)
        if not spotify_playlist_id:
            return False  # User not connected to Spotify

        # Swap playlist contents + start playback
        try:
            client = SpotifyUserClient(user_id)
            client.replace_playlist_tracks(spotify_playlist_id, track_uris)

            # Start playback
            playlist_uri = f"spotify:playlist:{spotify_playlist_id}"
            client.start_playback(context_uri=playlist_uri)

            return True
        except SpotifyNotConnectedError:
            return False
        except Exception:
            # Log but don't crash — playlist might've updated even if playback failed
            return False
