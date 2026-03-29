FROM python:3.12-slim

WORKDIR /app

# Tailwind standalone CLI (no Node required)
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && curl -sLO https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64 \
    && chmod +x tailwindcss-linux-x64 \
    && mv tailwindcss-linux-x64 /usr/local/bin/tailwindcss \
    && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

# Python deps first (cached layer)
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# App code
COPY . .

# Build CSS
RUN tailwindcss -i static/css/main.css -o static/css/output.css --minify

# Create data dir for SQLite
RUN mkdir -p /app/data

# Non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

ENV PORT=8080
EXPOSE $PORT

CMD gunicorn -b 0.0.0.0:$PORT "app:create_app()"
