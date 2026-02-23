"""Application configuration from environment variables."""

import logging
import os
from datetime import datetime
from pathlib import Path

_LOG_FMT = "%(name)s %(levelname)s %(message)s"

# App identity - change this to rebrand
APP_NAME = "giglz"
APP_DISPLAY_NAME = "GIGLZ"

# Data directory - allows separating dev and prod data
# Usage: GIGLZ_DATA_DIR=data-dev uv run python app.py
DATA_DIR = Path(os.environ.get("GIGLZ_DATA_DIR", "data")).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_NAME = f"{APP_NAME}.db"
SQL_ALCHEMY_DB_URI = DATA_DIR / DB_NAME

SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATA_DIR / DB_NAME}"
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Network sharing - bind to 0.0.0.0 to allow access from other devices on LAN
# Usage: GIGLZ_SHARE=1 uv run python app.py
SHARE_ON_NETWORK = bool(os.environ.get("GIGLZ_SHARE"))

# Port - default 5001 to avoid macOS AirPlay Receiver conflict on 5000
PORT = int(os.environ.get("GIGLZ_PORT", "5001"))

# Host user ID - this user owns the Spotify playlist and is used for playlist operations
# All logged-in users can import shows, but tracks are added using the host's account
HOST_USER_ID = os.environ.get("HOST_USER_ID")

# Allowed user IDs - only these Spotify users can log in
# Host is always allowed. Add friends via comma-separated env var.
# Usage: ALLOWED_USER_IDS=friend1_id,friend2_id
_allowed_raw = os.environ.get("ALLOWED_USER_IDS", "")
ALLOWED_USER_IDS: set[str] = {HOST_USER_ID} if HOST_USER_ID else set()
ALLOWED_USER_IDS |= set(filter(None, (uid.strip() for uid in _allowed_raw.split(","))))

# Flask session secret key - generate with: python -c "import secrets; print(secrets.token_hex(32))"
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-insecure-change-me")


def setup_logging() -> None:
    """Configure logging. Call once at app startup."""
    logging.basicConfig(level=logging.INFO, format=_LOG_FMT)

    if os.environ.get("GIGLZ_DEBUG"):
        log_dir = Path("logs") / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(str(log_dir / f"{APP_NAME}.log"))
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(_LOG_FMT))
        logging.getLogger().addHandler(fh)
        for name in ("app", "spotify_client", "show_extractor", "db"):
            logging.getLogger(name).setLevel(logging.DEBUG)


# User-facing display name for ShowLists (internal name is "ShowList")
SHOWLIST_DISPLAY_NAME = "Lineup"
