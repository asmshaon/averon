# Averon AI runner (stdlib-only Python + ffmpeg). Week 2 can copy ai/ into the Laravel worker image.
FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY averon_ai ./averon_ai
COPY run_turn.py ./
RUN useradd --system --no-create-home runner
USER runner
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENTRYPOINT []
