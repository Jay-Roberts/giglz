"""Tests for the Database facade.

Tests the SQLAlchemy-backed Database class - single entry point for persistence.
"""

import pytest

from app import app
from extensions import db as flask_db
from db import Database
from models import (
    Show,
    ShowSubmission,
    ImportedUrl,
    ImportStatus,
)


# --- Show constants ---

DEFAULT_SHOW_ID = "test-id-1"
DEFAULT_VENUE = "The Earl"
DEFAULT_DATE = "2026-03-15"
DEFAULT_CREATED_AT = "2026-02-07T12:00:00"
DEFAULT_PLAYLIST_ID = "playlist-abc"

# --- Import constants ---

DEFAULT_URL = "https://songkick.com/concerts/123"
DEFAULT_TIMESTAMP = "2026-02-13T12:00:00"
DEFAULT_SHOW_REF_ID = "show-abc"


# --- Helpers ---


def _make_show(
    artists: list[str],
    show_id: str = DEFAULT_SHOW_ID,
    venue: str = DEFAULT_VENUE,
    date: str = DEFAULT_DATE,
    artist_ids: list[str] | None = None,
    playlist_name: str = "",
    track_uris: list[str] | None = None,
) -> Show:
    """Create a Show for testing."""
    return Show(
        submission=ShowSubmission(artists=artists, venue=venue, date=date),
        id=show_id,
        created_at=DEFAULT_CREATED_AT,
        artist_spotify_ids=artist_ids or ["spotify:artist:fake"] * len(artists),
        track_uris=track_uris or ["spotify:track:fake1", "spotify:track:fake2"],
        playlist_id=DEFAULT_PLAYLIST_ID,
        playlist_name=playlist_name,
    )


def _make_import(
    url: str = DEFAULT_URL,
    status: ImportStatus = ImportStatus.SUCCESS,
    show_id: str | None = DEFAULT_SHOW_REF_ID,
    artist_count: int = 2,
    track_count: int = 6,
    error: str | None = None,
) -> ImportedUrl:
    """Create an ImportedUrl for testing."""
    return ImportedUrl(
        url=url,
        status=status,
        show_id=show_id,
        artist_count=artist_count,
        track_count=track_count,
        error=error,
        attempted_at=DEFAULT_TIMESTAMP,
    )


# --- Fixtures ---


@pytest.fixture()
def test_app(tmp_path):
    """Configure the app with a temp SQLite database."""
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_path}/test.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["TESTING"] = True

    with app.app_context():
        flask_db.create_all()
        yield app
        flask_db.drop_all()


@pytest.fixture()
def db(test_app) -> Database:
    """Provide a fresh Database facade."""
    return Database()


# --- Show Tests ---


class TestShowSaveAndRetrieve:
    """Round-trip: save a show, read it back."""

    def test_save_and_get_all(self, db: Database) -> None:
        show = _make_show(["Militarie Gun"])
        db.save_show(show)

        all_shows = db.get_all_shows()
        assert len(all_shows) == 1
        assert all_shows[0].id == show.id
        assert all_shows[0].submission.artists == ["Militarie Gun"]

    def test_save_multiple_shows(self, db: Database) -> None:
        db.save_show(_make_show(["Kitty Ray"], show_id="id-1"))
        db.save_show(_make_show(["ZULU"], show_id="id-2"))

        all_shows = db.get_all_shows()
        assert len(all_shows) == 2

    def test_submission_fields_round_trip(self, db: Database) -> None:
        show = _make_show(
            ["Kitty Ray", "ZULU"],
            venue="Barboza",
            date="2026-04-01",
        )
        show.submission.ticket_url = "https://tickets.example.com"
        db.save_show(show)

        retrieved = db.get_all_shows()[0]
        assert retrieved.submission.venue == "Barboza"
        assert retrieved.submission.date == "2026-04-01"
        assert retrieved.submission.ticket_url == "https://tickets.example.com"
        assert retrieved.submission.artists == ["Kitty Ray", "ZULU"]

    def test_track_uris_round_trip(self, db: Database) -> None:
        show = _make_show(["Band A"])
        db.save_show(show)

        retrieved = db.get_all_shows()[0]
        assert retrieved.track_uris == ["spotify:track:fake1", "spotify:track:fake2"]


