from flask import Flask, redirect, url_for
from config import Settings
from db_models import db
from routes.auth import auth_bp, get_current_user
from routes.shows import shows_bp
from routes.playlists import playlists_bp
from routes.spotify import spotify_bp
from routes.api import api_bp


def create_app(config_overrides: dict | None = None):
    settings = Settings(**(config_overrides or {}))

    app = Flask(__name__)
    # Flask internals require these specific keys in app.config
    app.config["SECRET_KEY"] = settings.secret_key
    app.config["SQLALCHEMY_DATABASE_URI"] = settings.database_url

    # Store for direct access
    app.extensions["settings"] = settings

    db.init_app(app)

    with app.app_context():
        db.create_all()

    app.register_blueprint(auth_bp)
    app.register_blueprint(shows_bp)
    app.register_blueprint(playlists_bp)
    app.register_blueprint(spotify_bp)
    app.register_blueprint(api_bp)

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
