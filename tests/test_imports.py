"""
Import feature tests.

Run with: uv run pytest tests/test_imports.py -v
"""
from dataclasses import dataclass
from io import BytesIO
from unittest.mock import patch, MagicMock

import pytest

# =============================================================================
# EXPECTED REQUEST → RESPONSE PAIRS
# =============================================================================

# GET /import (no session) — redirect to login
UPLOAD_FORM_NO_SESSION_STATUS = 302
UPLOAD_FORM_NO_SESSION_REDIRECT = "/auth/login"

# GET /import (with session) — upload form
UPLOAD_FORM_STATUS = 200
UPLOAD_FORM_CONTAINS = b"Import"

# POST /import (no file) — error
UPLOAD_NO_FILE_STATUS = 302

# POST /import (success) — redirect to shows
UPLOAD_SUCCESS_STATUS = 302
UPLOAD_SUCCESS_REDIRECT = "/shows/"


# =============================================================================
# MOCK DATA
# =============================================================================

@dataclass
class MockArtistSearch:
    spotify_id: str
    name: str
    image_url: str = "https://example.com/image.jpg"
    match_score: float = 95.0


@dataclass
class MockTrackInfo:
    spotify_id: str
    name: str = "Test Track"
    preview_url: str = "https://example.com/preview.mp3"


MOCK_ARTISTS = {
    "Radiohead": MockArtistSearch(spotify_id="spotify_radiohead", name="Radiohead"),
    "Militarie Gun": MockArtistSearch(spotify_id="spotify_militarie", name="Militarie Gun"),
    "ZULU": MockArtistSearch(spotify_id="spotify_zulu", name="ZULU"),
}

MOCK_TRACKS = {
    "spotify_radiohead": [MockTrackInfo(spotify_id="track_radiohead")],
    "spotify_militarie": [MockTrackInfo(spotify_id="track_militarie")],
    "spotify_zulu": [MockTrackInfo(spotify_id="track_zulu")],
}

# Test CSV content
CSV_SINGLE_ARTIST = b"""artists,venue,city,date,ticket_url
Radiohead,The Tabernacle,Atlanta,2026-05-01,https://tickets.com/123
"""

CSV_MULTIPLE_ARTISTS = b'''"artists",venue,city,date,ticket_url
"Militarie Gun, ZULU",The Earl,Atlanta,2026-04-15,
'''

CSV_FLEXIBLE_DATES = b"""artists,venue,city,date,ticket_url
Radiohead,Venue A,City A,2026-04-15,
Radiohead,Venue B,City B,April 20 2026,
Radiohead,Venue C,City C,4/25/26,
"""

CSV_WITH_UNKNOWN_ARTIST = b"""artists,venue,city,date,ticket_url
Unknown Band,The Earl,Atlanta,2026-06-01,
"""

CSV_EMPTY_ROWS = b"""artists,venue,city,date,ticket_url
Radiohead,The Tabernacle,Atlanta,2026-05-01,
,,,,
,The Earl,Atlanta,2026-05-02,
"""


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def authed_client(client, create_user, create_token):
    """Client with authenticated session."""
    user_id, _ = create_user("imports@example.com")
    token = create_token(user_id)
    client.get(f"/auth/verify?token={token}")
    return client


@pytest.fixture
def mock_spotify():
    """Mock SpotifyAPI to avoid real API calls."""
    with patch("services.shows.SpotifyAPI") as mock_class:
        mock_instance = MagicMock()
        mock_instance.search_artist.side_effect = lambda name: MOCK_ARTISTS.get(
            name.strip()
        )
        mock_instance.get_top_tracks.side_effect = lambda aid, limit=5: MOCK_TRACKS.get(
            aid, []
        )
        mock_class.return_value = mock_instance
        yield mock_instance


# =============================================================================
# ROUTE TESTS
# =============================================================================

def test_upload_form_requires_auth(client):
    """GET /import redirects to login when not authed."""
    response = client.get("/import", follow_redirects=False)

    assert response.status_code == UPLOAD_FORM_NO_SESSION_STATUS
    assert UPLOAD_FORM_NO_SESSION_REDIRECT in response.headers.get("Location", "")


def test_upload_form_loads(authed_client):
    """GET /import returns upload form when authed."""
    response = authed_client.get("/import")

    assert response.status_code == UPLOAD_FORM_STATUS
    assert UPLOAD_FORM_CONTAINS in response.data


def test_upload_no_file(authed_client):
    """POST /import without file shows error."""
    response = authed_client.post("/import", data={}, follow_redirects=False)

    assert response.status_code == UPLOAD_NO_FILE_STATUS


