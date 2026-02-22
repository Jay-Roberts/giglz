"""Tests for the Spotify client interface.

Mocks the spotipy.Spotify instance so tests run offline.
"""

from unittest.mock import MagicMock, patch

import pytest

from spotify import ArtistSearch, ArtistTopTrack, SpotifyAPI, UserPlaylist
from spotify.client import _playlist_cache

# Backwards compatibility alias for tests
SpotifyClient = SpotifyAPI


# -- Fake Spotify API responses (minimal, matching real shapes) ---------------


def _make_playlist_response(
    name: str = "Scouting",
    playlist_id: str = "pl-1",
    owner_id: str = "user-1",
) -> dict:
    """A single playlist object as returned by the Spotify API."""
    return {
        "name": name,
        "id": playlist_id,
        "owner": {
            "id": owner_id,
            "display_name": "testuser",
            "external_urls": {"spotify": f"https://open.spotify.com/user/{owner_id}"},
        },
        "external_urls": {
            "spotify": f"https://open.spotify.com/playlist/{playlist_id}"
        },
    }


def _make_playlists_page(playlists: list[dict]) -> dict:
    """A current_user_playlists page response."""
    return {
        "items": playlists,
        "total": len(playlists),
        "limit": 50,
        "offset": 0,
        "next": None,
        "previous": None,
    }


def _make_artist_item(name: str, artist_id: str) -> dict:
    """A single artist item from search results."""
    return {
        "name": name,
        "id": artist_id,
        "external_urls": {"spotify": f"https://open.spotify.com/artist/{artist_id}"},
    }


def _make_search_response(
    name: str = "kitty ray",
    artist_id: str = "artist-1",
) -> dict:
    """A sp.search(type='artist') response with one result."""
    return {"artists": {"items": [_make_artist_item(name, artist_id)]}}


def _make_multi_search_response(artists: list[tuple[str, str]]) -> dict:
    """A sp.search(type='artist') response with multiple results.

    Args:
        artists: List of (name, id) tuples.
    """
    return {"artists": {"items": [_make_artist_item(n, i) for n, i in artists]}}


def _make_track(
    track_name: str = "Counting All The Starfish",
    track_id: str = "track-1",
    artist_name: str = "kitty ray",
) -> dict:
    """A single track object from artist_top_tracks."""
    return {
        "name": track_name,
        "id": track_id,
        "uri": f"spotify:track:{track_id}",
        "artists": [{"name": artist_name}],
    }


def _make_top_tracks_response(tracks: list[dict] | None = None) -> dict:
    """A sp.artist_top_tracks response."""
    if tracks is None:
        tracks = [
            _make_track("Counting All The Starfish", "track-1"),
            _make_track("Last Minute", "track-2"),
            _make_track("Still Miss U", "track-3"),
        ]
    return {"tracks": tracks}


# -- Fixtures -----------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_playlist_cache():
    """Clear the global playlist cache before each test."""
    _playlist_cache._cache.clear()


@pytest.fixture()
def mock_sp() -> MagicMock:
    """A mocked spotipy.Spotify instance with sensible defaults."""
    sp = MagicMock()
    sp.current_user.return_value = {"id": "user-1"}
    sp.current_user_playlists.return_value = _make_playlists_page(
        [_make_playlist_response("Scouting", "pl-1")]
    )
    return sp


@pytest.fixture()
def client(mock_sp: MagicMock) -> SpotifyClient:
    """A SpotifyClient wired to the mock_sp fixture."""
    with patch("spotify.client.spotipy.Spotify", return_value=mock_sp):
        return SpotifyClient(token="fake-token")


# -- Tests --------------------------------------------------------------------


class TestInit:
    """SpotifyClient initialization."""

    def test_sets_user_id(self, client: SpotifyClient) -> None:
        assert client._user_id == "user-1"

    def test_loads_playlists(self, client: SpotifyClient) -> None:
        playlists = client.get_user_playlists(use_cache=False)
        assert len(playlists) == 1
        assert playlists[0].name == "Scouting"

    def test_raises_when_no_user(self, mock_sp: MagicMock) -> None:
        mock_sp.current_user.return_value = None
        with patch("spotify.client.spotipy.Spotify", return_value=mock_sp):
            with pytest.raises(ValueError, match="Failed to get user info"):
                SpotifyClient(token="fake-token")

    def test_pagination_stops_on_short_page(self) -> None:
        sp = MagicMock()
        sp.current_user.return_value = {"id": "user-1"}
        # Return fewer items than the limit — should stop after one page
        sp.current_user_playlists.return_value = _make_playlists_page(
            [_make_playlist_response("A", "pl-a")]
        )
        with patch("spotify.client.spotipy.Spotify", return_value=sp):
            c = SpotifyClient(token="fake-token")
        playlists = c.get_user_playlists(use_cache=False)
        assert sp.current_user_playlists.call_count == 1
        assert len(playlists) == 1


