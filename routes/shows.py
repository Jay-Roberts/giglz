"""
Shows routes — list shows, add show form/submit.

Thin layer: parse request, call ShowService, render response.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from pydantic import ValidationError
from routes.auth import login_required, get_current_user
from db_models import ShowStatus
from services.shows import ShowService, DuplicateShowError
from services.playlists import PlaylistService
from schemas import AddShowRequest, ShowsFilterRequest

shows_bp = Blueprint("shows", __name__, url_prefix="/shows")


@shows_bp.route("/")
@login_required
def list_shows():
    user = get_current_user()
    show_service = ShowService()
    playlist_service = PlaylistService()

    # Parse filters from query params
    filters = ShowsFilterRequest.from_args(request.args)

    # Get filtered shows with heat
    shows_with_heat = show_service.list_shows_filtered(
        user_id=user.id,
        status_filter=ShowStatus(filters.status) if filters.status else None,
        date_from=filters.date_from,
        date_to=filters.date_to,
        heat_min=filters.heat_min,
    )

    # Existing context
    playlist = playlist_service.get_or_create_now_scouting(user.id)
    scouting_show_ids = playlist_service.get_scouting_show_ids(playlist.id)
    statuses = show_service.get_user_show_statuses(user.id)
    statuses_json = {k: v.value for k, v in statuses.items()}
    status_options = {s.name: s.value for s in ShowStatus}

    return render_template(
        "shows/list.html",
        shows_with_heat=shows_with_heat,
        scouting_show_ids=scouting_show_ids,
        statuses=statuses_json,
        status_options=status_options,
        filters=filters,
    )


@shows_bp.route("/add", methods=["GET"])
@login_required
def add_form():
    return render_template("shows/add.html")


@shows_bp.route("/add", methods=["POST"])
@login_required
def add_submit():
    try:
        req = AddShowRequest.from_form(request.form)
    except ValidationError as e:
        for error in e.errors():
            field = error["loc"][0]
            error_type = error["type"]
            if field == "date":
                if error_type == "date_from_datetime_parsing":
                    flash("Invalid date format", "error")
                else:
                    flash("Date is required (YYYY-MM-DD)", "error")
            else:
                messages = {
                    "artists": "At least one artist is required",
                    "venue": "Venue is required",
                    "city": "City is required",
                }
                flash(messages.get(field, str(error["msg"])), "error")
        return render_template("shows/add.html"), 400

    if not req.artist_names:
        flash("At least one artist is required", "error")
        return render_template("shows/add.html"), 400

    service = ShowService()
    try:
        service.add_show(
            artist_names=req.artist_names,
            show_date=req.date,
            venue_name=req.venue,
            city_name=req.city,
            ticket_url=req.ticket_url,
        )
    except DuplicateShowError as e:
        flash(str(e), "error")
        return render_template("shows/add.html"), 400

    flash(f"Added show: {', '.join(req.artist_names)} at {req.venue}", "success")
    return redirect(url_for("shows.list_shows"))


