"""
Playlists routes — Now Scouting playlist view and management.
"""
from flask import Blueprint, render_template, redirect, url_for, flash
from routes.auth import login_required, get_current_user
from services.playlists import PlaylistService

playlists_bp = Blueprint("playlists", __name__, url_prefix="/playlists")


@playlists_bp.route("/scouting")
@login_required
def scouting():
    user = get_current_user()
    service = PlaylistService()
    playlist = service.get_or_create_now_scouting(user.id)
    tracks = service.get_playlist_tracks(playlist.id)

    return render_template(
        "playlists/scouting.html",
        playlist=playlist,
        tracks=tracks,
        show_count=len(playlist.shows),
        track_count=len(tracks),
    )


@playlists_bp.route("/scouting/shows/<show_id>", methods=["POST"])
@login_required
def add_show(show_id: str):
    user = get_current_user()
    service = PlaylistService()
    playlist = service.get_or_create_now_scouting(user.id)
    service.add_show_to_playlist(playlist.id, show_id)

    flash("Show added to Now Scouting", "success")
    return redirect(url_for("shows.list_shows"))


@playlists_bp.route("/scouting/shows/<show_id>/remove", methods=["POST"])
@login_required
def remove_show(show_id: str):
    user = get_current_user()
    service = PlaylistService()
    playlist = service.get_or_create_now_scouting(user.id)
    service.remove_show_from_playlist(playlist.id, show_id)

    flash("Show removed from Now Scouting", "success")
    return redirect(url_for("shows.list_shows"))
