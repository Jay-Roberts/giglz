"""
Playlist service — business logic for playlists.

Handles Now Scouting playlist: get/create, add/remove shows, get tracks.
"""
from db_models import db, Playlist, PlaylistShow, Show, Track


class PlaylistService:
    def get_or_create_now_scouting(self, user_id: str) -> Playlist:
        """Get user's Now Scouting playlist, create if doesn't exist."""
        playlist = Playlist.query.filter_by(
            user_id=user_id,
            is_now_scouting=True
        ).first()

        if playlist:
            return playlist

        playlist = Playlist(
            user_id=user_id,
            name="Now Scouting",
            is_now_scouting=True,
        )
        db.session.add(playlist)
        db.session.commit()
        return playlist

    def add_show_to_playlist(self, playlist_id: str, show_id: str) -> None:
        """Add show to playlist. No-op if already in playlist."""
        if self.is_show_in_playlist(playlist_id, show_id):
            return

        playlist_show = PlaylistShow(playlist_id=playlist_id, show_id=show_id)
        db.session.add(playlist_show)
        db.session.commit()

    def remove_show_from_playlist(self, playlist_id: str, show_id: str) -> None:
        """Remove show from playlist."""
        PlaylistShow.query.filter_by(
            playlist_id=playlist_id,
            show_id=show_id
        ).delete()
        db.session.commit()

    def get_playlist_tracks(self, playlist_id: str) -> list[Track]:
        """Get all tracks from all shows in playlist."""
        playlist = db.session.get(Playlist, playlist_id)
        if not playlist:
            return []

        # playlist → shows → artists → tracks
        tracks = []
        seen_track_ids = set()

        for show in playlist.shows:
            for artist in show.artists:
                for track in artist.tracks:
                    if track.id not in seen_track_ids:
                        tracks.append(track)
                        seen_track_ids.add(track.id)

        return tracks

    def is_show_in_playlist(self, playlist_id: str, show_id: str) -> bool:
        """Check if show is already in playlist."""
        return PlaylistShow.query.filter_by(
            playlist_id=playlist_id,
            show_id=show_id
        ).first() is not None

    def get_scouting_show_ids(self, playlist_id: str) -> set[str]:
        """Get set of show IDs in playlist (for template context)."""
        rows = PlaylistShow.query.filter_by(playlist_id=playlist_id).all()
        return {row.show_id for row in rows}
