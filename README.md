# giglz

Spotify-integrated Flask web app for scouting concert shows. Add upcoming shows, auto-build a playlist of artists' top tracks, and listen together with friends.

## Quick Start

```sh
uv sync
cp .env.example .env  # Edit with your values
uv run python app.py
```

App runs at http://127.0.0.1:5001

## Setup

### Spotify App

1. [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) → Create app
2. Add redirect URI: `http://127.0.0.1:5001/callback`
3. Copy Client ID and Secret to `.env`

### Environment Variables

```sh
SPOTIFY_CLIENT_ID=your-client-id
SPOTIFY_CLIENT_SECRET=your-client-secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:5001/callback
HOST_USER_ID=your-spotify-user-id

# Optional
FLASK_SECRET_KEY=generate-with-secrets-module
OPENROUTER_API_KEY=for-url-import-feature
```

Find your Spotify user ID at spotify.com/account or in your profile URL.

## Development

```sh
make dev          # Run with separate dev data
make lint         # Run all checks
uv run pytest     # Run tests
```

Install git hooks:
```sh
uv run pre-commit install
```

## Deployment (Railway)

*Coming soon*

Key points:
- Set `GIGLZ_DATA_DIR=/data` with a Railway Volume for persistence
- Add `ALLOWED_USER_IDS=friend1,friend2` for access control
- Gunicorn runs via Procfile

## Sharing with Friends (Tailscale)

For local hosting with friends on your network:

```sh
make serve        # Start Tailscale HTTPS
make serve-stop   # Stop proxy
```

Friends install Tailscale, you invite them, share your URL.

Cards-only view (no playback controls): `/playlist/<name>/shows`
