"""Database facade - single entry point for all persistence."""

import uuid
from datetime import datetime, timezone

from extensions import db
from db_models import (
    Playlist as PlaylistModel,
    Show as ShowModel,
    ShowArtist,
    ShowTrack,
    PlaylistShow,
    ImportedUrl as ImportedUrlModel,
    UserLovedTrack,
)
from models import (
    Artist,
    Show,
    Playlist,
    ImportedUrl,
    ImportStatus,
    LovedTrack,
)

DEFAULT_PLAYLIST_NAME = "all the giglz"


class Database:
    """Single entry point for all persistence operations."""

    # -------------------------------------------------------------------------
    # Playlists
    # -------------------------------------------------------------------------

    def create_playlist(self, name: str, owner_user_id: str) -> Playlist:
        """Create a new playlist."""
        playlist_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        row = PlaylistModel(
            id=playlist_id,
            name=name,
            owner_user_id=owner_user_id,
            created_at=now,
        )
        db.session.add(row)
        db.session.commit()

        return Playlist(
            id=playlist_id,
            name=name,
            owner_user_id=owner_user_id,
            created_at=now,
            spotify_playlist_id=None,
        )

    def get_playlist(self, playlist_id: str) -> Playlist | None:
        """Get playlist by ID."""
        row = PlaylistModel.query.filter_by(id=playlist_id).first()
        if not row:
            return None
        return self._row_to_playlist(row)

    def get_playlist_by_name(self, name: str) -> Playlist | None:
        """Get playlist by name (case-insensitive).

        Returns the most recently created match if multiple exist.
        Use count_playlists_by_name() to check for duplicates.
        """
        row = PlaylistModel.query.filter(
            db.func.lower(PlaylistModel.name) == name.lower()
        ).order_by(PlaylistModel.created_at.desc()).first()
        if not row:
            return None
        return self._row_to_playlist(row)

    def count_playlists_by_name(self, name: str) -> int:
        """Count playlists with a given name (case-insensitive)."""
        return PlaylistModel.query.filter(
            db.func.lower(PlaylistModel.name) == name.lower()
        ).count()

    def get_all_playlists(self) -> list[Playlist]:
        """Get all playlists."""
        rows = PlaylistModel.query.order_by(PlaylistModel.created_at).all()
        return [self._row_to_playlist(r) for r in rows]

    def get_or_create_default_playlist(self, owner_user_id: str) -> Playlist:
        """Get the default playlist, creating it if it doesn't exist.

        Returns the most recent if multiple exist with the default name.
        Caller should use count_playlists_by_name() to warn about duplicates.
        """
        playlist = self.get_playlist_by_name(DEFAULT_PLAYLIST_NAME)
        if playlist:
            return playlist
        return self.create_playlist(DEFAULT_PLAYLIST_NAME, owner_user_id)

    def update_playlist_spotify_id(
        self, playlist_id: str, spotify_playlist_id: str | None
    ) -> None:
        """Link a Giglz playlist to a Spotify playlist.

        Called when:
        - First sync: Giglz playlist exists, Spotify playlist just created
        - Re-sync: Spotify playlist was deleted, new one created

        Set to None to clear the link (e.g., if Spotify playlist is gone).
        """
        row = PlaylistModel.query.filter_by(id=playlist_id).first()
        if row:
            row.spotify_playlist_id = spotify_playlist_id
            db.session.commit()

    def _row_to_playlist(self, row: PlaylistModel) -> Playlist:
        """Convert DB row to Pydantic model."""
        return Playlist(
            id=row.id,
            name=row.name,
            owner_user_id=row.owner_user_id,
            created_at=row.created_at,
            spotify_playlist_id=row.spotify_playlist_id,
        )

    # -------------------------------------------------------------------------
    # Shows
    # -------------------------------------------------------------------------

    def save_show(self, show: Show) -> None:
        """Persist a show (upsert behavior)."""
        # Delete existing data for this show
        ShowArtist.query.filter_by(show_id=show.id).delete()
        ShowTrack.query.filter_by(show_id=show.id).delete()
        ShowModel.query.filter_by(id=show.id).delete()

        # Insert show
        show_row = ShowModel(
            id=show.id,
            venue=show.venue,
            date=show.date,
            created_at=show.created_at,
            ticket_url=show.ticket_url,
        )
        db.session.add(show_row)

        # Insert artists
        for position, artist in enumerate(show.artists):
            artist_row = ShowArtist(
                show_id=show.id,
                artist_name=artist.name,
                position=position,
                spotify_id=artist.spotify_id,
            )
            db.session.add(artist_row)

        # Insert tracks
        for track_uri in show.track_uris:
            track_row = ShowTrack(show_id=show.id, track_uri=track_uri)
            db.session.add(track_row)

        db.session.commit()

    def get_show(self, show_id: str) -> Show | None:
        """Get show by ID."""
        row = ShowModel.query.filter_by(id=show_id).first()
        if not row:
            return None
        return self._row_to_show(row)

    def get_all_shows(self) -> list[Show]:
        """Get all shows."""
        rows = ShowModel.query.order_by(ShowModel.created_at.desc()).all()
        return [self._row_to_show(r) for r in rows]

    def _row_to_show(self, row: ShowModel) -> Show:
        """Reconstruct Show from normalized DB rows."""
        artist_rows = ShowArtist.query.filter_by(show_id=row.id).order_by(
            ShowArtist.position
        ).all()
        artists = [
            Artist(name=a.artist_name, spotify_id=a.spotify_id) for a in artist_rows
        ]

        track_rows = ShowTrack.query.filter_by(show_id=row.id).all()
        track_uris = [t.track_uri for t in track_rows]

        return Show(
            id=row.id,
            venue=row.venue,
            date=row.date,
            created_at=row.created_at,
            ticket_url=row.ticket_url,
            artists=artists,
            track_uris=track_uris,
        )

    # -------------------------------------------------------------------------
    # Playlist-Show Linking
    # -------------------------------------------------------------------------

    def add_show_to_playlist(
        self, playlist_id: str, show_id: str, user_id: str
    ) -> None:
        """Link a show to a playlist."""
        existing = PlaylistShow.query.filter_by(
            playlist_id=playlist_id, show_id=show_id
        ).first()
        if existing:
            return

        now = datetime.now(timezone.utc).isoformat()
        row = PlaylistShow(
            playlist_id=playlist_id,
            show_id=show_id,
            added_at=now,
            added_by_user_id=user_id,
        )
        db.session.add(row)
        db.session.commit()

    def remove_show_from_playlist(self, playlist_id: str, show_id: str) -> None:
        """Unlink a show from a playlist."""
        PlaylistShow.query.filter_by(
            playlist_id=playlist_id, show_id=show_id
        ).delete()
        db.session.commit()

    def get_shows_for_playlist(self, playlist_id: str) -> list[Show]:
        """Get all shows in a playlist."""
        links = PlaylistShow.query.filter_by(playlist_id=playlist_id).all()
        show_ids = [link.show_id for link in links]

        shows = []
        for show_id in show_ids:
            show = self.get_show(show_id)
            if show:
                shows.append(show)
        return shows

    def get_playlists_for_show(self, show_id: str) -> list[Playlist]:
        """Get all playlists containing a show."""
        links = PlaylistShow.query.filter_by(show_id=show_id).all()
        playlist_ids = [link.playlist_id for link in links]

        playlists = []
        for pid in playlist_ids:
            playlist = self.get_playlist(pid)
            if playlist:
                playlists.append(playlist)
        return playlists

    # -------------------------------------------------------------------------
    # Track Queries
    # -------------------------------------------------------------------------

    def is_track_scouted(self, track_uri: str) -> bool:
        """Check if track exists in any show."""
        return ShowTrack.query.filter_by(track_uri=track_uri).first() is not None

    def get_shows_with_track(self, track_uri: str) -> list[str]:
        """Get show IDs containing a track."""
        tracks = ShowTrack.query.filter_by(track_uri=track_uri).all()
        return list(dict.fromkeys(t.show_id for t in tracks))

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

    def record_import(
        self,
        imported_url: ImportedUrl,
        show: Show | None = None,
    ) -> None:
        """Save import record and show together."""
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
        """Love a track for a user. Returns show IDs containing this track."""
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
        """Unlove a track for a user. Returns show IDs containing this track."""
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
        """Get loved track counts per show for a user."""
        if not show_ids:
            return {}

        loved_uris = {
            r.track_uri
            for r in UserLovedTrack.query.filter_by(user_id=user_id).all()
        }
        if not loved_uris:
            return {}

        counts: dict[str, int] = {}
        for show_id in show_ids:
            show_tracks = ShowTrack.query.filter_by(show_id=show_id).all()
            count = sum(1 for t in show_tracks if t.track_uri in loved_uris)
            if count > 0:
                counts[show_id] = count

        return counts

    # -------------------------------------------------------------------------
    # Clear All
    # -------------------------------------------------------------------------

    def clear_all(self) -> None:
        """Wipe all data."""
        PlaylistShow.query.delete()
        ShowArtist.query.delete()
        ShowTrack.query.delete()
        ShowModel.query.delete()
        PlaylistModel.query.delete()
        ImportedUrlModel.query.delete()
        UserLovedTrack.query.delete()
        db.session.commit()
