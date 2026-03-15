from functools import wraps
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    g,
)
from pydantic import ValidationError
from services.auth import request_login, verify_token, AuthError, TokenExpiredError
from schemas import LoginRequest

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def get_current_user():
    """Load current user from session into g.user."""
    if "user_id" not in session:
        g.user = None
        return None

    if not hasattr(g, "user") or g.user is None:
        from db_models import db, User

        g.user = db.session.get(User, session["user_id"])

    return g.user


def login_required(f):
    """Decorator to require authentication."""

    @wraps(f)
    def decorated(*args, **kwargs):
        if get_current_user() is None:
            return redirect(url_for("auth.login_form"))
        return f(*args, **kwargs)

    return decorated


@auth_bp.route("/login", methods=["GET"])
def login_form():
    return render_template("auth/login.html")


@auth_bp.route("/login", methods=["POST"])
def login_submit():
    try:
        req = LoginRequest(email=request.form.get("email", ""))
    except ValidationError:
        flash("Please enter a valid email address", "error")
        return render_template("auth/login.html"), 400

    try:
        request_login(req.email)
    except Exception:
        flash("Couldn't send login email. Please try again.", "error")
        return render_template("auth/login.html"), 500

    return render_template("auth/check_email.html", email=req.email)


@auth_bp.route("/verify")
def verify():
    token = request.args.get("token", "")

    if not token:
        return render_template("auth/error.html", message="Missing login token"), 400

    try:
        user = verify_token(token)
    except TokenExpiredError:
        return render_template(
            "auth/error.html",
            message="This login link has expired. Please request a new one.",
        ), 400
    except AuthError as e:
        return render_template("auth/error.html", message=str(e)), 400

    # create session (regenerate to prevent fixation)
    session.clear()
    session["user_id"] = user.id
    session.permanent = True

    return redirect(url_for("home"))


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login_form"))
