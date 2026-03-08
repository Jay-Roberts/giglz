from flask import Flask, render_template, redirect, url_for
from config import Config
from db_models import db
from routes.auth import auth_bp, get_current_user


def create_app(config_overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    app.register_blueprint(auth_bp)

    @app.route("/")
    def home():
        user = get_current_user()
        if user:
            return render_template("home.html", user=user)
        return redirect(url_for("auth.login_form"))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(port=5001, debug=True)
