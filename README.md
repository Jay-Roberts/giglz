# Gig Landing Zone (giglz)

When my friends and I go to a new city we look for local venues and see what gigs are happening. We open 100 tabs, check the bands out on Spotify, and then try to cross reference who was playing where and when. This sucks. That's why I'm making Gig Landing Zone (a.k.a giglz).

The idea is to have all the shows you want to see in one spot where you can easily make Spotify playlists of them, keep track of the bands you'd love to see, and coordinate with your friends on where to go.

It's also a personal project to learn a bit about web apps and practice some fun data engineering. So the Python code around the data architecture is pretty carefully designed, but the front end UI... is more of a vibe.

Under the hood, giglz is a Spotify-integrated Flask application with a small SQLite database backend. The instructions below are my own notes and may drift over time but hopefully are enough for you to deploy this yourself without too much headache. Happy listening!

## Prerequisites

1. **Spotify Developer App**
   - [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) → Create app
   - Note your Client ID and Client Secret
   - Add redirect URI (depends on deployment, see below)

2. **Find your Spotify User ID**
   - Go to spotify.com/account or check your profile URL: `open.spotify.com/user/<your-id>`

3. **Install dependencies**
   ```sh
   uv sync
   cp .env.example .env
   ```

## Deployment Options

### Local (Just You)

Run on your machine for personal use.

```sh
# .env
SPOTIFY_CLIENT_ID=your-client-id
SPOTIFY_CLIENT_SECRET=your-client-secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:5001/callback
HOST_USER_ID=your-spotify-user-id
```

Add `http://127.0.0.1:5001/callback` to your Spotify app's redirect URIs.

```sh
uv run python app.py
```

App runs at http://127.0.0.1:5001

### Railway (Share with Friends)

Deploy to the cloud. Friends can access via URL, limited to Spotify test users you've added.

```sh
railway login
railway init
railway up
```

**Add a volume** for database persistence (Dashboard → Service → Volumes):
- Mount path: `/data`

> **Note:** Volumes _may_ require Railway Pro ($5/mo). Free tier resets the database on every deploy.

**Set environment variables:**
```sh
railway variables set GIGLZ_DATA_DIR=/data
railway variables set SPOTIFY_CLIENT_ID=xxx
railway variables set SPOTIFY_CLIENT_SECRET=xxx
railway variables set SPOTIFY_REDIRECT_URI=https://YOUR-APP.up.railway.app/callback
railway variables set HOST_USER_ID=your-spotify-id
railway variables set FLASK_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
```

**Update Spotify Dashboard** → Your App → Redirect URIs with your Railway URL.

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

### Tailscale (LAN Sharing)

> **Use at your own risk.** This is experimental and may not be maintained.

Share locally with friends on your Tailscale network without deploying to the cloud.

```sh
make serve        # Start Tailscale HTTPS proxy
make serve-stop   # Stop proxy
```

Friends install Tailscale, you invite them, share your Tailscale URL.

## Development

```sh
make dev          # Run with separate dev data directory
make lint         # Run all checks (ruff, biome, pre-commit)
uv run pytest     # Run tests
```

Install git hooks:
```sh
uv run pre-commit install
```