class TestSearchArtist:
    """search_artist — fuzzy-matched artist lookup."""

    def test_found_exact_match(self, client: SpotifyClient, mock_sp: MagicMock) -> None:
        mock_sp.search.return_value = _make_search_response("kitty ray", "art-1")
        result = client.search_artist("kitty ray")

        assert result is not None
        assert isinstance(result, ArtistSearch)
        assert result.name == "kitty ray"
        assert result.id == "art-1"
        assert "art-1" in result.url
        assert result.match_score == 100.0

    def test_returns_best_fuzzy_match(
        self, client: SpotifyClient, mock_sp: MagicMock
    ) -> None:
        """Should return highest-scoring candidate, not first result."""
        mock_sp.search.return_value = _make_multi_search_response(
            [
                ("ZULU Warriors", "wrong"),  # Lower score
                ("ZULU", "correct"),  # Exact match
            ]
        )
        result = client.search_artist("ZULU")

        assert result is not None
        assert result.id == "correct"
        assert result.name == "ZULU"

    def test_rejects_low_confidence_match(
        self, client: SpotifyClient, mock_sp: MagicMock
    ) -> None:
        """Should return None if best match is below threshold."""
        mock_sp.search.return_value = _make_multi_search_response(
            [
                ("Completely Different Artist", "art-1"),
            ]
        )
        result = client.search_artist("ZULU")

        assert result is None

    def test_not_found_empty_items(
        self, client: SpotifyClient, mock_sp: MagicMock
    ) -> None:
        mock_sp.search.return_value = {"artists": {"items": []}}
        assert client.search_artist("nonexistent") is None

    def test_not_found_none_response(
        self, client: SpotifyClient, mock_sp: MagicMock
    ) -> None:
        mock_sp.search.return_value = None
        assert client.search_artist("nonexistent") is None


class TestScoreArtistMatch:
    """_score_artist_match — fuzzy string matching."""

    def test_exact_match_scores_100(self, client: SpotifyClient) -> None:
        score = client._score_artist_match("Radiohead", "Radiohead")
        assert score == 100.0

    def test_case_insensitive(self, client: SpotifyClient) -> None:
        score = client._score_artist_match("radiohead", "RADIOHEAD")
        assert score == 100.0

    def test_similar_names_score_high(self, client: SpotifyClient) -> None:
        score = client._score_artist_match("Radiohead", "Radio Head")
        assert score > 80

    def test_unrelated_names_score_low(self, client: SpotifyClient) -> None:
        score = client._score_artist_match("Radiohead", "Taylor Swift")
        assert score < 50


class TestGetTopTracks:
    """get_top_tracks — top N tracks for an artist."""

    def test_returns_tracks(self, client: SpotifyClient, mock_sp: MagicMock) -> None:
        mock_sp.artist_top_tracks.return_value = _make_top_tracks_response()
        result = client.get_top_tracks("art-1", limit=2)

        assert result is not None
        assert len(result) == 2
        assert isinstance(result[0], ArtistTopTrack)
        assert result[0].track == "Counting All The Starfish"
        assert result[0].uri == "spotify:track:track-1"

    def test_respects_limit(self, client: SpotifyClient, mock_sp: MagicMock) -> None:
        tracks = [_make_track(f"Song {i}", f"t-{i}") for i in range(10)]
        mock_sp.artist_top_tracks.return_value = _make_top_tracks_response(tracks)
        result = client.get_top_tracks("art-1", limit=5)

        assert result is not None
        assert len(result) == 5

    def test_limit_over_10_raises(self, client: SpotifyClient) -> None:
        with pytest.raises(ValueError, match="ten tracks"):
            client.get_top_tracks("art-1", limit=11)

    def test_none_response(self, client: SpotifyClient, mock_sp: MagicMock) -> None:
        mock_sp.artist_top_tracks.return_value = None
        assert client.get_top_tracks("art-1") is None

    def test_track_uri_format(self, client: SpotifyClient, mock_sp: MagicMock) -> None:
        mock_sp.artist_top_tracks.return_value = _make_top_tracks_response()
        result = client.get_top_tracks("art-1")

        assert result is not None
        for track in result:
            assert track.uri.startswith("spotify:track:")


