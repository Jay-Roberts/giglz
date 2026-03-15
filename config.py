from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASEDIR = Path(__file__).parent


class Settings(BaseSettings):
    """Application configuration from environment variables.

    Uses pydantic-settings: env vars auto-map to fields (SECRET_KEY -> secret_key).
    Falls back to .env file if env var not set.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Required
    secret_key: str

    # Database
    database_url: str = f"sqlite:///{BASEDIR / 'data' / 'giglz.db'}"

    # Email
    resend_api_key: str = ""

    # Auth
    magic_link_expiry_minutes: int = 15
    base_url: str = "http://127.0.0.1:5001"
    dev_mode: bool = False

    # Spotify
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_redirect_uri: str = "http://127.0.0.1:5001/spotify/callback"
    spotify_top_tracks_limit: int = 5
    spotify_artist_search_limit: int = 5
