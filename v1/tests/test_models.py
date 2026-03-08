"""Tests for Pydantic models."""

import pytest

from models import Artist, Show


class TestShowIdComputation:
    """Show.id is computed from natural key (artist spotify_ids + date)."""

    def test_empty_artists_raises(self) -> None:
        """Show requires at least one artist with spotify_id."""
        with pytest.raises(ValueError, match="requires at least one artist"):
            Show(
                venue="The Earl",
                date="2026-03-15",
                created_at="2026-02-15T12:00:00",
                artists=[],
                track_uris=[],
            )

    def test_all_none_spotify_ids_raises(self) -> None:
        """Artists without spotify_ids should raise."""
        with pytest.raises(ValueError, match="requires at least one artist"):
            Show(
                venue="The Earl",
                date="2026-03-15",
                created_at="2026-02-15T12:00:00",
                artists=[
                    Artist(name="Unknown", spotify_id=None),
                    Artist(name="Artist", spotify_id=None),
                ],
                track_uris=[],
            )

    def test_existing_id_preserved(self) -> None:
        """Loading from DB preserves existing ID (doesn't recompute)."""
        show = Show(
            id="existing-id-from-db",
            venue="The Earl",
            date="2026-03-15",
            created_at="2026-02-15T12:00:00",
            artists=[Artist(name="Test", spotify_id="spotify:artist:123")],
            track_uris=[],
        )
        assert show.id == "existing-id-from-db"

    def test_id_computed_from_artists_and_date(self) -> None:
        """ID is computed from artist spotify_ids + date."""
        show1 = Show(
            venue="The Earl",
            date="2026-03-15",
            created_at="2026-02-15T12:00:00",
            artists=[Artist(name="Test", spotify_id="abc123")],
            track_uris=[],
        )
        show2 = Show(
            venue="Different Venue",
            date="2026-03-15",
            created_at="2026-02-16T12:00:00",
            artists=[Artist(name="Test", spotify_id="abc123")],
            track_uris=[],
        )
        # Same artist + date = same ID (regardless of venue)
        assert show1.id == show2.id

    def test_different_date_different_id(self) -> None:
        """Different date = different ID."""
        show1 = Show(
            venue="The Earl",
            date="2026-03-15",
            created_at="2026-02-15T12:00:00",
            artists=[Artist(name="Test", spotify_id="abc123")],
            track_uris=[],
        )
        show2 = Show(
            venue="The Earl",
            date="2026-03-16",
            created_at="2026-02-15T12:00:00",
            artists=[Artist(name="Test", spotify_id="abc123")],
            track_uris=[],
        )
        assert show1.id != show2.id
