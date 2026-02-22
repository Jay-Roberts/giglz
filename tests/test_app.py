"""Tests for URL import functions in app.py."""

from unittest.mock import Mock, patch
import pytest

from app import app, extract_data_from_urls, process_single_url
from extensions import db as flask_db
from models import ImportedUrl, ImportStatus, Show, ShowSubmission


def _make_show(show_id: str = "test-id", artists: list[str] | None = None) -> Show:
    """Helper to create a Show for testing."""
    if artists is None:
        artists = ["Test Artist"]
    return Show(
        submission=ShowSubmission(
            artists=artists,
            venue="Test Venue",
            date="2026-03-15",
            ticket_url="https://example.com/event",
        ),
        id=show_id,
        created_at="2026-02-13T12:00:00Z",
        artist_spotify_ids=["spotify:artist:123"],
        track_uris=["spotify:track:1", "spotify:track:2"],
        playlist_id="playlist-123",
    )


@pytest.fixture
def test_app(tmp_path):
    """Configure the app with a temp SQLite database."""
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_path}/test.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["TESTING"] = True

    with app.app_context():
        flask_db.create_all()
        yield app
        flask_db.drop_all()


@pytest.fixture
def mock_db():
    """Mock Database facade."""
    return Mock()


class TestExtractDataFromUrls:
    @patch("app._import_url")
    @patch("app.get_db")
    def test_returns_shows_on_success(self, mock_get_db, mock_import_url, test_app):
        mock_db = Mock()
        mock_db.get_import.return_value = None
        mock_get_db.return_value = mock_db
        mock_import_url.return_value = _make_show()

        shows, imported_urls, failures, skipped = extract_data_from_urls(
            ["https://example.com/event"]
        )

        assert len(shows) == 1
        assert len(imported_urls) == 1
        assert imported_urls[0].status == ImportStatus.SUCCESS
        assert len(failures) == 0
        assert len(skipped) == 0

    @patch("app._import_url")
    @patch("app.get_db")
    def test_skips_already_imported_urls(self, mock_get_db, mock_import_url, test_app):
        mock_db = Mock()
        mock_db.get_import.return_value = ImportedUrl(
            url="https://example.com/event",
            status=ImportStatus.SUCCESS,
            show_id="existing-id",
            attempted_at="2026-02-12T12:00:00Z",
            error=None,
        )
        mock_get_db.return_value = mock_db

        shows, imported_urls, failures, skipped = extract_data_from_urls(
            ["https://example.com/event"]
        )

        assert len(shows) == 0
        assert len(imported_urls) == 0
        assert len(failures) == 0
        assert len(skipped) == 1
        assert skipped[0] == "https://example.com/event"
        mock_import_url.assert_not_called()

    @patch("app._import_url")
    @patch("app.get_db")
    def test_retries_failed_urls(self, mock_get_db, mock_import_url, test_app):
        mock_db = Mock()
        mock_db.get_import.return_value = ImportedUrl(
            url="https://example.com/event",
            status=ImportStatus.FAILED,
            show_id=None,
            error="Previous error",
            attempted_at="2026-02-12T12:00:00Z",
        )
        mock_get_db.return_value = mock_db
        mock_import_url.return_value = _make_show()

        shows, imported_urls, failures, skipped = extract_data_from_urls(
            ["https://example.com/event"]
        )

        assert len(shows) == 1
        assert len(skipped) == 0
        mock_import_url.assert_called_once()

    @patch("app._import_url")
    @patch("app.get_db")
    def test_records_failures(self, mock_get_db, mock_import_url, test_app):
        mock_db = Mock()
        mock_db.get_import.return_value = None
        mock_get_db.return_value = mock_db
        mock_import_url.side_effect = ValueError("Could not extract artists")

        shows, imported_urls, failures, skipped = extract_data_from_urls(
            ["https://example.com/event"]
        )

        assert len(shows) == 0
        assert len(imported_urls) == 1
        assert imported_urls[0].status == ImportStatus.FAILED
        assert imported_urls[0].error == "Could not extract artists"
        assert len(failures) == 1
        assert "Could not extract artists" in failures[0]

    @patch("app._import_url")
    @patch("app.get_db")
    def test_handles_multiple_urls(self, mock_get_db, mock_import_url, test_app):
        mock_db = Mock()
        # First URL: success, Second URL: already imported, Third URL: fails
        mock_db.get_import.side_effect = [
            None,
            ImportedUrl(
                url="https://example.com/event2",
                status=ImportStatus.SUCCESS,
                show_id="existing",
                attempted_at="2026-02-12T12:00:00Z",
                error=None,
            ),
            None,
        ]
        mock_get_db.return_value = mock_db
        mock_import_url.side_effect = [
            _make_show(show_id="show-1"),
            ValueError("Bot protection"),
        ]

        shows, imported_urls, failures, skipped = extract_data_from_urls(
            [
                "https://example.com/event1",
                "https://example.com/event2",
                "https://example.com/event3",
            ]
        )

        assert len(shows) == 1
        assert shows[0].id == "show-1"
        assert len(skipped) == 1
        assert len(failures) == 1
        assert "Bot protection" in failures[0]
        assert len(imported_urls) == 2  # success + failure, not skipped

    @patch("app._import_url")
    @patch("app.get_db")
    def test_normalizes_urls_for_dedup(self, mock_get_db, mock_import_url, test_app):
        mock_db = Mock()
        mock_db.get_import.return_value = None
        mock_get_db.return_value = mock_db
        mock_import_url.return_value = _make_show()

        extract_data_from_urls(["https://WWW.Example.COM/event?utm_source=twitter"])

        # Should normalize before checking DB
        mock_db.get_import.assert_called_once_with("https://example.com/event")

    @patch("app._import_url")
    @patch("app.get_db")
    def test_imported_url_has_correct_fields(
        self, mock_get_db, mock_import_url, test_app
    ):
        mock_db = Mock()
        mock_db.get_import.return_value = None
        mock_get_db.return_value = mock_db
        show = _make_show(show_id="test-123", artists=["Artist 1", "Artist 2"])
        show.track_uris = ["t1", "t2", "t3"]
        mock_import_url.return_value = show

        shows, imported_urls, failures, skipped = extract_data_from_urls(
            ["https://example.com/event"]
        )

        imported = imported_urls[0]
        assert imported.status == ImportStatus.SUCCESS
        assert imported.show_id == "test-123"
        assert imported.artist_count == 2
        assert imported.track_count == 3
        assert imported.error is None
        assert imported.attempted_at is not None


