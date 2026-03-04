# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Working with me

Use the notes directory for planning and other research learning docs.

```sh
notes/
|-learnings/
|-feature_name/
    |-plans/
    |-learnings/
    |-<YYYY-mm-dd>_status.md
```

Where in each feature directory,`plans` will have plans to implement changes and `learnings` will have things we learned along the way (e.g. how Flask plays with spotify integration or common gotcha's from spotipy). After a feature is done we can move major learnings to the top learnings dir.

* The daily status docs are where we keep our current status of what we're working on, challenges we faced, what we will do next, and other context or references to learnings that would be useful after compactification.
* I will comment with `#!` in our docs or code to flag something we should discuss for review.

## Project Overview

Giglz is a Spotify-integrated Flask web app for scouting concert shows. Users add shows (artist, venue, date), the app finds artists' top tracks on Spotify and adds them to a "Scouting" playlist for pre-listening, then displays show info while music plays.

**Status: Deployed on Railway.** Core features complete: Spotify integration, SQLite persistence, multi-user auth, loved tracks, browser extension for scouting. Frontend has a dreampop aesthetic with Tailwind.

Built incrementally with Flask, Spotipy, and vanilla JavaScript.

## Commands

- **Install dependencies:** `uv sync`
- **Add a dependency:** `uv add <package>`
- **Run the app:** `uv run python app.py` (Flask dev server on http://127.0.0.1:5001)
- **Run with dev data:** `make dev` (uses `data-dev/` directory, starts Tailscale HTTPS)
- **Run tests:** `uv run pytest`
- **Run single test:** `uv run pytest tests/test_app.py::test_function_name -v`
- **Run linter:** `make lint` (runs pre-commit hooks)
- **Lint JS only:** `make lint-js` (Biome, works on untracked files)

### Database Migrations (Flask-Migrate)

- **Generate migration:** `make db-migrate msg="description"`
- **Apply migrations:** `make db-upgrade` (prod) or `make db-upgrade-dev` (dev data)
- **Rollback one:** `make db-downgrade` / `make db-downgrade-dev`
- **Reset dev DB:** `make db-reset-dev` (drops and recreates)

**CRITICAL: Never rename or delete migration files once deployed.** Alembic tracks the current revision ID in the database. If you rename `abc123_foo.py` to `def456_bar.py`, deployed databases will fail with "Can't locate revision 'abc123'". Only add new migrations on top of existing ones.

## Tech Stack

- Python 3.12, Flask, Spotipy (Spotify API wrapper), python-dotenv, Pydantic
- LLM extraction: OpenAI client via OpenRouter (Claude Haiku), Jina Reader for URL fetching
- Package manager: `uv` (lock file: `uv.lock`)
- Data persistence: SQLite with Flask-SQLAlchemy, Flask-Migrate for migrations
- Templates: Jinja2 (Flask) in `templates/`, Tailwind CSS via CDN

## Architecture

**app.py** — Flask routes and request handling.
- `GET /` — Home page with playlists front and center
- `GET /shows` — Browse all shows, create playlists
- `GET /import` — Import page (CSV, URL, manual)
- `GET /lineup/<name>` — View a playlist with player
- `POST /api/scout` — Browser extension endpoint (receives page text, extracts show)

**models.py** — Pydantic data models.
- `ShowSubmission` — User-provided form data (artists, venue, date, ticket_url)
- `Show` — Enriched with Spotify data (artist IDs, track URIs, playlist ID)
- `ImportStatus` — Enum: SUCCESS, FAILED, SKIPPED
- `ImportedUrl` — Tracks URL import attempts and outcomes

**spotify/** — Spotify abstraction layer.
- `SpotifyAPI` — Stateless wrapper around spotipy (search, top tracks, playlist management)
- `TokenManager` — Per-user OAuth token management with file-based caching

**show_extractor.py** — LLM-based show extraction.
- `extract_show(url)` — Fetches via Jina Reader, extracts with Haiku
- `extract_from_text(text)` — Extracts from raw text (used by browser extension, bypasses bot protection)

**db.py** — Database facade, single entry point for all persistence.
- `Database` class with methods for shows, imports, and per-user loved tracks
- Access via `get_db()` helper in Flask app context

**db_models.py** — SQLAlchemy models (Show, ShowTrack, ImportedUrl, UserLovedTrack).

**url_utils.py** — URL normalization (strips tracking params, normalizes format).

**config.py** — Central config from env vars (ports, paths, feature flags).

**extension/** — Chrome/Brave browser extension for one-click scouting.
- Click extension on any ticket page → extracts show via LLM → adds to playlist
- Bypasses bot protection (extension sends rendered page text, not URL)
- Session-based auth (uses Giglz login cookie)

**templates/** — Jinja2 templates with Tailwind styling.
- `base.html` — Layout with dreampop aesthetic (pink/teal, pixel font, scanlines)
- `macros.html` — Reusable components (input, button, card, show_card)
- `home.html` — Main page with import form, manual form, show list

## Environment Variables

Required in `.env` (loaded by python-dotenv):
- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`
- `SPOTIFY_REDIRECT_URI` (default: `http://127.0.0.1:5001/callback`)
- `HOST_USER_ID` — Spotify user ID of the host (playlist operations use host's account)
- `OPENROUTER_API_KEY` — For LLM-based show extraction

Optional:
- `ALLOWED_USER_IDS` — Comma-separated Spotify user IDs allowed to log in (host always allowed)
- `GIGLZ_DATA_DIR` — Directory for SQLite database and token cache (default: `data/`)
- `GIGLZ_DEBUG` — Enables debug file logging to `logs/`
- `GIGLZ_SHARE` — Set to `1` to bind to 0.0.0.0 for LAN access

## Testing

- Tests use `client` fixture (unauthenticated) or `host_client` fixture (authenticated as host)
- Spotify API calls are mocked — see `tests/test_spotify_client.py` for patterns
- Database tests use the app's SQLite with Flask test client

## Development Phases (from design doc)

- **Phase 1 (complete):** Flask with full page reloads, JSON persistence, Spotify playlist creation
- **Phase 2 (complete):** JavaScript-driven UI, SSE streaming for imports, SQLite persistence
- **Phase 3 (complete):** Railway deployment, multi-user support, browser extension