class TestShowGetById:
    """Look up a single show by ID."""

    def test_found(self, db: Database) -> None:
        db.save_show(_make_show(["Militarie Gun"], show_id="abc-123"))
        result = db.get_show("abc-123")

        assert result is not None
        assert result.id == "abc-123"

    def test_not_found(self, db: Database) -> None:
        db.save_show(_make_show(["Militarie Gun"], show_id="abc-123"))
        assert db.get_show("nonexistent") is None


class TestShowEmptyDatabase:
    """Behavior when no shows have been saved."""

    def test_get_all_returns_empty(self, db: Database) -> None:
        assert len(db.get_all_shows()) == 0

    def test_get_by_id_returns_none(self, db: Database) -> None:
        assert db.get_show("anything") is None


class TestShowDeduplication:
    """Shows with same ID are deduplicated (upsert behavior)."""

    def test_same_id_upserts(self, db: Database) -> None:
        """Re-saving show with same ID updates existing show, not duplicate."""
        show1 = _make_show(
            ["Band A"],
            show_id="",
            artist_ids=["spotify:artist:abc123"],
            date="2026-03-15",
        )
        show2 = _make_show(
            ["Band A"],
            show_id="",
            artist_ids=["spotify:artist:abc123"],
            date="2026-03-15",
        )

        db.save_show(show1)
        db.save_show(show2)

        all_shows = db.get_all_shows()
        assert len(all_shows) == 1  # Upserted, not duplicated

    def test_different_ids_creates_two(self, db: Database) -> None:
        """Different show IDs create separate shows."""
        show1 = _make_show(
            ["Band A"],
            show_id="",
            artist_ids=["spotify:artist:abc123"],
            date="2026-03-15",
        )
        show2 = _make_show(
            ["Band A"],
            show_id="",
            artist_ids=["spotify:artist:abc123"],
            date="2026-03-16",  # Different date = different ID
        )

        db.save_show(show1)
        db.save_show(show2)

        all_shows = db.get_all_shows()
        assert len(all_shows) == 2  # Two separate shows


class TestShowByPlaylist:
    """Find shows by playlist name."""

    def test_found(self, db: Database) -> None:
        db.save_show(_make_show(["Band A"], show_id="id-1", playlist_name="ATL-Feb"))
        result = db.get_shows_by_playlist("ATL-Feb")

        assert len(result) == 1
        assert result[0].id == "id-1"

    def test_case_insensitive(self, db: Database) -> None:
        db.save_show(_make_show(["Band A"], show_id="id-1", playlist_name="ATL-Feb"))
        result = db.get_shows_by_playlist("atl-feb")

        assert len(result) == 1

    def test_not_found(self, db: Database) -> None:
        db.save_show(_make_show(["Band A"], show_id="id-1", playlist_name="ATL-Feb"))
        result = db.get_shows_by_playlist("Seattle-Mar")

        assert len(result) == 0

    def test_multiple_shows_same_playlist(self, db: Database) -> None:
        db.save_show(_make_show(["Band A"], show_id="id-1", playlist_name="ATL-Feb"))
        db.save_show(_make_show(["Band B"], show_id="id-2", playlist_name="ATL-Feb"))
        result = db.get_shows_by_playlist("ATL-Feb")

        assert len(result) == 2


