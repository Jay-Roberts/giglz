"""Flask routes for giglz."""

import csv
import functools
import io
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import flask
from flask_cors import CORS
import spotipy

from config import (
    ALLOWED_USER_IDS,
    APP_DISPLAY_NAME,
    APP_NAME,
    FLASK_SECRET_KEY,
    HOST_USER_ID,
    PORT,
    SCOUT_GIG_CTA,
    SCOUT_GIG_PLAYLIST_NAME,
    SHARE_ON_NETWORK,
    SHOWLIST_DISPLAY_NAME,
    SQLALCHEMY_DATABASE_URI,
    SQLALCHEMY_TRACK_MODIFICATIONS,
    setup_logging,
)
import db_models  # noqa: F401 - registers models with SQLAlchemy
from db import DEFAULT_SHOWLIST_NAME, Database
from extensions import db, migrate
from models import (
    ImportedUrl,
    ImportStatus,
    LoveTrackResponse,
    ScoutRequest,
    ScoutResponse,
    ScoutShowInfo,
    Show,
    ShowLovedCount,
    ShowSubmission,
    TrackStatusResponse,
)
from show_extractor import ShowExtractor
from spotify import SpotifyAPI, TokenManager
from url_utils import normalize_url

setup_logging()
logger = logging.getLogger(__name__)


def create_app():
    """Setup app."""
    app = flask.Flask(__name__)
    app.secret_key = FLASK_SECRET_KEY

    # Config must be set BEFORE init_app
    app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = SQLALCHEMY_TRACK_MODIFICATIONS

    db.init_app(app)
    migrate.init_app(app, db)

    # CORS for browser extension - allow credentials (session cookies)
    CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

    # Database facade - single entry point for persistence
    app.extensions["database"] = Database()

    return app


def get_db() -> Database:
    """Get database facade from current app context."""
    return flask.current_app.extensions["database"]  # type: ignore[return-value]


app = create_app()


# Static template globals - search here to see what's injected into all templates
TEMPLATE_GLOBALS: dict[str, Any] = {
    "app_name": APP_NAME,
    "app_display_name": APP_DISPLAY_NAME,
    "share_on_network": SHARE_ON_NETWORK,
    "showlist_display_name": SHOWLIST_DISPLAY_NAME,
    "scout_gig_cta": SCOUT_GIG_CTA,
    "default_showlist_name": DEFAULT_SHOWLIST_NAME,
}


@app.context_processor
def inject_globals():
    """Make config flags and auth info available to all templates."""
    return {
        **TEMPLATE_GLOBALS,
        # Dynamic - requires request context
        "current_user_id": flask.session.get("user_id"),
        "current_user_name": flask.session.get("user_name"),
        "is_host": flask.session.get("user_id") == HOST_USER_ID,
    }


