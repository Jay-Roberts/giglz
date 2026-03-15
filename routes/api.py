"""
API routes — JSON endpoints for player polling.
"""
from flask import Blueprint, jsonify, session
from db_models import Track
from spotify.user_client import SpotifyUserClient, SpotifyNotConnectedError
from schemas import NowPlayingResponse, TrackState, ShowContext

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/now-playing")
def now_playing():
    """Return current track JSON for player polling."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401

    try:
        client = SpotifyUserClient(user_id)
    except SpotifyNotConnectedError:
        return jsonify(NowPlayingResponse(connected=False).model_dump())

    playback = client.get_currently_playing()
    if not playback:
        return jsonify(NowPlayingResponse(connected=True, playing=False).model_dump())

    show_context = _get_show_context(playback.track_id)

    response = NowPlayingResponse(
        connected=True,
        playing=playback.is_playing,
        track=TrackState(
            id=playback.track_id,
            name=playback.track_name,
            artist=playback.artist_name,
            album_art=playback.album_art,
            progress_ms=playback.progress_ms,
            duration_ms=playback.duration_ms,
        ),
        show_context=show_context,
    )
    return jsonify(response.model_dump())


def _get_show_context(spotify_track_id: str) -> ShowContext | None:
    """Look up show context for a track."""
    track = Track.query.filter_by(spotify_id=spotify_track_id).first()
    if not track:
        return None

    artist = track.artist
    if not artist.shows:
        return None

    show = artist.shows[0]
    return ShowContext(
        show_id=show.id,
        show_name=f"{artist.name} @ {show.venue.name}",
    )
