from flask import Flask, redirect, url_for
from config import Config
from db_models import db
from routes.auth import auth_bp, get_current_user
from routes.shows import shows_bp


def create_app(config_overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    app.register_blueprint(auth_bp)
    app.register_blueprint(shows_bp)

    @app.route("/")
    def home():
        user = get_current_user()
        if user:
            return redirect(url_for("shows.list_shows"))
        return redirect(url_for("auth.login_form"))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(port=5001, debug=True)
