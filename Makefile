.PHONY: dev serve serve-stop test lint lint-js docs docs-serve db-migrate db-upgrade db-upgrade-dev db-downgrade db-downgrade-dev db-reset-dev

# Development (separate data, Tailscale HTTPS for player)
dev:
	tailscale serve --bg http://127.0.0.1:5001
	@tailscale serve status
	GIGLZ_DATA_DIR=data-dev uv run python app.py

# Serve with Tailscale HTTPS (for sharing with friends)
serve:
	tailscale serve --bg http://127.0.0.1:5001
	@echo ""
	@tailscale serve status
	@echo ""
	GIGLZ_SHARE=1 uv run python app.py

# Stop Tailscale HTTPS proxy
serve-stop:
	tailscale serve off

# Run tests
test:
	uv run pytest

# Run linter
lint:
	uv run pre-commit run --all-files

# Run JS linter directly (works on untracked files too)
lint-js:
	biome check static/js/

# --- Documentation ---

# Build docs to site/
docs:
	uv run --group docs mkdocs build

# Serve docs locally (auto-reload)
docs-serve:
	uv run --group docs mkdocs serve

# --- Database migrations ---

# Generate migration from model changes (shared across envs)
db-migrate:
	uv run flask db migrate -m "$(msg)"

# Apply pending migrations (prod)
db-upgrade:
	uv run flask db upgrade

# Apply pending migrations (dev)
db-upgrade-dev:
	GIGLZ_DATA_DIR=data-dev uv run flask db upgrade

# Rollback one migration (prod)
db-downgrade:
	uv run flask db downgrade

# Rollback one migration (dev)
db-downgrade-dev:
	GIGLZ_DATA_DIR=data-dev uv run flask db downgrade

# Reset dev database (drop all, recreate)
db-reset-dev:
	rm -f data-dev/giglz.db
	GIGLZ_DATA_DIR=data-dev uv run flask db upgrade