class TestUserHasPlaylist:
    """user_has_playlist — lookup by name or id."""

    def test_find_by_name(self, client: SpotifyClient) -> None:
        result = client.get_user_playlist(name="Scouting")
        assert result is not None
        assert result.name == "Scouting"

    def test_find_by_id(self, client: SpotifyClient) -> None:
        result = client.get_user_playlist(playlist_id="pl-1")
        assert result is not None
        assert result.id == "pl-1"

    def test_id_takes_precedence(self, client: SpotifyClient) -> None:
        # name matches but id doesn't — should return None
        result = client.get_user_playlist(name="Scouting", playlist_id="nonexistent")
        assert result is None

    def test_not_found_by_name(self, client: SpotifyClient) -> None:
        assert client.get_user_playlist(name="Nope") is None

    def test_not_found_by_id(self, client: SpotifyClient) -> None:
        assert client.get_user_playlist(playlist_id="nonexistent") is None

    def test_no_args_raises(self, client: SpotifyClient) -> None:
        with pytest.raises(ValueError):
            client.get_user_playlist()


class TestGetOrCreatePlaylist:
    """get_or_create_playlist — find existing or create new."""

    def test_returns_existing(self, client: SpotifyClient, mock_sp: MagicMock) -> None:
        result = client.get_or_create_playlist("Scouting")

        assert result is not None
        assert result.id == "pl-1"
        mock_sp.user_playlist_create.assert_not_called()

    def test_creates_when_missing(
        self, client: SpotifyClient, mock_sp: MagicMock
    ) -> None:
        mock_sp.user_playlist_create.return_value = _make_playlist_response(
            "New Playlist", "pl-new"
        )
        result = client.get_or_create_playlist("New Playlist")

        assert result is not None
        assert result.id == "pl-new"
        assert result.name == "New Playlist"
        mock_sp.user_playlist_create.assert_called_once()

    def test_created_playlist_invalidates_cache(
        self, client: SpotifyClient, mock_sp: MagicMock
    ) -> None:
        """Creating a playlist invalidates cache so next fetch gets fresh data."""
        mock_sp.user_playlist_create.return_value = _make_playlist_response(
            "New Playlist", "pl-new"
        )
        # Update mock to return both playlists on next fetch
        mock_sp.current_user_playlists.return_value = _make_playlists_page(
            [
                _make_playlist_response("Scouting", "pl-1"),
                _make_playlist_response("New Playlist", "pl-new"),
            ]
        )
        client.get_or_create_playlist("New Playlist")

        # Cache was invalidated, so this fetches fresh (updated mock returns both)
        result = client.get_user_playlist(name="New Playlist")
        assert result is not None
        assert result.id == "pl-new"

    def test_returns_none_when_create_fails(
        self, client: SpotifyClient, mock_sp: MagicMock
    ) -> None:
        mock_sp.user_playlist_create.return_value = None
        result = client.get_or_create_playlist("Ghost Playlist")
        assert result is None


class TestAddTracksToPlaylist:
    """add_tracks_to_playlist — add track URIs to an existing playlist."""

    def test_adds_tracks(self, client: SpotifyClient, mock_sp: MagicMock) -> None:
        uris = ["spotify:track:a", "spotify:track:b"]
        result = client.add_tracks_to_playlist("pl-1", uris)

        assert result is True
        mock_sp.playlist_add_items.assert_called_once_with("pl-1", uris)


class TestUserPlaylistFromSpotify:
    """UserPlaylist.from_spotify_playlist classmethod."""

    def test_parses_playlist_response(self) -> None:
        raw = _make_playlist_response("Scouting", "pl-1", "user-1")
        result = UserPlaylist.from_spotify_playlist(raw)

        assert result.name == "Scouting"
        assert result.id == "pl-1"
        assert result.user_id == "user-1"
        assert "pl-1" in result.url

    def test_parses_create_response(self) -> None:
        # user_playlist_create returns the same shape
        raw = _make_playlist_response("New", "pl-new", "user-1")
        result = UserPlaylist.from_spotify_playlist(raw)

        assert result.name == "New"
        assert result.id == "pl-new"