class TestGetPlaylists:
    """Get list of unique playlists with counts."""

    def test_returns_playlists_with_counts(self, db: Database) -> None:
        db.save_show(_make_show(["Band A"], show_id="id-1", playlist_name="ATL-Feb"))
        db.save_show(_make_show(["Band B"], show_id="id-2", playlist_name="ATL-Feb"))
        db.save_show(
            _make_show(["Band C"], show_id="id-3", playlist_name="Seattle-Mar")
        )

        playlists = db.get_playlists()

        assert len(playlists) == 2
        atl = next(p for p in playlists if p["name"] == "ATL-Feb")
        seattle = next(p for p in playlists if p["name"] == "Seattle-Mar")

        assert atl["show_count"] == 2
        assert seattle["show_count"] == 1

    def test_skips_shows_without_playlist_name(self, db: Database) -> None:
        db.save_show(_make_show(["Band A"], show_id="id-1", playlist_name="ATL-Feb"))
        db.save_show(_make_show(["Band B"], show_id="id-2", playlist_name=""))

        playlists = db.get_playlists()

        assert len(playlists) == 1
        assert playlists[0]["name"] == "ATL-Feb"

    def test_empty_when_no_shows(self, db: Database) -> None:
        playlists = db.get_playlists()
        assert playlists == []


class TestTrackScouted:
    """Test track lookup."""

    def test_track_found(self, db: Database) -> None:
        db.save_show(_make_show(["Band A"]))
        assert db.is_track_scouted("spotify:track:fake1") is True

    def test_track_not_found(self, db: Database) -> None:
        db.save_show(_make_show(["Band A"]))
        assert db.is_track_scouted("spotify:track:nonexistent") is False


class TestGetShowsWithTrack:
    """Test finding shows containing a track."""

    def test_returns_show_ids(self, db: Database) -> None:
        db.save_show(_make_show(["Band A"], show_id="id-1", track_uris=["track:1"]))
        db.save_show(_make_show(["Band B"], show_id="id-2", track_uris=["track:1"]))
        db.save_show(_make_show(["Band C"], show_id="id-3", track_uris=["track:2"]))

        result = db.get_shows_with_track("track:1")
        assert set(result) == {"id-1", "id-2"}

    def test_empty_when_not_found(self, db: Database) -> None:
        db.save_show(_make_show(["Band A"], show_id="id-1"))
        result = db.get_shows_with_track("nonexistent")
        assert result == []


# --- Import Tests ---


class TestImportSaveAndRetrieve:
    """Round-trip: save an import via record_import, read it back."""

    def test_fields_round_trip_success(self, db: Database) -> None:
        record = _make_import(
            url="https://dice.fm/event/xyz",
            show_id="show-999",
            artist_count=3,
            track_count=9,
        )
        db.record_import(record)

        retrieved = db.get_import("https://dice.fm/event/xyz")
        assert retrieved is not None
        assert retrieved.url == "https://dice.fm/event/xyz"
        assert retrieved.status == ImportStatus.SUCCESS
        assert retrieved.show_id == "show-999"
        assert retrieved.artist_count == 3
        assert retrieved.track_count == 9
        assert retrieved.error is None

    def test_fields_round_trip_failure(self, db: Database) -> None:
        record = _make_import(
            status=ImportStatus.FAILED,
            show_id=None,
            artist_count=0,
            track_count=0,
            error="Could not extract venue, date",
        )
        db.record_import(record)

        retrieved = db.get_import(DEFAULT_URL)
        assert retrieved is not None
        assert retrieved.status == ImportStatus.FAILED
        assert retrieved.show_id is None
        assert retrieved.error == "Could not extract venue, date"


class TestImportGetByUrl:
    """Look up an import record by URL."""

    def test_found(self, db: Database) -> None:
        db.record_import(_make_import(url=DEFAULT_URL))
        result = db.get_import(DEFAULT_URL)

        assert result is not None
        assert result.url == DEFAULT_URL

    def test_not_found(self, db: Database) -> None:
        db.record_import(_make_import(url=DEFAULT_URL))
        assert db.get_import("https://songkick.com/concerts/999") is None


