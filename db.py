"""Database facade - single entry point for all persistence."""

import uuid
from datetime import datetime, timezone

from extensions import db
from db_models import (
    ShowList as ShowListModel,
    Show as ShowModel,
    ShowArtist,
    ShowTrack,
    ShowListShow,
    ImportedUrl as ImportedUrlModel,
    UserLovedTrack,
)
from models import (
    Artist,
    Show,
    ShowList,
    ImportedUrl,
    ImportStatus,
    LovedTrack,
)

DEFAULT_SHOWLIST_NAME = "giglz"


class Database:
    """Single entry point for all persistence operations."""

    # -------------------------------------------------------------------------
    # ShowLists
    # -------------------------------------------------------------------------

    def create_showlist(self, name: str, owner_user_id: str) -> ShowList:
        """Create a new showlist with a unique name.

        If a showlist with the given name already exists, appends -2, -3, etc.
        """
        final_name = name
        suffix = 2
        while self.get_showlist_by_name(final_name):
            final_name = f"{name}-{suffix}"
            suffix += 1

        showlist_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        row = ShowListModel(
            id=showlist_id,
            name=final_name,
            owner_user_id=owner_user_id,
            created_at=now,
        )
        db.session.add(row)
        db.session.commit()

        return ShowList(
            id=showlist_id,
            name=final_name,
            owner_user_id=owner_user_id,
            created_at=now,
            spotify_playlist_id=None,
        )

    def get_showlist(self, showlist_id: str) -> ShowList | None:
        """Get showlist by ID."""
        row = ShowListModel.query.filter_by(id=showlist_id).first()
        if not row:
            return None
        return self._row_to_showlist(row)

    def get_showlist_by_name(self, name: str) -> ShowList | None:
        """Get showlist by name (case-insensitive)."""
        row = ShowListModel.query.filter(
            db.func.lower(ShowListModel.name) == name.lower()
        ).first()
        if not row:
            return None
        return self._row_to_showlist(row)

    def get_all_showlists(self) -> list[ShowList]:
        """Get all showlists."""
        rows = ShowListModel.query.order_by(ShowListModel.created_at).all()
        return [self._row_to_showlist(r) for r in rows]

    def get_or_create_default_showlist(self, owner_user_id: str) -> ShowList:
        """Get the default showlist, creating it if it doesn't exist."""
        showlist = self.get_showlist_by_name(DEFAULT_SHOWLIST_NAME)
        if showlist:
            return showlist
        return self.create_showlist(DEFAULT_SHOWLIST_NAME, owner_user_id)

    def update_showlist_spotify_id(
        self, showlist_id: str, spotify_playlist_id: str | None
    ) -> None:
        """Link a Giglz showlist to a Spotify playlist.

        Called when:
        - First sync: Giglz showlist exists, Spotify playlist just created
        - Re-sync: Spotify playlist was deleted, new one created

        Set to None to clear the link (e.g., if Spotify playlist is gone).
        """
        row = ShowListModel.query.filter_by(id=showlist_id).first()
        if row:
            row.spotify_playlist_id = spotify_playlist_id
            db.session.commit()

    def _row_to_showlist(self, row: ShowListModel) -> ShowList:
        """Convert DB row to Pydantic model."""
        return ShowList(
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

    def get_all_shows(
        self,
        sort: str = "date",
        user_id: str | None = None,
    ) -> list[Show]:
        """Get all shows with sorting.

        Args:
            sort: Sort order - "date" (ascending), "hearts" (descending),
                  or "combined" (upcoming shows with hearts first).
            user_id: Required for "hearts" and "combined" sort to count loved tracks.

        Returns:
            List of Show objects with loved_tracks populated if user_id provided.
        """
        rows = ShowModel.query.all()
        shows = [self._row_to_show(r) for r in rows]

        # Populate loved_tracks if user_id provided
        if user_id:
            loved_uris = {
                r.track_uri
                for r in UserLovedTrack.query.filter_by(user_id=user_id).all()
            }
            for show in shows:
                show.loved_tracks = [
                    uri for uri in show.track_uris if uri in loved_uris
                ]

        # Apply sorting
        if sort == "hearts" and user_id:
            shows.sort(key=lambda s: len(s.loved_tracks or []), reverse=True)
        elif sort == "combined" and user_id:
            shows.sort(
                key=lambda s: (
                    0 if s.loved_tracks else 1,
                    -len(s.loved_tracks or []),
                    s.date or "",
                )
            )
        else:
            # Default: sort by date ascending
            shows.sort(key=lambda s: s.date or "")

        return shows

    def _row_to_show(self, row: ShowModel) -> Show:
        """Reconstruct Show from normalized DB rows."""
        artist_rows = (
            ShowArtist.query.filter_by(show_id=row.id)
            .order_by(ShowArtist.position)
            .all()
        )
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
    # ShowList-Show Linking
    # -------------------------------------------------------------------------

    def add_show_to_showlist(
        self, showlist_id: str, show_id: str, user_id: str
    ) -> None:
        """Link a show to a showlist."""
        existing = ShowListShow.query.filter_by(
            showlist_id=showlist_id, show_id=show_id
        ).first()
        if existing:
            return

        now = datetime.now(timezone.utc).isoformat()
        row = ShowListShow(
            showlist_id=showlist_id,
            show_id=show_id,
            added_at=now,
            added_by_user_id=user_id,
        )
        db.session.add(row)
        db.session.commit()

    def remove_show_from_showlist(self, showlist_id: str, show_id: str) -> None:
        """Unlink a show from a showlist."""
        ShowListShow.query.filter_by(showlist_id=showlist_id, show_id=show_id).delete()
        db.session.commit()

    def get_shows_for_showlist(
        self,
        showlist_id: str,
        sort: str = "date",
        user_id: str | None = None,
    ) -> list[Show]:
        """Get all shows in a showlist with sorting.

        Args:
            showlist_id: The showlist to query.
            sort: Sort order - "date" (ascending), "hearts" (descending),
                  or "combined" (upcoming shows with hearts first).
            user_id: Required for "hearts" and "combined" sort to count loved tracks.

        Returns:
            List of Show objects with loved_tracks populated if user_id provided.
        """
        links = ShowListShow.query.filter_by(showlist_id=showlist_id).all()
        show_ids = [link.show_id for link in links]

        shows = []
        for show_id in show_ids:
            show = self.get_show(show_id)
            if show:
                shows.append(show)

        # Populate loved_tracks if user_id provided
        if user_id:
            loved_uris = {
                r.track_uri
                for r in UserLovedTrack.query.filter_by(user_id=user_id).all()
            }
            for show in shows:
                show.loved_tracks = [
                    uri for uri in show.track_uris if uri in loved_uris
                ]

        # Apply sorting
        if sort == "hearts" and user_id:
            # Sort by loved track count descending
            shows.sort(key=lambda s: len(s.loved_tracks or []), reverse=True)
        elif sort == "combined" and user_id:
            # Sort: shows with hearts first (by hearts desc), then by date
            shows.sort(
                key=lambda s: (
                    0 if s.loved_tracks else 1,  # Has hearts first
                    -len(s.loved_tracks or []),  # Then by heart count desc
                    s.date or "",  # Then by date asc
                )
            )
        else:
            # Default: sort by date ascending
            shows.sort(key=lambda s: s.date or "")

        return shows

    def get_showlists_for_show(self, show_id: str) -> list[ShowList]:
        """Get all showlists containing a show."""
        links = ShowListShow.query.filter_by(show_id=show_id).all()
        showlist_ids = [link.showlist_id for link in links]

        showlists = []
        for sid in showlist_ids:
            showlist = self.get_showlist(sid)
            if showlist:
                showlists.append(showlist)
        return showlists

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
            r.track_uri for r in UserLovedTrack.query.filter_by(user_id=user_id).all()
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
        ShowListShow.query.delete()
        ShowArtist.query.delete()
        ShowTrack.query.delete()
        ShowModel.query.delete()
        ShowListModel.query.delete()
        ImportedUrlModel.query.delete()
        UserLovedTrack.query.delete()
        db.session.commit()
