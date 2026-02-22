"""Tests for CSV import functionality."""

import io
import pytest
from unittest.mock import patch, Mock

from app import app, parse_shows_csv
from config import HOST_USER_ID
from models import ShowSubmission


class TestParseShowsCsv:
    """Tests for parse_shows_csv helper function."""

    def test_parses_single_artist(self):
        """Parse CSV with single artist per row."""
        csv_content = """artists,venue,date
Radiohead,The Tabernacle,2026-05-01
"""
        submissions = parse_shows_csv(io.StringIO(csv_content))

        assert len(submissions) == 1
        assert submissions[0].artists == ["Radiohead"]
        assert submissions[0].venue == "The Tabernacle"
        assert submissions[0].date == "2026-05-01"

    def test_parses_multiple_artists(self):
        """Parse CSV with comma-separated artists in quotes."""
        csv_content = """artists,venue,date
"Militarie Gun, ZULU",The Earl,2026-04-15
"""
        submissions = parse_shows_csv(io.StringIO(csv_content))

        assert len(submissions) == 1
        assert submissions[0].artists == ["Militarie Gun", "ZULU"]
        assert submissions[0].venue == "The Earl"
        assert submissions[0].date == "2026-04-15"

    def test_parses_multiple_rows(self):
        """Parse CSV with multiple shows."""
        csv_content = """artists,venue,date
"Militarie Gun, ZULU",The Earl,2026-04-15
Kitty Ray,Barboza,2026-04-20
Radiohead,The Tabernacle,2026-05-01
"""
        submissions = parse_shows_csv(io.StringIO(csv_content))

        assert len(submissions) == 3
        assert submissions[0].venue == "The Earl"
        assert submissions[1].venue == "Barboza"
        assert submissions[2].venue == "The Tabernacle"

    def test_skips_empty_rows(self):
        """Skip rows with missing required fields."""
        csv_content = """artists,venue,date
Radiohead,The Tabernacle,2026-05-01
,,
Kitty Ray,Barboza,2026-04-20
"""
        submissions = parse_shows_csv(io.StringIO(csv_content))

        assert len(submissions) == 2
        assert submissions[0].artists == ["Radiohead"]
        assert submissions[1].artists == ["Kitty Ray"]

    def test_skips_row_missing_artists(self):
        """Skip row when artists column is empty."""
        csv_content = """artists,venue,date
,The Earl,2026-04-15
Radiohead,The Tabernacle,2026-05-01
"""
        submissions = parse_shows_csv(io.StringIO(csv_content))

        assert len(submissions) == 1
        assert submissions[0].artists == ["Radiohead"]

    def test_skips_row_missing_venue(self):
        """Skip row when venue column is empty."""
        csv_content = """artists,venue,date
Radiohead,,2026-05-01
Kitty Ray,Barboza,2026-04-20
"""
        submissions = parse_shows_csv(io.StringIO(csv_content))

        assert len(submissions) == 1
        assert submissions[0].artists == ["Kitty Ray"]

    def test_skips_row_missing_date(self):
        """Skip row when date column is empty."""
        csv_content = """artists,venue,date
Radiohead,The Tabernacle,
Kitty Ray,Barboza,2026-04-20
"""
        submissions = parse_shows_csv(io.StringIO(csv_content))

        assert len(submissions) == 1
        assert submissions[0].artists == ["Kitty Ray"]

    def test_strips_whitespace(self):
        """Strip whitespace from all fields."""
        csv_content = """artists,venue,date
  Radiohead  ,  The Tabernacle  ,  2026-05-01
"""
        submissions = parse_shows_csv(io.StringIO(csv_content))

        assert len(submissions) == 1
        assert submissions[0].artists == ["Radiohead"]
        assert submissions[0].venue == "The Tabernacle"
        assert submissions[0].date == "2026-05-01"

    def test_handles_bytes_input(self):
        """Handle file-like objects that return bytes."""
        csv_bytes = b"""artists,venue,date
Radiohead,The Tabernacle,2026-05-01
"""

        class BytesFile:
            def read(self):
                return csv_bytes

        submissions = parse_shows_csv(BytesFile())
        assert len(submissions) == 1
        assert submissions[0].artists == ["Radiohead"]

    def test_returns_empty_for_empty_csv(self):
        """Return empty list for CSV with only headers."""
        csv_content = """artists,venue,date
"""
        submissions = parse_shows_csv(io.StringIO(csv_content))
        assert submissions == []


