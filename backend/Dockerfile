FROM python:3.10-slim

WORKDIR /app

RUN pip install --no-cache-dir poetry
RUN poetry config virtualenvs.create false

# ── Backend deps ───────────────────────────────────────────────────────────────
COPY backend/pyproject.toml backend/poetry.lock* ./
RUN poetry lock --no-interaction --no-ansi \
 && poetry install --with dev --no-interaction --no-ansi --no-root \
 && pip install --no-cache-dir slack-bolt "aiohttp==3.9.5"

COPY backend/. .

EXPOSE 8000
ENTRYPOINT ["sh", "entrypoint.sh"]
