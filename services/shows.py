"""
Shows service — business logic for adding and listing shows.

Orchestrates: Spotify search → find/create entities → persist show.
"""

from datetime import date
from db_models import db, City, Venue, Artist, Track, Show, ShowArtist, ShowSource
from spotify import SpotifyAPI


class DuplicateShowError(Exception):
    """Show with same artists, venue, and date already exists."""


class ShowService:
    def __init__(self):
        self._spotify = None

    @property
    def spotify(self) -> SpotifyAPI:
        if self._spotify is None:
            self._spotify = SpotifyAPI()
        return self._spotify

    def add_show(
        self,
        artist_names: list[str],
        show_date: date,
        venue_name: str,
        city_name: str,
        ticket_url: str | None = None,
    ) -> Show:
        """Add a show with artists, searching Spotify for each."""

        # find or create city
        city = self._find_or_create_city(city_name)

        # find or create venue
        venue = self._find_or_create_venue(venue_name, city.id)

        # find or create artists (with spotify search)
        artists = []
        for name in artist_names:
            artist = self._find_or_create_artist(name)
            artists.append(artist)

        # check for duplicate
        if self._is_duplicate(artists, venue.id, show_date):
            raise DuplicateShowError(
                f"Show with these artists at {venue_name} on {show_date} already exists"
            )

        # create show
        show = Show(
            date=show_date,
            venue_id=venue.id,
            ticket_url=ticket_url,
            source=ShowSource.MANUAL,
        )
        db.session.add(show)
        db.session.flush()  # get show.id

        # create show-artist relations
        for artist in artists:
            show_artist = ShowArtist(show_id=show.id, artist_id=artist.id)
            db.session.add(show_artist)

        db.session.commit()
        return show

    def _find_or_create_city(self, name: str) -> City:
        name = name.strip()
        city = City.query.filter(db.func.lower(City.name) == name.lower()).first()
        if city:
            return city

        city = City(name=name)
        db.session.add(city)
        db.session.flush()
        return city

    def _find_or_create_venue(self, name: str, city_id: str) -> Venue:
        # TODO: We need better city handeling. Paris -> TX or FR?
        name = name.strip()
        venue = Venue.query.filter(
            db.func.lower(Venue.name) == name.lower(), Venue.city_id == city_id
        ).first()
        if venue:
            return venue

        venue = Venue(name=name, city_id=city_id)
        db.session.add(venue)
        db.session.flush()
        return venue

    def _find_or_create_artist(self, name: str) -> Artist:
        name = name.strip()

        # search spotify first
        spotify_result = self.spotify.search_artist(name)

        if spotify_result:
            # check if we already have this artist by spotify_id
            artist = Artist.query.filter_by(
                spotify_id=spotify_result.spotify_id
            ).first()
            if artist:
                return artist

            # create artist with spotify data
            artist = Artist(
                spotify_id=spotify_result.spotify_id,
                name=spotify_result.name,
                image_url=spotify_result.image_url,
            )
            db.session.add(artist)
            db.session.flush()

            # pull top tracks
            self._pull_tracks_for_artist(artist, spotify_result.spotify_id)

            return artist
        else:
            # artist not found on spotify - create without spotify data
            # case-insensitive match to avoid duplicates (CHVRCHES vs Chvrches)
            artist = Artist.query.filter(
                db.func.lower(Artist.name) == name.lower()
            ).first()
            if artist:
                return artist

            artist = Artist(name=name)
            db.session.add(artist)
            db.session.flush()
            return artist

    def _pull_tracks_for_artist(self, artist: Artist, spotify_id: str) -> None:
        """Pull top tracks from Spotify and create Track records."""
        from flask import current_app

        settings = current_app.extensions["settings"]
        limit = settings.spotify_top_tracks_limit

        tracks = self.spotify.get_top_tracks(spotify_id, limit=limit)
        for track_info in tracks:
            # skip if track already exists
            existing = Track.query.filter_by(spotify_id=track_info.spotify_id).first()
            if existing:
                continue

            track = Track(
                spotify_id=track_info.spotify_id,
                name=track_info.name,
                artist_id=artist.id,
                preview_url=track_info.preview_url,
            )
            db.session.add(track)

    def _is_duplicate(
        self, artists: list[Artist], venue_id: str, show_date: date
    ) -> bool:
        """Check if show with same artists, venue, and date exists."""
        artist_ids = sorted(a.id for a in artists)

        # find shows at same venue on same date
        existing_shows = Show.query.filter_by(venue_id=venue_id, date=show_date).all()

        for show in existing_shows:
            show_artist_ids = sorted(a.id for a in show.artists)
            if show_artist_ids == artist_ids:
                return True

        return False

    def list_shows(self) -> list[Show]:
        """List all shows, ordered by date."""
        return Show.query.order_by(Show.date.asc()).all()