@app.template_filter("format_date")
def format_date_filter(date_str: str) -> str:
    """Convert YYYY-MM-DD to DD Mon. YYYY (e.g., '24 Feb. 2026')."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%-d %b. %Y")
    except (ValueError, TypeError):
        return date_str


extractor = ShowExtractor()


# --- Auth Helpers ---


def require_host(f):
    """Decorator to restrict route to host only."""

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if flask.session.get("user_id") != HOST_USER_ID:
            flask.flash("Only the host can do that.")
            return flask.redirect(flask.url_for("home"))
        return f(*args, **kwargs)

    return wrapper


def _auto_follow_host_playlist(access_token: str) -> None:
    """Make user follow the host's giglz playlist.

    Called on first login for non-host users. Fails gracefully
    if host hasn't set up the playlist yet.
    """
    try:
        if not HOST_USER_ID:
            logger.warning("HOST_USER_ID not set, can't auto-follow")
            return

        host_tm = TokenManager(user_id=HOST_USER_ID)
        host_token = host_tm.get_token()
        if not host_token:
            logger.warning("Host not authenticated, can't auto-follow")
            return

        host_api = SpotifyAPI(host_token)
        spotify_playlist = host_api.get_user_playlist(name="giglz")
        if not spotify_playlist:
            logger.warning("Host playlist 'giglz' not found")
            return

        user_api = SpotifyAPI(access_token)
        user_api.follow_playlist(spotify_playlist.id)
        logger.info("User auto-followed playlist %s", spotify_playlist.id)
    except Exception as e:
        logger.warning("Auto-follow failed: %s", e)


# --- Auth Routes ---


@app.route("/login")
def login():
    """Redirect to Spotify OAuth."""
    tm = TokenManager()
    auth_url = tm.get_auth_url()
    return flask.redirect(auth_url)


@app.route("/callback")
def callback():
    """Handle Spotify OAuth callback."""
    code = flask.request.args.get("code")
    error = flask.request.args.get("error")

    if error:
        flask.flash(f"Spotify auth failed: {error}")
        return flask.redirect(flask.url_for("home"))

    if not code:
        flask.flash("No authorization code received.")
        return flask.redirect(flask.url_for("home"))

    tm = TokenManager()
    try:
        token_info = tm.exchange_code(code)
    except Exception as e:
        logger.warning("Token exchange failed: %s", e)
        flask.flash("Login failed. Please try again.")
        return flask.redirect(flask.url_for("home"))

    sp = spotipy.Spotify(auth=token_info["access_token"])
    user = sp.current_user()
    if not user:
        flask.flash("Failed to get user info from Spotify.")
        return flask.redirect(flask.url_for("home"))

    user_id = user["id"]
    user_name = user.get("display_name") or user_id

    if ALLOWED_USER_IDS and user_id not in ALLOWED_USER_IDS:
        logger.warning("Rejected login from non-allowed user: %s", user_id)
        flask.flash("This is a private listening party.")
        return flask.redirect(flask.url_for("home"))

    user_tm = TokenManager(user_id=user_id)
    user_tm.save_token(token_info)

    flask.session["user_id"] = user_id
    flask.session["user_name"] = user_name

    if user_id != HOST_USER_ID:
        _auto_follow_host_playlist(token_info["access_token"])

    flask.flash(f"Logged in as {user_name}")
    return flask.redirect(flask.url_for("home"))


@app.route("/logout", methods=["POST"])
def logout():
    """Clear session."""
    flask.session.clear()
    flask.flash("Logged out.")
    return flask.redirect(flask.url_for("home"))


# --- Spotify API Helpers ---


def get_spotify_api() -> SpotifyAPI:
    """Get SpotifyAPI for current session user.

    Raises:
        ValueError: If not logged in or token expired.
    """
    user_id = flask.session.get("user_id")
    if not user_id:
        raise ValueError("Not logged in")

    tm = TokenManager(user_id=user_id)
    token = tm.get_token()
    if not token:
        raise ValueError("Token expired or missing")

    return SpotifyAPI(token)


def get_host_spotify_api() -> SpotifyAPI:
    """Get SpotifyAPI for the host user.

    Used for operations that should always use host's account
    (e.g., adding tracks to playlist).

    Raises:
        ValueError: If host not authenticated.
    """
    if not HOST_USER_ID:
        raise ValueError("HOST_USER_ID not configured")

    tm = TokenManager(user_id=HOST_USER_ID)
    token = tm.get_token()
    if not token:
        raise ValueError("Host not authenticated")

    return SpotifyAPI(token)


def _scout_submission(
    submission: ShowSubmission,
    user_id: str,
) -> tuple[Show, list[str]]:
    """Run Spotify pipeline on a ShowSubmission.

    Searches each artist, grabs top tracks, adds them to the default
    showlist's Spotify playlist, and builds a Show object.

    Uses host's Spotify account for playlist operations.

    Args:
        submission: The show submission to process.
        user_id: User ID of the person importing (for showlist ownership).

    Returns:
        A tuple of (Show, not_found_artists).

    Raises:
        ValueError: If the playlist can't be created or host not authenticated.
    """
    spotify = get_host_spotify_api()
    database = get_db()

    artist_spotify_ids: list[str] = []
    all_track_uris: list[str] = []
    not_found: list[str] = []

    for artist_name in submission.artists:
        result = spotify.search_artist(artist_name)
        if result is None:
            logger.info("Artist NOT FOUND on Spotify: %r", artist_name)
            artist_spotify_ids.append("")
            not_found.append(artist_name)
            continue

        logger.info(
            "Artist match: %r -> %r (id=%s)", artist_name, result.name, result.id
        )
        artist_spotify_ids.append(result.id)

        top_tracks = spotify.get_top_tracks(result.id)
        if top_tracks:
            logger.info(
                "Top tracks for %r: %s",
                result.name,
                [f"{t.track} ({t.artist_name})" for t in top_tracks],
            )
            all_track_uris.extend(t.uri for t in top_tracks)

    # Get or create default showlist
    showlist = database.get_or_create_default_showlist(user_id)
    spotify_playlist_id = showlist.spotify_playlist_id

    # Ensure Spotify playlist exists
    if not spotify_playlist_id:
        spotify_playlist = spotify.get_or_create_playlist("giglz")
        if spotify_playlist is None:
            raise ValueError("Failed to create giglz playlist on Spotify.")
        database.update_showlist_spotify_id(showlist.id, spotify_playlist.id)
        spotify_playlist_id = spotify_playlist.id

    # Add tracks to Spotify playlist
    if all_track_uris:
        spotify.add_tracks_to_playlist(spotify_playlist_id, all_track_uris)

    # Create show
    show = Show.from_submission(
        submission=submission,
        artist_spotify_ids=artist_spotify_ids,
        track_uris=all_track_uris,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    # Save show and link to showlist
    database.save_show(show)
    database.add_show_to_showlist(showlist.id, show.id, user_id)

    return show, not_found


@app.route("/")
def home():
    """Render the home page with playlists front and center."""
    database = get_db()
    showlists = database.get_all_showlists()

    # Enrich showlists with show/track counts for display
    enriched_showlists = []
    for sl in showlists:
        shows = database.get_shows_for_showlist(sl.id)
        enriched_showlists.append(
            {
                "id": sl.id,
                "name": sl.name,
                "spotify_playlist_id": sl.spotify_playlist_id,
                "show_count": len(shows),
                "track_count": sum(len(s.track_uris) for s in shows),
            }
        )

    return flask.render_template("home.html", showlists=enriched_showlists)


@app.route("/import")
def import_page():
    """Render the import page with all import forms."""
    return flask.render_template("import.html")


@app.route("/lineups")
def all_showlists():
    """List all showlists."""
    showlists = get_db().get_all_showlists()
    return flask.render_template("showlists.html", showlists=showlists)


@app.route("/lineup/create", methods=["POST"])
def create_showlist():
    """Create a new showlist."""
    user_id = flask.session.get("user_id")
    if not user_id:
        flask.flash("Please log in to create a lineup.")
        return flask.redirect(flask.url_for("home"))

    name = flask.request.form.get("name", "").strip()
    if not name:
        flask.flash("Please enter a name for your lineup.")
        return flask.redirect(flask.url_for("home"))

    showlist = get_db().create_showlist(name, user_id)
    flask.flash(f"Created lineup: {showlist.name}")
    return flask.redirect(flask.url_for("showlist_view", name=showlist.name))


@app.route("/shows")
def all_shows():
    """View all imported shows with selection UI."""
    sort = flask.request.args.get("sort", "date")
    user_id = flask.session.get("user_id")
    shows = get_db().get_all_shows(sort=sort, user_id=user_id)
    showlists = get_db().get_all_showlists()
    return flask.render_template(
        "shows.html", shows=shows, showlists=showlists, sort=sort
    )


@app.route("/playlist/create", methods=["POST"])
def create_playlist_with_shows():
    """Create a new lineup with selected shows and sync to Spotify."""
    user_id = flask.session.get("user_id")
    if not user_id:
        flask.flash("Please log in to create a playlist.")
        return flask.redirect(flask.url_for("home"))

    database = get_db()

    # Get playlist name and show IDs
    name = flask.request.form.get("name", "").strip()
    if not name:
        flask.flash("Please enter a name for your playlist.")
        return flask.redirect(flask.url_for("all_shows"))

    show_ids = flask.request.form.getlist("show_ids")
    if not show_ids:
        flask.flash("No shows selected.")
        return flask.redirect(flask.url_for("all_shows"))

    # Create showlist in database (handles unique naming)
    showlist = database.create_showlist(name, user_id)

    # Get Spotify API (uses host account for playlist operations)
    try:
        spotify = get_host_spotify_api()
    except ValueError as e:
        flask.flash(f"Spotify error: {e}")
        return flask.redirect(flask.url_for("all_shows"))

    # Create Spotify playlist
    spotify_playlist = spotify.get_or_create_playlist(showlist.name)
    if spotify_playlist is None:
        flask.flash(f"Failed to create Spotify playlist for {showlist.name}")
        return flask.redirect(flask.url_for("all_shows"))
    database.update_showlist_spotify_id(showlist.id, spotify_playlist.id)

    # Link shows to showlist and collect tracks
    all_track_uris: list[str] = []
    for show_id in show_ids:
        show = database.get_show(show_id)
        if show:
            database.add_show_to_showlist(showlist.id, show_id, user_id)
            all_track_uris.extend(show.track_uris)

    # Add tracks to Spotify playlist
    if all_track_uris:
        spotify.add_tracks_to_playlist(spotify_playlist.id, all_track_uris)

    flask.flash(f"Created playlist '{showlist.name}' with {len(show_ids)} show(s)")
    return flask.redirect(flask.url_for("showlist_view", name=showlist.name))


@app.route("/lineup/<name>/add-shows", methods=["POST"])
def add_shows_to_lineup(name: str):
    """Add selected shows to a showlist and sync to Spotify."""
    user_id = flask.session.get("user_id")
    if not user_id:
        flask.flash("Please log in to add shows.")
        return flask.redirect(flask.url_for("home"))

    database = get_db()
    showlist = database.get_showlist_by_name(name)
    if not showlist:
        flask.abort(404)

    show_ids = flask.request.form.getlist("show_ids")
    if not show_ids:
        flask.flash("No shows selected.")
        return flask.redirect(flask.url_for("all_shows"))

    # Get Spotify API (uses host account for playlist operations)
    try:
        spotify = get_host_spotify_api()
    except ValueError as e:
        flask.flash(f"Spotify error: {e}")
        return flask.redirect(flask.url_for("all_shows"))

    # Ensure Spotify playlist exists for this showlist
    spotify_playlist_id = showlist.spotify_playlist_id
    if not spotify_playlist_id:
        spotify_playlist = spotify.get_or_create_playlist(showlist.name)
        if spotify_playlist is None:
            flask.flash(f"Failed to create Spotify playlist for {showlist.name}")
            return flask.redirect(flask.url_for("all_shows"))
        database.update_showlist_spotify_id(showlist.id, spotify_playlist.id)
        spotify_playlist_id = spotify_playlist.id

    # Collect tracks from selected shows and add to showlist
    all_track_uris: list[str] = []
    for show_id in show_ids:
        show = database.get_show(show_id)
        if show:
            database.add_show_to_showlist(showlist.id, show_id, user_id)
            all_track_uris.extend(show.track_uris)

    # Add tracks to Spotify playlist
    if all_track_uris:
        spotify.add_tracks_to_playlist(spotify_playlist_id, all_track_uris)

    flask.flash(f"Added {len(show_ids)} show(s) to {showlist.name}")
    return flask.redirect(flask.url_for("showlist_view", name=name))


@app.route("/lineup/<name>")
def showlist_view(name: str):
    """View shows for a specific showlist (with player)."""
    showlist = get_db().get_showlist_by_name(name)
    if not showlist:
        flask.abort(404)

    sort = flask.request.args.get("sort", "date")
    user_id = flask.session.get("user_id")
    shows = get_db().get_shows_for_showlist(showlist.id, sort=sort, user_id=user_id)

    return flask.render_template(
        "showlist.html",
        showlist=showlist,
        shows=shows,
        sort=sort,
        with_player=True,
    )


@app.route("/lineup/<name>/shows")
def showlist_shows_only(name: str):
    """View shows for a showlist (cards only, no player)."""
    showlist = get_db().get_showlist_by_name(name)
    if not showlist:
        flask.abort(404)
    shows = get_db().get_shows_for_showlist(showlist.id)
    return flask.render_template(
        "showlist.html",
        showlist=showlist,
        shows=shows,
        with_player=False,
    )


@app.route("/add-show", methods=["POST"])
def add_show():
    """Handle the add-show form submission."""
    user_id = flask.session.get("user_id")
    if not user_id:
        flask.flash("Please log in to add shows.")
        return flask.redirect(flask.url_for("import_page"))

    raw_artists = flask.request.form.get("artists", "")
    artists = [a.strip() for a in raw_artists.split(",") if a.strip()]
    venue = flask.request.form.get("venue", "")
    date = flask.request.form.get("date", "")
    ticket_url = flask.request.form.get("ticket_url") or None

    if not artists or not venue or not date:
        flask.flash("Artists, venue, and date are required.")
        return flask.redirect(flask.url_for("import_page"))

    submission = ShowSubmission(
        artists=artists, venue=venue, date=date, ticket_url=ticket_url
    )

    try:
        show, not_found = _scout_submission(submission, user_id)
    except ValueError as e:
        flask.flash(str(e))
        return flask.redirect(flask.url_for("import_page"))

    found_count = len(artists) - len(not_found)
    msg = (
        f"Added {venue} on {date} — {found_count} artist(s) found, "
        f"{len(show.track_uris)} tracks added."
    )
    if not_found:
        msg += f" Couldn't find: {', '.join(not_found)}"
    flask.flash(msg)

    return flask.redirect(flask.url_for("import_page"))


def _import_url(url: str, user_id: str) -> Show:
    """Extract show data from a URL and run the Spotify pipeline.

    Returns:
        The saved Show object.

    Raises:
        ValueError: If extraction fails or returns incomplete data.
        Exception: If page fetch or Spotify pipeline fails.
    """
    submission = extractor.extract_show(url)
    if submission is None:
        raise ValueError(f"No data extracted from {url}")
    show, _not_found = _scout_submission(submission, user_id)
    return show


def process_single_url(url: str, user_id: str) -> tuple[Show | None, ImportedUrl]:
    """Process a single URL: normalize, dedup, extract, and build ImportedUrl.

    Args:
        url: Raw ticket URL to process.
        user_id: User ID of the person importing.

    Returns:
        (show, imported_url) — show is None if skipped or failed.
    """
    normalized = normalize_url(url)

    existing = get_db().get_import(normalized)
    if existing and existing.status == ImportStatus.SUCCESS:
        logger.info("Skipping already imported URL: %s", normalized)
        return None, ImportedUrl(
            url=normalized,
            status=ImportStatus.SKIPPED,
            show_id=existing.show_id,
            artist_count=existing.artist_count,
            track_count=existing.track_count,
            error=None,
            attempted_at=datetime.now(timezone.utc).isoformat(),
        )

    try:
        show = _import_url(url, user_id)
        return show, ImportedUrl(
            url=normalized,
            status=ImportStatus.SUCCESS,
            show_id=show.id,
            artist_count=len(show.artists),
            track_count=len(show.track_uris),
            error=None,
            attempted_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        logger.warning("Failed to import %s: %s", url, e)
        return None, ImportedUrl(
            url=normalized,
            status=ImportStatus.FAILED,
            show_id=None,
            error=str(e),
            attempted_at=datetime.now(timezone.utc).isoformat(),
        )


def extract_data_from_urls(
    urls: list[str],
    user_id: str,
) -> tuple[list[Show], list[ImportedUrl], list[str], list[str]]:
    """Extract show data from ticket URLs, with dedup and error tracking.

    Batch version that does NOT save to DB — useful for testing.
    Uses process_single_url internally.

    Args:
        urls: Raw ticket URLs to process.
        user_id: User ID of the person importing.

    Returns:
        A tuple of (shows, imported_urls, failures, skipped_urls):
        - shows: Successfully extracted Show objects
        - imported_urls: ImportedUrl records for success/failure (not skipped)
        - failures: Error message strings for failed URLs
        - skipped_urls: Original URLs that were already imported
    """
    skipped_urls: list[str] = []
    failures: list[str] = []
    shows: list[Show] = []
    imported_urls: list[ImportedUrl] = []

    for url in urls:
        show, imported_url = process_single_url(url, user_id)

        if imported_url.status == ImportStatus.SKIPPED:
            skipped_urls.append(url)
            # Don't add to imported_urls — matches original behavior
        elif imported_url.status == ImportStatus.FAILED:
            failures.append(imported_url.error or "Unknown error")
            imported_urls.append(imported_url)
        else:  # SUCCESS
            shows.append(show)  # type: ignore — show is not None for SUCCESS
            imported_urls.append(imported_url)

    return shows, imported_urls, failures, skipped_urls


@app.route("/import-shows", methods=["POST"])
def import_shows():
    """Import shows from a list of ticket URLs with incremental saves."""
    user_id = flask.session.get("user_id")
    if not user_id:
        flask.flash("Please log in to import shows.")
        return flask.redirect(flask.url_for("import_page"))

    raw_urls = flask.request.form.get("urls", "")

    urls = [u.strip() for u in raw_urls.splitlines() if u.strip()]
    if not urls:
        flask.flash("Paste at least one URL.")
        return flask.redirect(flask.url_for("import_page"))

    results = {"imported": 0, "failed": 0, "skipped": 0, "tracks": 0}
    failures: list[str] = []

    for url in urls:
        show, imported_url = process_single_url(url, user_id)

        if imported_url.status == ImportStatus.SKIPPED:
            results["skipped"] += 1
            continue

        # Save immediately (crash-resilient)
        get_db().record_import(imported_url)

        if imported_url.status == ImportStatus.SUCCESS:
            results["imported"] += 1
            results["tracks"] += len(show.track_uris)  # type: ignore
        else:  # FAILED
            results["failed"] += 1
            if imported_url.error:
                failures.append(imported_url.error)

    msg = (
        f"Imported {results['imported']}/{len(urls)} shows, {results['tracks']} tracks."
    )
    if results["skipped"]:
        msg += f" Skipped {results['skipped']} already imported."

    flask.flash(msg)
    for failure in failures:
        flask.flash(failure)

    return flask.redirect(flask.url_for("import_page"))


@app.route("/import-shows/stream", methods=["POST"])
def import_shows_stream():
    """Import shows with SSE streaming for real-time UI updates.

    Streams JSON events as each URL is processed:
    - {type: "progress", url, status, show?, error?, imported, failed, skipped, total}
    - {type: "complete", imported, failed, skipped, tracks, total}
    """
    user_id = flask.session.get("user_id")
    if not user_id:
        return flask.jsonify({"error": "Not logged in"}), 401

    raw_urls = flask.request.form.get("urls", "")
    urls = [u.strip() for u in raw_urls.splitlines() if u.strip()]

    def generate():
        if not urls:
            yield f"data: {json.dumps({'type': 'error', 'message': 'No URLs provided'})}\n\n"
            return

        results = {"imported": 0, "failed": 0, "skipped": 0, "tracks": 0}

        # Capture db reference before generator yields (for app context)
        database = get_db()

        for i, url in enumerate(urls):
            show, imported_url = process_single_url(url, user_id)

            event = {
                "type": "progress",
                "url": url,
                "status": imported_url.status.value,
                "index": i,
                "total": len(urls),
            }

            if imported_url.status == ImportStatus.SKIPPED:
                results["skipped"] += 1
            elif imported_url.status == ImportStatus.SUCCESS:
                database.record_import(imported_url)
                results["imported"] += 1
                results["tracks"] += len(show.track_uris)  # type: ignore
                event["show"] = {
                    "id": show.id,  # type: ignore
                    "artists": [a.name for a in show.artists],  # type: ignore
                    "venue": show.venue,  # type: ignore
                    "date": show.date,  # type: ignore
                    "track_count": len(show.track_uris),  # type: ignore
                }
            else:  # FAILED
                database.record_import(imported_url)
                results["failed"] += 1
                event["error"] = imported_url.error

            event.update(results)
            yield f"data: {json.dumps(event)}\n\n"

        yield f"data: {json.dumps({'type': 'complete', **results})}\n\n"

    return flask.Response(generate(), mimetype="text/event-stream")


# --- CSV Import ---


def parse_shows_csv(file) -> list[ShowSubmission]:
    """Parse uploaded CSV into ShowSubmission objects.

    Expected columns: artists, venue, date
    - artists: Comma-separated artist names (quote if multiple)
    - venue: Venue name
    - date: YYYY-MM-DD format

    Example CSV:
        artists,venue,date
        "Militarie Gun, ZULU",The Earl,2026-04-15
        Kitty Ray,Barboza,2026-04-20
    """
    # Read file content and decode if bytes
    content = file.read()
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    reader = csv.DictReader(io.StringIO(content))
    submissions = []

    for row in reader:
        # Handle both quoted "Artist1, Artist2" and unquoted single artist
        raw_artists = row.get("artists", "")
        artists = [a.strip() for a in raw_artists.split(",") if a.strip()]

        venue = row.get("venue", "").strip()
        date = row.get("date", "").strip()

        if not artists or not venue or not date:
            continue  # Skip incomplete rows

        submissions.append(
            ShowSubmission(
                artists=artists,
                venue=venue,
                date=date,
            )
        )

    return submissions


@app.route("/import-shows/csv", methods=["POST"])
def import_shows_csv():
    """Import shows from uploaded CSV file."""
    user_id = flask.session.get("user_id")
    if not user_id:
        flask.flash("Please log in to import shows.")
        return flask.redirect(flask.url_for("import_page"))

    file = flask.request.files.get("csv_file")

    if not file or not file.filename:
        flask.flash("No file uploaded.")
        return flask.redirect(flask.url_for("import_page"))

    try:
        submissions = parse_shows_csv(file)
    except Exception as e:
        logger.warning("Failed to parse CSV: %s", e)
        flask.flash(f"Failed to parse CSV: {e}")
        return flask.redirect(flask.url_for("import_page"))

    if not submissions:
        flask.flash("No valid shows found in CSV. Check format: artists,venue,date")
        return flask.redirect(flask.url_for("import_page"))

    results = {"imported": 0, "failed": 0, "tracks": 0}
    not_found_all: list[str] = []

    for submission in submissions:
        try:
            show, not_found = _scout_submission(submission, user_id)
            results["imported"] += 1
            results["tracks"] += len(show.track_uris)
            not_found_all.extend(not_found)
        except Exception as e:
            logger.warning("Failed to import show %s: %s", submission.venue, e)
            results["failed"] += 1

    msg = f"Imported {results['imported']} shows, {results['tracks']} tracks."
    if results["failed"]:
        msg += f" {results['failed']} failed."
    if not_found_all:
        msg += f" Couldn't find: {', '.join(not_found_all[:5])}"
        if len(not_found_all) > 5:
            msg += f" (+{len(not_found_all) - 5} more)"

    flask.flash(msg)
    return flask.redirect(flask.url_for("import_page"))


# --- Love Track API ---


@app.route("/api/love-track", methods=["POST"])
def love_track():
    """Love a track for the current user."""
    user_id = flask.session.get("user_id")
    if not user_id:
        return flask.jsonify({"error": "Not logged in"}), 401

    data = flask.request.get_json()
    if not data:
        return flask.jsonify({"error": "JSON body required"}), 400

    track_uri = data.get("uri")
    track_name = data.get("name", "")
    track_artist = data.get("artist", "")

    if not track_uri:
        return flask.jsonify({"error": "uri required"}), 400

    db = get_db()
    show_ids = db.love_track(user_id, track_uri, track_name, track_artist)
    counts = db.get_loved_counts_for_shows(user_id, show_ids)

    shows_updated = [
        ShowLovedCount(id=sid, loved_count=counts.get(sid, 0)) for sid in show_ids
    ]
    response = LoveTrackResponse(
        loved=True, uri=track_uri, shows=show_ids, shows_updated=shows_updated
    )
    return flask.jsonify(response.model_dump())


@app.route("/api/unlove-track", methods=["POST"])
def unlove_track():
    """Unlove a track for the current user."""
    user_id = flask.session.get("user_id")
    if not user_id:
        return flask.jsonify({"error": "Not logged in"}), 401

    data = flask.request.get_json()
    if not data:
        return flask.jsonify({"error": "JSON body required"}), 400

    track_uri = data.get("uri")

    if not track_uri:
        return flask.jsonify({"error": "uri required"}), 400

    db = get_db()
    show_ids = db.unlove_track(user_id, track_uri)
    counts = db.get_loved_counts_for_shows(user_id, show_ids)

    shows_updated = [
        ShowLovedCount(id=sid, loved_count=counts.get(sid, 0)) for sid in show_ids
    ]
    response = LoveTrackResponse(
        loved=False, uri=track_uri, shows=show_ids, shows_updated=shows_updated
    )
    return flask.jsonify(response.model_dump())


@app.route("/api/track/<path:track_uri>/status")
def track_status(track_uri: str):
    """Check if a track is loved by the current user.

    Also returns show context (venue/date) if track belongs to a scouted show.
    """
    user_id = flask.session.get("user_id")

    db = get_db()
    show_ids = db.get_shows_with_track(track_uri)
    loved = db.is_track_loved(user_id, track_uri) if user_id else False

    # Get show context from first matching show
    show_venue = None
    show_date = None
    if show_ids:
        #! does this return soonest show? If so lets doc that/
        show = db.get_show(show_ids[0])
        if show:
            show_venue = show.venue
            show_date = show.date

    response = TrackStatusResponse(
        uri=track_uri,
        loved=loved,
        shows=show_ids,
        show_venue=show_venue,
        show_date=show_date,
    )
    return flask.jsonify(response.model_dump())


@app.route("/api/scout-gig", methods=["POST"])
def scout_gig():
    """Hot-swap the user's Now Scouting playlist with a show's tracks.

    Takes the current track URI, finds the most recent show containing it,
    and transfers playback to a playlist with that show's tracks.

    Request:
        {"track_uri": "spotify:track:xxx"}

    Response:
        {"success": true, "show": {...}, "track_count": 30}
    """
    user_id = flask.session.get("user_id")
    if not user_id:
        return flask.jsonify({"error": "Not logged in"}), 401

    data = flask.request.get_json()
    if not data or not data.get("track_uri"):
        return flask.jsonify({"error": "track_uri required"}), 400

    track_uri = data["track_uri"]
    database = get_db()

    # Find shows containing this track, pick most recent by date
    show_ids = database.get_shows_with_track(track_uri)
    if not show_ids:
        return flask.jsonify({"error": "Track not from a scouted show"}), 404

    shows = [database.get_show(sid) for sid in show_ids]
    shows = [s for s in shows if s is not None]
    if not shows:
        return flask.jsonify({"error": "Show not found"}), 404

    # Sort by date descending, pick most recent
    shows.sort(key=lambda s: s.date or "", reverse=True)
    show = shows[0]

    # Get Spotify API for current user (not host - this is user's playlist)
    try:
        spotify = get_spotify_api()
    except ValueError as e:
        return flask.jsonify({"error": str(e)}), 401

    # Get or create the "Now Scouting" playlist on user's account
    playlist = spotify.get_or_create_playlist(SCOUT_GIG_PLAYLIST_NAME)
    if not playlist:
        return flask.jsonify({"error": "Failed to create playlist"}), 500

    # Clear and fill with show's tracks
    spotify.clear_playlist(playlist.id)

    # Ensure current track is first if it's in the show
    track_uris = list(show.track_uris)
    if track_uri in track_uris:
        track_uris.remove(track_uri)
        track_uris.insert(0, track_uri)

    spotify.add_tracks_to_playlist(playlist.id, track_uris)

    # Transfer playback to the playlist, starting from current track
    try:
        spotify.transfer_playback_to_playlist(playlist.id, track_uri)
    except Exception as e:
        # Playback transfer can fail (no premium, no active device, etc.)
        # Playlist is still updated, so return partial success
        logger.warning("Playback transfer failed: %s", e)
        return flask.jsonify(
            {
                "success": True,
                "playback_transferred": False,
                "error": "Playlist updated but playback transfer failed",
                "show": {
                    "id": show.id,
                    "venue": show.venue,
                    "date": show.date,
                    "artists": [a.name for a in show.artists],
                },
                "track_count": len(track_uris),
            }
        )

    return flask.jsonify(
        {
            "success": True,
            "playback_transferred": True,
            "show": {
                "id": show.id,
                "venue": show.venue,
                "date": show.date,
                "artists": [a.name for a in show.artists],
            },
            "track_count": len(track_uris),
        }
    )


@app.route("/api/spotify-token")
def api_spotify_token():
    """Return current user's access token for Web Playback SDK."""
    user_id = flask.session.get("user_id")
    if not user_id:
        return flask.jsonify({"error": "Not logged in"}), 401

    tm = TokenManager(user_id=user_id)
    token_info = tm.get_token_info()
    if not token_info:
        return flask.jsonify({"error": "Token expired. Please log in again."}), 401

    return flask.jsonify(
        {
            "access_token": token_info["access_token"],
            "expires_in": token_info.get("expires_in", 3600),
        }
    )