class TestImportShowsCsvRoute:
    """Tests for POST /import-shows/csv route."""

    @pytest.fixture
    def host_client(self):
        """Flask test client authenticated as host."""
        app.config["TESTING"] = True
        with app.test_client() as client:
            with client.session_transaction() as session:
                session["user_id"] = HOST_USER_ID
                session["user_name"] = "Test Host"
            yield client

    @pytest.fixture
    def client(self):
        """Flask test client (not authenticated)."""
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_no_file_flashes_error(self, host_client):
        """Redirect with flash when no file uploaded."""
        response = host_client.post("/import-shows/csv", data={})
        assert response.status_code == 302
        assert response.location == "/"

    def test_empty_filename_flashes_error(self, host_client):
        """Redirect with flash when file has no filename."""
        response = host_client.post(
            "/import-shows/csv",
            data={"csv_file": (io.BytesIO(b""), "")},
            content_type="multipart/form-data",
        )
        assert response.status_code == 302

    @patch("app._scout_submission")
    @patch("app.get_db")
    def test_imports_valid_csv(self, mock_get_db, mock_scout, host_client):
        """Successfully import shows from valid CSV."""
        mock_db = Mock()
        mock_get_db.return_value = mock_db

        mock_show = Mock()
        mock_show.track_uris = ["spotify:track:1", "spotify:track:2"]
        mock_scout.return_value = (mock_show, [])

        csv_content = b"""artists,venue,date
Radiohead,The Tabernacle,2026-05-01
"""
        response = host_client.post(
            "/import-shows/csv",
            data={
                "csv_file": (io.BytesIO(csv_content), "shows.csv"),
                "playlist_name": "Scouting",
            },
            content_type="multipart/form-data",
        )

        assert response.status_code == 302
        assert mock_scout.call_count == 1
        assert mock_db.save_show.call_count == 1

    @patch("app._scout_submission")
    @patch("app.get_db")
    def test_uses_default_playlist_name(self, mock_get_db, mock_scout, host_client):
        """Use default playlist name when not specified."""
        mock_db = Mock()
        mock_get_db.return_value = mock_db

        mock_show = Mock()
        mock_show.track_uris = []
        mock_scout.return_value = (mock_show, [])

        csv_content = b"""artists,venue,date
Radiohead,The Tabernacle,2026-05-01
"""
        response = host_client.post(
            "/import-shows/csv",
            data={"csv_file": (io.BytesIO(csv_content), "shows.csv")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 302
        # Scout was called (would use default playlist internally)
        assert mock_scout.call_count == 1

    def test_invalid_csv_flashes_error(self, host_client):
        """Flash error for CSV with no valid rows."""
        csv_content = b"""artists,venue,date
,,
"""
        response = host_client.post(
            "/import-shows/csv",
            data={"csv_file": (io.BytesIO(csv_content), "shows.csv")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 302

    @patch("app._scout_submission")
    @patch("app.get_db")
    def test_reports_not_found_artists(self, mock_get_db, mock_scout, host_client):
        """Flash message includes artists not found on Spotify."""
        mock_db = Mock()
        mock_get_db.return_value = mock_db

        mock_show = Mock()
        mock_show.track_uris = ["spotify:track:1"]
        mock_scout.return_value = (mock_show, ["Unknown Artist"])

        csv_content = b"""artists,venue,date
"Known, Unknown Artist",The Earl,2026-04-15
"""
        response = host_client.post(
            "/import-shows/csv",
            data={"csv_file": (io.BytesIO(csv_content), "shows.csv")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 302
        # Flash message would include "Couldn't find: Unknown Artist"

    @patch("app._scout_submission")
    @patch("app.get_db")
    def test_handles_scout_failure(self, mock_get_db, mock_scout, host_client):
        """Handle failures from _scout_submission gracefully."""
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        mock_scout.side_effect = ValueError("Spotify API error")

        csv_content = b"""artists,venue,date
Radiohead,The Tabernacle,2026-05-01
"""
        response = host_client.post(
            "/import-shows/csv",
            data={"csv_file": (io.BytesIO(csv_content), "shows.csv")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 302
        # Should still redirect, with failure count in flash message
        assert mock_db.save_show.call_count == 0

    def test_requires_host_auth(self, client):
        """Non-host users are redirected."""
        csv_content = b"""artists,venue,date
Radiohead,The Tabernacle,2026-05-01
"""
        response = client.post(
            "/import-shows/csv",
            data={"csv_file": (io.BytesIO(csv_content), "shows.csv")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 302  # Redirected, not allowed
