"""Tests for Pydantic models."""

import pytest

from models import Show, ShowSubmission


def _make_submission(
    artists: list[str] | None = None,
    venue: str = "The Earl",
    date: str = "2026-03-15",
) -> ShowSubmission:
    """Create a ShowSubmission for testing."""
    return ShowSubmission(
        artists=artists or ["Test Artist"],
        venue=venue,
        date=date,
    )


class TestShowIdComputation:
    """Show.id is computed from natural key (artist_ids + date)."""

    def test_empty_artist_ids_raises(self) -> None:
        """Show requires at least one valid artist_spotify_id."""
        with pytest.raises(ValueError, match="requires at least one valid"):
            Show(
                submission=_make_submission(),
                created_at="2026-02-15T12:00:00",
                artist_spotify_ids=[],
                track_uris=[],
                playlist_id="pl-123",
            )

    def test_all_empty_string_artist_ids_raises(self) -> None:
        """Artist IDs that are all empty strings should raise."""
        with pytest.raises(ValueError, match="requires at least one valid"):
            Show(
                submission=_make_submission(artists=["Unknown", "Artist"]),
                created_at="2026-02-15T12:00:00",
                artist_spotify_ids=["", ""],  # All lookups failed
                track_uris=[],
                playlist_id="pl-123",
            )

    def test_existing_id_preserved(self) -> None:
        """Loading from DB preserves existing ID (doesn't recompute)."""
        show = Show(
            submission=_make_submission(),
            id="existing-id-from-db",
            created_at="2026-02-15T12:00:00",
            artist_spotify_ids=["spotify:artist:123"],
            track_uris=[],
            playlist_id="pl-123",
        )
        assert show.id == "existing-id-from-db"