class TestProcessSingleUrl:
    @patch("app._import_url")
    @patch("app.get_db")
    def test_returns_success_for_new_url(self, mock_get_db, mock_import_url, test_app):
        mock_db = Mock()
        mock_db.get_import.return_value = None
        mock_get_db.return_value = mock_db
        mock_import_url.return_value = _make_show(show_id="new-show")

        show, imported_url = process_single_url("https://example.com/event")

        assert show is not None
        assert show.id == "new-show"
        assert imported_url.status == ImportStatus.SUCCESS
        assert imported_url.show_id == "new-show"

    @patch("app._import_url")
    @patch("app.get_db")
    def test_returns_skipped_for_already_imported(
        self, mock_get_db, mock_import_url, test_app
    ):
        mock_db = Mock()
        mock_db.get_import.return_value = ImportedUrl(
            url="https://example.com/event",
            status=ImportStatus.SUCCESS,
            show_id="existing-id",
            artist_count=2,
            track_count=5,
            attempted_at="2026-02-12T12:00:00Z",
            error=None,
        )
        mock_get_db.return_value = mock_db

        show, imported_url = process_single_url("https://example.com/event")

        assert show is None
        assert imported_url.status == ImportStatus.SKIPPED
        assert imported_url.show_id == "existing-id"
        assert imported_url.artist_count == 2
        assert imported_url.track_count == 5
        mock_import_url.assert_not_called()

    @patch("app._import_url")
    @patch("app.get_db")
    def test_returns_failed_on_error(self, mock_get_db, mock_import_url, test_app):
        mock_db = Mock()
        mock_db.get_import.return_value = None
        mock_get_db.return_value = mock_db
        mock_import_url.side_effect = ValueError("Bot protection detected")

        show, imported_url = process_single_url("https://example.com/event")

        assert show is None
        assert imported_url.status == ImportStatus.FAILED
        assert imported_url.error == "Bot protection detected"

    @patch("app._import_url")
    @patch("app.get_db")
    def test_retries_previously_failed_url(
        self, mock_get_db, mock_import_url, test_app
    ):
        mock_db = Mock()
        mock_db.get_import.return_value = ImportedUrl(
            url="https://example.com/event",
            status=ImportStatus.FAILED,
            show_id=None,
            error="Previous error",
            attempted_at="2026-02-12T12:00:00Z",
        )
        mock_get_db.return_value = mock_db
        mock_import_url.return_value = _make_show(show_id="retry-success")

        show, imported_url = process_single_url("https://example.com/event")

        assert show is not None
        assert show.id == "retry-success"
        assert imported_url.status == ImportStatus.SUCCESS
        mock_import_url.assert_called_once()

    @patch("app._import_url")
    @patch("app.get_db")
    def test_normalizes_url_before_dedup_check(
        self, mock_get_db, mock_import_url, test_app
    ):
        mock_db = Mock()
        mock_db.get_import.return_value = None
        mock_get_db.return_value = mock_db
        mock_import_url.return_value = _make_show()

        process_single_url("https://WWW.Example.COM/event?utm_source=foo")

        mock_db.get_import.assert_called_once_with("https://example.com/event")