def test_upload_success(authed_client, mock_spotify):
    """POST /import with valid CSV creates shows and redirects."""
    response = authed_client.post(
        "/import",
        data={"csv_file": (BytesIO(CSV_SINGLE_ARTIST), "shows.csv")},
        content_type="multipart/form-data",
        follow_redirects=False,
    )

    assert response.status_code == UPLOAD_SUCCESS_STATUS
    assert UPLOAD_SUCCESS_REDIRECT in response.headers.get("Location", "")


# =============================================================================
# SERVICE TESTS
# =============================================================================

def test_parse_csv_single_artist(app, mock_spotify):
    """Parse CSV with single artist per row."""
    from services.imports import ImportService
    from datetime import date

    with app.app_context():
        service = ImportService()
        rows = service._parse_csv(BytesIO(CSV_SINGLE_ARTIST))

        assert len(rows) == 1
        assert rows[0].artists == ["Radiohead"]
        assert rows[0].venue == "The Tabernacle"
        assert rows[0].city == "Atlanta"
        assert rows[0].date == date(2026, 5, 1)


def test_parse_csv_multiple_artists(app, mock_spotify):
    """Parse CSV with comma-separated artists in quotes."""
    from services.imports import ImportService

    with app.app_context():
        service = ImportService()
        rows = service._parse_csv(BytesIO(CSV_MULTIPLE_ARTISTS))

        assert len(rows) == 1
        assert rows[0].artists == ["Militarie Gun", "ZULU"]


def test_parse_csv_flexible_dates(app, mock_spotify):
    """Parse various date formats via dateutil."""
    from services.imports import ImportService
    from datetime import date

    with app.app_context():
        service = ImportService()
        rows = service._parse_csv(BytesIO(CSV_FLEXIBLE_DATES))

        assert len(rows) == 3
        assert rows[0].date == date(2026, 4, 15)
        assert rows[1].date == date(2026, 4, 20)
        assert rows[2].date == date(2026, 4, 25)


def test_parse_csv_skips_empty_rows(app, mock_spotify):
    """Empty rows are skipped during parse."""
    from services.imports import ImportService

    with app.app_context():
        service = ImportService()
        rows = service._parse_csv(BytesIO(CSV_EMPTY_ROWS))

        assert len(rows) == 1


def test_import_creates_batch_and_records(app, authed_client, mock_spotify):
    """Import creates ImportBatch with ImportRecords."""
    from db_models import ImportBatch, ImportRecord, User

    with app.app_context():
        user = User.query.filter_by(email="imports@example.com").first()

        from services.imports import ImportService
        service = ImportService()
        service.import_csv(user.id, BytesIO(CSV_SINGLE_ARTIST))

        batch = ImportBatch.query.first()
        assert batch is not None
        assert batch.user_id == user.id

        records = ImportRecord.query.filter_by(batch_id=batch.id).all()
        assert len(records) == 1


def test_import_creates_shows(app, authed_client, mock_spotify):
    """Successful import creates shows via ShowService."""
    from db_models import Show, User

    with app.app_context():
        user = User.query.filter_by(email="imports@example.com").first()

        from services.imports import ImportService
        service = ImportService()
        result = service.import_csv(user.id, BytesIO(CSV_SINGLE_ARTIST))

        assert result.success == 1
        assert Show.query.count() == 1


def test_import_skips_duplicates(app, authed_client, mock_spotify):
    """Duplicate shows get status=skipped."""
    from db_models import ImportRecord, ImportStatus, User

    with app.app_context():
        user = User.query.filter_by(email="imports@example.com").first()

        from services.imports import ImportService
        service = ImportService()

        # First import
        service.import_csv(user.id, BytesIO(CSV_SINGLE_ARTIST))

        # Second import (duplicate)
        result = service.import_csv(user.id, BytesIO(CSV_SINGLE_ARTIST))

        assert result.skipped == 1
        assert result.success == 0

        skipped_record = ImportRecord.query.filter_by(status=ImportStatus.SKIPPED).first()
        assert skipped_record is not None
        assert skipped_record.error == "Duplicate show"


def test_import_reports_not_found_artists(app, authed_client, mock_spotify):
    """Artists not found on Spotify included in result."""
    from db_models import User

    with app.app_context():
        user = User.query.filter_by(email="imports@example.com").first()

        from services.imports import ImportService
        service = ImportService()
        result = service.import_csv(user.id, BytesIO(CSV_WITH_UNKNOWN_ARTIST))

        assert result.success == 1
        assert "Unknown Band" in result.not_found_artists


def test_import_uses_csv_source(app, authed_client, mock_spotify):
    """Imported shows have source=CSV."""
    from db_models import Show, ShowSource, User

    with app.app_context():
        user = User.query.filter_by(email="imports@example.com").first()

        from services.imports import ImportService
        service = ImportService()
        service.import_csv(user.id, BytesIO(CSV_SINGLE_ARTIST))

        show = Show.query.first()
        assert show.source == ShowSource.CSV
