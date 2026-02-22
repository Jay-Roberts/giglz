"""Database facade - single entry point for all persistence."""

from collections import defaultdict
from datetime import datetime, timezone

from extensions import db
from db_models import (
    Show as ShowModel,
    ShowTrack,
    ImportedUrl as ImportedUrlModel,
    UserLovedTrack,
)
from models import (
    Show,
    ShowSubmission,
    ImportedUrl,
    ImportStatus,
    LovedTrack,
)


class Database:
    """Single entry point for all persistence operations.

    Usage:
        from db import get_db
        get_db().save_show(show)
    """

    # -------------------------------------------------------------------------
    # Shows
    # -------------------------------------------------------------------------

    def save_show(self, show: Show) -> None:
        """Persist a show (upsert behavior)."""
        ShowModel.query.filter_by(show_id=show.id).delete()
        ShowTrack.query.filter_by(show_id=show.id).delete()

        # Insert one row per artist (denormalized)
        for artist_name, spotify_id in zip(
            show.submission.artists, show.artist_spotify_ids
        ):
            row = ShowModel(
                show_id=show.id,
                venue=show.submission.venue,
                date=show.submission.date,
                playlist_name=show.playlist_name,
                playlist_id=show.playlist_id,
                created_at=show.created_at,
                ticket_url=show.submission.ticket_url,
                artist_name=artist_name,
                spotify_id=spotify_id or None,
            )
            db.session.add(row)

        for track_uri in show.track_uris:
            track_row = ShowTrack(show_id=show.id, track_uri=track_uri)
            db.session.add(track_row)

        db.session.commit()

    def get_show(self, show_id: str) -> Show | None:
        """Get show by ID."""
        rows = ShowModel.query.filter_by(show_id=show_id).order_by(ShowModel.id).all()
        if not rows:
            return None

        track_uris = [
            t.track_uri for t in ShowTrack.query.filter_by(show_id=show_id).all()
        ]
        return self._rows_to_show(rows, track_uris)

    def get_all_shows(self) -> list[Show]:
        """Get all shows."""
        all_rows = ShowModel.query.order_by(ShowModel.show_id, ShowModel.id).all()
        all_tracks = ShowTrack.query.all()

        rows_by_show: dict[str, list[ShowModel]] = defaultdict(list)
        for row in all_rows:
            rows_by_show[row.show_id].append(row)

        tracks_by_show: dict[str, list[str]] = defaultdict(list)
        for track in all_tracks:
            tracks_by_show[track.show_id].append(track.track_uri)

        shows = []
        for show_id, rows in rows_by_show.items():
            track_uris = tracks_by_show.get(show_id, [])
            shows.append(self._rows_to_show(rows, track_uris))

        return shows

    def get_shows_by_playlist(self, playlist_name: str) -> list[Show]:
        """Get all shows in a playlist (case-insensitive)."""
        rows = ShowModel.query.filter(
            db.func.lower(ShowModel.playlist_name) == playlist_name.lower()
        ).all()

        show_ids = list(dict.fromkeys(r.show_id for r in rows))
        shows = [self.get_show(sid) for sid in show_ids]
        return [s for s in shows if s is not None]

    def get_playlists(self) -> list[dict]:
        """Get playlist summaries: [{name, show_count, loved_count}]."""
        all_rows = ShowModel.query.all()

        playlists: dict[str, dict] = {}
        seen_shows: dict[str, set] = defaultdict(set)

        for row in all_rows:
            name = row.playlist_name
            if not name:
                continue
            if name not in playlists:
                playlists[name] = {"name": name, "show_count": 0, "loved_count": 0}
            if row.show_id not in seen_shows[name]:
                seen_shows[name].add(row.show_id)
                playlists[name]["show_count"] += 1

        return list(playlists.values())

    def is_track_scouted(self, track_uri: str) -> bool:
        """Check if track exists in any show."""
        return ShowTrack.query.filter_by(track_uri=track_uri).first() is not None

    def get_shows_with_track(self, track_uri: str) -> list[str]:
        """Get show IDs containing a track."""
        tracks = ShowTrack.query.filter_by(track_uri=track_uri).all()
        return list(dict.fromkeys(t.show_id for t in tracks))

    def _rows_to_show(self, rows: list[ShowModel], track_uris: list[str]) -> Show:
        """Reconstruct Show from denormalized DB rows."""
        first = rows[0]
        artists = [r.artist_name for r in rows]
        artist_spotify_ids = [r.spotify_id or "" for r in rows]

        submission = ShowSubmission(
            artists=artists,
            venue=first.venue,
            date=first.date,
            ticket_url=first.ticket_url,
        )

        return Show(
            id=first.show_id,
            submission=submission,
            created_at=first.created_at,
            artist_spotify_ids=artist_spotify_ids,
            track_uris=track_uris,
            playlist_id=first.playlist_id,
            playlist_name=first.playlist_name,
            loved_tracks=[],  # Loved tracks are per-user now, not per-show
        )

    # -------------------------------------------------------------------------
    # Imports
    # -------------------------------------------------------------------------

    def get_import(self, url: str) -> ImportedUrl | None:
        """Look up import record by URL."""
        row = ImportedUrlModel.query.filter_by(url=url).first()
        if not row:
            return None

        return ImportedUrl(
            url=row.url,
            status=ImportStatus(row.status),
            show_id=row.show_id,
            artist_count=row.artist_count or 0,
            track_count=row.track_count or 0,
            error=row.error,
            attempted_at=row.attempted_at,
        )

    def was_imported(self, url: str) -> bool:
        """Check if URL was successfully imported."""
        imp = self.get_import(url)
        return imp is not None and imp.status == ImportStatus.SUCCESS

    # -------------------------------------------------------------------------
    # Love/Unlove Tracks
    # -------------------------------------------------------------------------

    def love_track(
        self,
        user_id: str,
        track_uri: str,
        track_name: str,
        artist_name: str,
    ) -> list[str]:
        """Love a track for a user.

        Returns list of show IDs containing this track.
        """
        existing = UserLovedTrack.query.filter_by(
            user_id=user_id, track_uri=track_uri
        ).first()
        if not existing:
            row = UserLovedTrack(
                user_id=user_id,
                track_uri=track_uri,
                track_name=track_name,
                artist_name=artist_name,
                loved_at=datetime.now(timezone.utc).isoformat(),
            )
            db.session.add(row)
            db.session.commit()

        return self.get_shows_with_track(track_uri)

    def unlove_track(self, user_id: str, track_uri: str) -> list[str]:
        """Unlove a track for a user.

        Returns list of show IDs containing this track.
        """
        UserLovedTrack.query.filter_by(user_id=user_id, track_uri=track_uri).delete()
        db.session.commit()

        return self.get_shows_with_track(track_uri)

    def is_track_loved(self, user_id: str, track_uri: str) -> bool:
        """Check if user has loved a track."""
        return (
            UserLovedTrack.query.filter_by(user_id=user_id, track_uri=track_uri).first()
            is not None
        )

    def get_loved_tracks(self, user_id: str) -> list[LovedTrack]:
        """Get all tracks loved by a user."""
        rows = UserLovedTrack.query.filter_by(user_id=user_id).all()
        return [
            LovedTrack(uri=r.track_uri, name=r.track_name, artist=r.artist_name)
            for r in rows
        ]

    def get_loved_counts_for_shows(
        self, user_id: str, show_ids: list[str]
    ) -> dict[str, int]:
        """Get loved track counts per show for a user.

        Returns dict of {show_id: count} for shows where count > 0.
        """
        if not show_ids:
            return {}

        # Get all tracks loved by this user
        loved_uris = {
            r.track_uri
            for r in UserLovedTrack.query.filter_by(user_id=user_id).all()
        }
        if not loved_uris:
            return {}

        # Count loved tracks per show
        counts: dict[str, int] = {}
        for show_id in show_ids:
            show_tracks = ShowTrack.query.filter_by(show_id=show_id).all()
            count = sum(1 for t in show_tracks if t.track_uri in loved_uris)
            if count > 0:
                counts[show_id] = count

        return counts

    # -------------------------------------------------------------------------
    # Combined Operations
    # -------------------------------------------------------------------------

    def record_import(
        self,
        imported_url: ImportedUrl,
        show: Show | None = None,
    ) -> None:
        """Save import record and show together.

        Args:
            imported_url: The import record (success, failed, or skipped).
            show: The show to save (only for successful imports).
        """
        ImportedUrlModel.query.filter_by(url=imported_url.url).delete()
        row = ImportedUrlModel(
            url=imported_url.url,
            status=imported_url.status.value,
            show_id=imported_url.show_id,
            artist_count=imported_url.artist_count,
            track_count=imported_url.track_count,
            error=imported_url.error,
            attempted_at=imported_url.attempted_at,
        )
        db.session.add(row)

        if show:
            self.save_show(show)
        else:
            db.session.commit()

    def clear_all(self) -> None:
        """Wipe all shows and import records."""
        ShowTrack.query.delete()
        ShowModel.query.delete()
        ImportedUrlModel.query.delete()
        UserLovedTrack.query.delete()
        db.session.commit()
