"""
Shows routes — list shows, add show form/submit.

Thin layer: parse request, call ShowService, render response.
"""
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from routes.auth import login_required
from services.shows import ShowService, DuplicateShowError

shows_bp = Blueprint("shows", __name__, url_prefix="/shows")


@shows_bp.route("/")
@login_required
def list_shows():
    service = ShowService()
    shows = service.list_shows()
    return render_template("shows/list.html", shows=shows)


@shows_bp.route("/add", methods=["GET"])
@login_required
def add_form():
    return render_template("shows/add.html")


@shows_bp.route("/add", methods=["POST"])
@login_required
def add_submit():
    # parse form
    artists_raw = request.form.get("artists", "").strip()
    date_raw = request.form.get("date", "").strip()
    venue = request.form.get("venue", "").strip()
    city = request.form.get("city", "").strip()
    ticket_url = request.form.get("ticket_url", "").strip() or None

    # validate
    errors = []
    if not artists_raw:
        errors.append("At least one artist is required")
    if not date_raw:
        errors.append("Date is required")
    if not venue:
        errors.append("Venue is required")
    if not city:
        errors.append("City is required")

    if errors:
        for error in errors:
            flash(error, "error")
        return render_template("shows/add.html"), 400

    # parse artists (comma-separated)
    artist_names = [a.strip() for a in artists_raw.split(",") if a.strip()]

    # parse date
    try:
        show_date = datetime.strptime(date_raw, "%Y-%m-%d").date()
    except ValueError:
        flash("Invalid date format", "error")
        return render_template("shows/add.html"), 400

    # create show
    service = ShowService()
    try:
        service.add_show(
            artist_names=artist_names,
            show_date=show_date,
            venue_name=venue,
            city_name=city,
            ticket_url=ticket_url,
        )
    except DuplicateShowError as e:
        flash(str(e), "error")
        return render_template("shows/add.html"), 400

    flash(f"Added show: {', '.join(artist_names)} at {venue}", "success")
    return redirect(url_for("shows.list_shows"))
