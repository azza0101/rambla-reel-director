FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    RAMBLA_RUNTIME_MODE=cloud \
    RAMBLA_RETRIEVAL_RANKING=provider \
    RAMBLA_PROJECT_ROOT=/data/projects \
    RAMBLA_BROWSER_PROFILE_ROOT=/data/browser-profiles

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg chromium ca-certificates fonts-liberation \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY backend ./backend
COPY docs ./docs

RUN pip install --upgrade pip \
 && pip install . \
 && pip install "yt-dlp>=2026.8.22" "Pillow>=10,<12"

RUN mkdir -p /data/projects /data/browser-profiles

VOLUME ["/data"]
EXPOSE 8080

CMD ["sh", "-c", "exec uvicorn backend.app.curation_server:app --host 0.0.0.0 --port ${PORT:-8080}"]
