"""
Spotify OAuth routes — connect and callback.
"""
from flask import Blueprint, redirect, url_for, request, flash, session
from routes.auth import login_required, get_current_user
from spotify.oauth import get_auth_url, exchange_code
from services.auth import disconnect_spotify
from db_models import db, SpotifyToken

spotify_bp = Blueprint("spotify", __name__, url_prefix="/spotify")


@spotify_bp.route("/connect")
@login_required
def connect():
    """Redirect to Spotify authorize URL."""
    auth_url = get_auth_url()
    return redirect(auth_url)


@spotify_bp.route("/callback")
@login_required
def callback():
    """Handle OAuth callback, save tokens."""
    error = request.args.get("error")
    if error:
        flash(f"Spotify connection failed: {error}", "error")
        return redirect(url_for("shows.list_shows"))

    code = request.args.get("code")
    if not code:
        flash("Spotify connection failed: no code received", "error")
        return redirect(url_for("shows.list_shows"))

    # Exchange code for tokens
    token_info = exchange_code(code)

    user = get_current_user()
    expires_at = token_info.expires_at_datetime

    # Upsert token
    existing = SpotifyToken.query.filter_by(user_id=user.id).first()
    if existing:
        existing.access_token = token_info.access_token
        existing.refresh_token = token_info.refresh_token
        existing.expires_at = expires_at
    else:
        token = SpotifyToken(
            user_id=user.id,
            access_token=token_info.access_token,
            refresh_token=token_info.refresh_token,
            expires_at=expires_at,
        )
        db.session.add(token)

    db.session.commit()

    flash("Spotify connected!", "success")
    return redirect(url_for("shows.list_shows"))


@spotify_bp.route("/disconnect", methods=["POST"])
@login_required
def disconnect():
    """Disconnect Spotify — remove tokens."""
    user_id = session.get("user_id")

    # Command
    disconnect_spotify(user_id)

    # Render
    flash("Spotify disconnected", "info")
    return redirect(url_for("shows.list_shows"))
