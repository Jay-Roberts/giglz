"""
Import routes — CSV upload form and handler.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from routes.auth import login_required, get_current_user
from services.imports import ImportService

imports_bp = Blueprint("imports", __name__)


@imports_bp.route("/import", methods=["GET"])
@login_required
def upload_form():
    return render_template("imports/upload.html")


@imports_bp.route("/import", methods=["POST"])
@login_required
def upload():
    user = get_current_user()
    file = request.files.get("csv_file")

    if not file or not file.filename:
        flash("No file selected", "error")
        return redirect(url_for("imports.upload_form"))

    service = ImportService()
    result = service.import_csv(user.id, file)

    # Build flash message
    msg = f"Imported {result.success} shows"
    if result.skipped:
        msg += f" ({result.skipped} skipped)"
    if result.failed:
        msg += f" ({result.failed} failed)"
    if result.not_found_artists:
        unique_artists = list(set(result.not_found_artists))
        msg += f". Artists not found on Spotify: {', '.join(unique_artists[:5])}"
        if len(unique_artists) > 5:
            msg += f" (+{len(unique_artists) - 5} more)"

    flash(msg, "info")
    return redirect(url_for("shows.list_shows"))
