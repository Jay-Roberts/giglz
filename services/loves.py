"""
Love service — handle track love/unlove operations.
"""

from db_models import db, Track, UserTrackLove
from spotify.user_client import SpotifyUserClient, SpotifyNotConnectedError


class LoveService:
    """Handle track love/unlove operations."""

    def toggle_love(self, user_id: str, spotify_track_id: str) -> bool:
        """Toggle love state. Returns new state (True = loved, False = unloved).

        Takes Spotify track ID, looks up internal Track.
        Returns False if track not in our database.
        """
        track = Track.query.filter_by(spotify_id=spotify_track_id).first()
        if not track:
            # Track not in our DB — can't love what we don't know
            return False

        existing = UserTrackLove.query.filter_by(
            user_id=user_id, track_id=track.id
        ).first()

        if existing:
            # Unlove
            db.session.delete(existing)
            if track.artist and track.artist.love_count > 0:
                track.artist.love_count -= 1
            db.session.commit()
            return False
        else:
            # Love
            love = UserTrackLove(user_id=user_id, track_id=track.id)
            db.session.add(love)
            if track.artist:
                track.artist.love_count += 1
            db.session.commit()
            self._sync_to_spotify(user_id, spotify_track_id)
            return True

    def is_loved(self, user_id: str, spotify_track_id: str) -> bool:
        """Check if user has loved a track (by Spotify ID)."""
        track = Track.query.filter_by(spotify_id=spotify_track_id).first()
        if not track:
            return False
        return UserTrackLove.query.filter_by(
            user_id=user_id, track_id=track.id
        ).first() is not None

    def _sync_to_spotify(self, user_id: str, spotify_track_id: str) -> None:
        """Add track to user's Spotify library (best-effort)."""
        try:
            client = SpotifyUserClient(user_id)
            client.save_track(spotify_track_id)
        except SpotifyNotConnectedError:
            # User hasn't connected Spotify — that's fine
            pass
        except Exception:
            # Log but don't fail — local love succeeded
            pass
