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

## Deploy to Railway

```sh
railway login
railway init
railway up
```

Add a **volume** for database persistence (Dashboard → Service → Volumes):
- Mount path: `/data`

Set variables:
```sh
railway variables set GIGLZ_DATA_DIR=/data
railway variables set SPOTIFY_CLIENT_ID=xxx
railway variables set SPOTIFY_CLIENT_SECRET=xxx
railway variables set SPOTIFY_REDIRECT_URI=https://YOUR-APP.up.railway.app/callback
railway variables set HOST_USER_ID=your-spotify-id
railway variables set FLASK_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
```

Update Spotify Dashboard → Your App → Redirect URIs with your Railway URL.

<details>
<summary>Optional variables</summary>

```sh
railway variables set OPENROUTER_API_KEY=xxx      # URL import feature
railway variables set ALLOWED_USER_IDS=id1,id2   # Allow friends to log in
```
</details>

<details>
<summary>First deploy: run migrations manually</summary>

```sh
railway shell
flask db upgrade
exit
```
After the first deploy, migrations run automatically via Procfile.
</details>

> **Note:** Volumes require Railway Pro ($5/mo). Free tier resets the database on every deploy.

## Sharing with Friends (Tailscale)

For local hosting with friends on your network:

```sh
make serve        # Start Tailscale HTTPS
make serve-stop   # Stop proxy
```

Friends install Tailscale, you invite them, share your URL.

Cards-only view (no playback controls): `/playlist/<name>/shows`
