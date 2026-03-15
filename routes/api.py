"""
API routes — JSON endpoints for player polling.
"""
from flask import Blueprint, jsonify, request
from pydantic import ValidationError
from db_models import Track, ShowStatus
from routes.auth import api_login_required
from spotify.user_client import SpotifyUserClient, SpotifyNotConnectedError
from services.loves import LoveService
from services.shows import ShowService
from services.scouting import ScoutingService
from schemas import (
    NowPlayingResponse, TrackState, ShowContext,
    LoveTrackRequest, LoveTrackResponse,
    SetShowStatusRequest, ShowStatusResponse,
)

_love_service = LoveService()

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/now-playing")
@api_login_required
def now_playing(user_id):
    """Return current track JSON for player polling."""
    try:
        client = SpotifyUserClient(user_id)
    except SpotifyNotConnectedError:
        return jsonify(NowPlayingResponse(connected=False).model_dump())

    playback = client.get_currently_playing()
    if not playback:
        return jsonify(NowPlayingResponse(connected=True, playing=False).model_dump())

    show_context = _get_show_context(playback.track_id)
    is_loved = _love_service.is_loved(user_id, playback.track_id)

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
            loved=is_loved,
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


@api_bp.route("/love", methods=["POST"])
@api_login_required
def toggle_love(user_id):
    """Toggle love state on a track."""
    # Parse
    try:
        req = LoveTrackRequest.model_validate_json(request.data)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400

    # Command
    service = LoveService()
    is_now_loved = service.toggle_love(user_id, req.spotify_track_id)

    # Render
    response = LoveTrackResponse(loved=is_now_loved, spotify_track_id=req.spotify_track_id)
    return jsonify(response.model_dump())


@api_bp.route("/shows/<show_id>/status", methods=["POST"])
@api_login_required
def set_show_status(user_id, show_id: str):
    """Set attendance status for a show."""
    # Parse
    try:
        req = SetShowStatusRequest.model_validate_json(request.data)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400

    # Convert string to enum (or None)
    status = ShowStatus(req.status) if req.status else None

    # Command
    service = ShowService()
    new_status = service.set_show_status(user_id, show_id, status)

    # Render
    response = ShowStatusResponse(
        show_id=show_id,
        status=new_status.value if new_status else None
    )
    return jsonify(response.model_dump())


@api_bp.route("/shows/<show_id>/scout", methods=["POST"])
@api_login_required
def scout_show(user_id, show_id: str):
    """Scout a show — swap playlist and start playback."""
    service = ScoutingService()
    success = service.scout_show(user_id, show_id)

    if success:
        return jsonify({"status": "scouting", "show_id": show_id})
    else:
        return jsonify({"error": "Could not start scouting"}), 400
