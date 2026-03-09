import os
from pathlib import Path
from dotenv import load_dotenv

#! Will this hold on railway
load_dotenv()

#! Will this hold on railway
BASEDIR = Path(__file__).parent


#! Any reason we can't rename this?
class Config:
    SECRET_KEY = os.environ["SECRET_KEY"]
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASEDIR / 'data' / 'giglz.db'}"
    )
    RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
    MAGIC_LINK_EXPIRY_MINUTES = 15
    #! Will this hold on railway
    BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:5001")
    DEV_MODE = os.environ.get("GIGLZ_DEV_MODE", "").lower() in ("1", "true")
    SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
    SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
    SPOTIFY_TOP_TRACKS_LIMIT = 5
