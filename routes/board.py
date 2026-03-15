"""
Board routes — personal dashboard.
"""
from flask import Blueprint, render_template
from routes.auth import login_required, get_current_user
from services.board import BoardService

board_bp = Blueprint("board", __name__, url_prefix="/board")


@board_bp.route("/")
@login_required
def index():
    user = get_current_user()
    service = BoardService()

    context = service.get_board_data(user.id)

    return render_template("board/index.html", **context)