class TestWasImported:
    """Convenience check for successful import."""

    def test_true_for_success(self, db: Database) -> None:
        db.record_import(_make_import(status=ImportStatus.SUCCESS))
        assert db.was_imported(DEFAULT_URL) is True

    def test_false_for_failed(self, db: Database) -> None:
        db.record_import(_make_import(status=ImportStatus.FAILED))
        assert db.was_imported(DEFAULT_URL) is False

    def test_false_for_not_found(self, db: Database) -> None:
        assert db.was_imported("https://never-imported.com") is False


class TestRecordImportWithShow:
    """Test combined save of import + show."""

    def test_saves_both(self, db: Database) -> None:
        show = _make_show(["Band A"], show_id="show-123")
        record = _make_import(show_id="show-123")

        db.record_import(record, show)

        # Both saved
        assert db.get_import(DEFAULT_URL) is not None
        assert db.get_show("show-123") is not None

    def test_saves_import_only_when_no_show(self, db: Database) -> None:
        record = _make_import(status=ImportStatus.FAILED, show_id=None)

        db.record_import(record)

        assert db.get_import(DEFAULT_URL) is not None
        assert len(db.get_all_shows()) == 0


# --- Love Track Tests ---


class TestLoveTrack:
    """Test per-user track loving."""

    def test_love_track(self, db: Database) -> None:
        db.save_show(_make_show(["Band A"], show_id="show-1", track_uris=["track:1"]))

        show_ids = db.love_track("user-123", "track:1", "Song Name", "Artist")

        assert db.is_track_loved("user-123", "track:1") is True
        assert "show-1" in show_ids

    def test_love_track_idempotent(self, db: Database) -> None:
        db.save_show(_make_show(["Band A"], show_id="show-1", track_uris=["track:1"]))

        db.love_track("user-123", "track:1", "Song", "Artist")
        db.love_track("user-123", "track:1", "Song", "Artist")  # Again

        # Still just one love
        loved = db.get_loved_tracks("user-123")
        assert len(loved) == 1

    def test_different_users_love_same_track(self, db: Database) -> None:
        db.save_show(_make_show(["Band A"], track_uris=["track:1"]))

        db.love_track("user-1", "track:1", "Song", "Artist")
        db.love_track("user-2", "track:1", "Song", "Artist")

        assert db.is_track_loved("user-1", "track:1") is True
        assert db.is_track_loved("user-2", "track:1") is True


class TestUnloveTrack:
    """Test unlove functionality."""

    def test_unlove_track(self, db: Database) -> None:
        db.save_show(_make_show(["Band A"], track_uris=["track:1"]))
        db.love_track("user-123", "track:1", "Song", "Artist")

        db.unlove_track("user-123", "track:1")

        assert db.is_track_loved("user-123", "track:1") is False

    def test_unlove_nonexistent_is_noop(self, db: Database) -> None:
        # Should not raise
        db.unlove_track("user-123", "track:never-loved")
        assert db.is_track_loved("user-123", "track:never-loved") is False


class TestGetLovedTracks:
    """Test retrieving user's loved tracks."""

    def test_returns_loved_tracks(self, db: Database) -> None:
        db.save_show(_make_show(["Band A"], track_uris=["track:1", "track:2"]))
        db.love_track("user-123", "track:1", "Song 1", "Artist A")
        db.love_track("user-123", "track:2", "Song 2", "Artist B")

        loved = db.get_loved_tracks("user-123")

        assert len(loved) == 2
        uris = {t.uri for t in loved}
        assert uris == {"track:1", "track:2"}

    def test_empty_for_new_user(self, db: Database) -> None:
        loved = db.get_loved_tracks("new-user")
        assert loved == []


# --- Clear All Tests ---


class TestClearAll:
    """Test clearing all data."""

    def test_clears_shows_and_imports(self, db: Database) -> None:
        db.save_show(_make_show(["Band A"], show_id="id-1"))
        db.record_import(_make_import(url="https://url1.com"))
        db.love_track("user-1", "track:1", "Song", "Artist")

        db.clear_all()

        assert len(db.get_all_shows()) == 0
        assert db.get_import("https://url1.com") is None
        assert db.is_track_loved("user-1", "track:1") is False