@app.route("/api/now-playing")
def api_now_playing():
    """Return what's currently playing for the logged-in user.

    Response:
        {playing: false} if nothing playing or not a track.
        {playing: true, is_scouted: bool, track_name, artist_name, ...} if playing.
        If scouted, includes show_venue and show_date for context.
    """
    user_id = flask.session.get("user_id")
    if not user_id:
        return flask.jsonify({"error": "Not logged in"}), 401

    try:
        api = get_spotify_api()
    except ValueError as e:
        return flask.jsonify({"error": str(e)}), 401

    track = api.get_currently_playing()
    if not track:
        return flask.jsonify({"playing": False})

    database = get_db()
    show_ids = database.get_shows_with_track(track.track_uri)
    is_scouted = len(show_ids) > 0

    response = {"playing": True, "is_scouted": is_scouted, **track.model_dump()}

    # Add show context if track is scouted
    if show_ids:
        show = database.get_show(show_ids[0])
        if show:
            response["show_venue"] = show.venue
            response["show_date"] = show.date

    return flask.jsonify(response)


# --- Browser Extension API ---


@app.route("/api/scout", methods=["POST"])
def api_scout():
    """Scout a show from browser extension.

    Receives page content from extension, extracts show info via LLM,
    runs Spotify pipeline, and adds show to default playlist.

    Request:
        {"url": "...", "title": "...", "text": "..."}

    Response:
        {"success": true, "show": {...}, "track_count": 30}
        {"success": false, "error": "..."}
    """
    user_id = flask.session.get("user_id")
    if not user_id:
        response = ScoutResponse(success=False, error="Not logged in")
        return flask.jsonify(response.model_dump()), 401

    data = flask.request.get_json()
    if not data:
        response = ScoutResponse(success=False, error="JSON body required")
        return flask.jsonify(response.model_dump()), 400

    try:
        request = ScoutRequest(**data)
    except Exception as e:
        response = ScoutResponse(success=False, error=f"Invalid request: {e}")
        return flask.jsonify(response.model_dump()), 400

    # Extract show info from page text
    try:
        submission = extractor.extract_from_text(request.text, request.url)
    except ValueError as e:
        response = ScoutResponse(success=False, error=str(e))
        return flask.jsonify(response.model_dump()), 400

    if submission is None:
        response = ScoutResponse(success=False, error="Could not extract show info")
        return flask.jsonify(response.model_dump()), 400

    # Run Spotify pipeline
    try:
        show, not_found = _scout_submission(submission, user_id)
    except ValueError as e:
        response = ScoutResponse(success=False, error=str(e))
        return flask.jsonify(response.model_dump()), 500

    # Build response
    show_info = ScoutShowInfo(
        id=show.id,
        venue=show.venue,
        date=show.date,
        artists=[a.name for a in show.artists],
    )
    response = ScoutResponse(
        success=True,
        show=show_info,
        track_count=len(show.track_uris),
    )

    logger.info(
        "Scouted via extension: %s at %s (%d tracks)",
        ", ".join(show_info.artists),
        show_info.venue,
        response.track_count,
    )

    return flask.jsonify(response.model_dump())


if __name__ == "__main__":
    host = "0.0.0.0" if SHARE_ON_NETWORK else "127.0.0.1"
    app.run(host=host, port=PORT, debug=True)
