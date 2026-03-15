"""
Board service — aggregate data for personal dashboard.
"""

from datetime import date
from collections import defaultdict
from sqlalchemy.orm import joinedload
from db_models import Show, Playlist, UserTrackLove, UserShowStatus, ShowStatus, Track


class BoardService:
    """Aggregate data for the personal board view."""

    def get_board_data(self, user_id: str) -> dict:
        return {
            "calendar_shows": self._get_calendar_shows(user_id),
            "playlists": self._get_playlists(user_id),
            "loved_tracks": self._get_loved_tracks(user_id),
            "top_artists": self._get_top_artists(user_id),
        }

    def _get_calendar_shows(self, user_id: str) -> dict[date, list[Show]]:
        """Shows user is 'going' to, grouped by date."""
        statuses = UserShowStatus.query.filter_by(
            user_id=user_id,
            status=ShowStatus.GOING
        ).all()

        show_ids = [s.show_id for s in statuses]
        if not show_ids:
            return {}

        shows = Show.query.filter(
            Show.id.in_(show_ids)
        ).options(
            joinedload(Show.venue),
            joinedload(Show.artists)
        ).order_by(Show.date).all()

        by_date = defaultdict(list)
        for show in shows:
            by_date[show.date].append(show)

        return dict(by_date)

    def _get_playlists(self, user_id: str) -> list[Playlist]:
        """User's playlists."""
        return Playlist.query.filter_by(user_id=user_id).all()

    def _get_loved_tracks(self, user_id: str, limit: int = 20) -> list[dict]:
        """Recent loved tracks with artist info."""
        loves = UserTrackLove.query.filter_by(
            user_id=user_id
        ).order_by(
            UserTrackLove.loved_at.desc()
        ).limit(limit).all()

        # Eager load track + artist
        track_ids = [love.track_id for love in loves]
        tracks = {t.id: t for t in Track.query.filter(
            Track.id.in_(track_ids)
        ).options(joinedload(Track.artist)).all()}

        return [
            {
                "track": tracks.get(love.track_id),
                "loved_at": love.loved_at,
            }
            for love in loves
            if tracks.get(love.track_id)
        ]

    def _get_top_artists(self, user_id: str, limit: int = 10) -> list[dict]:
        """Artists ranked by how many of their tracks user loved."""
        loves = UserTrackLove.query.filter_by(user_id=user_id).all()
        track_ids = [love.track_id for love in loves]

        if not track_ids:
            return []

        tracks = Track.query.filter(
            Track.id.in_(track_ids)
        ).options(joinedload(Track.artist)).all()

        # Count loves per artist
        artist_counts = defaultdict(int)
        artist_map = {}
        for track in tracks:
            if track.artist:
                artist_counts[track.artist.id] += 1
                artist_map[track.artist.id] = track.artist

        # Sort by count
        sorted_artists = sorted(
            artist_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]

        return [
            {"artist": artist_map[aid], "love_count": count}
            for aid, count in sorted_artists
        ]
