FROM python:3.10-slim

WORKDIR /app

RUN pip install --no-cache-dir poetry
RUN poetry config virtualenvs.create false

# ── SDK install ────────────────────────────────────────────────────────────────
# Local dev  (docker-compose):  sdk/ is bind-mounted at /sdk, installed editable
# CI / prod  (GitHub Actions):  sdk/ is COPY'd into the image at build time
# PyPI future:                  replace both paths with `pip install observe-me`
ARG SDK_PATH=sdk
COPY ${SDK_PATH} /sdk
RUN pip install --no-cache-dir /sdk

# ── Backend deps ───────────────────────────────────────────────────────────────
COPY backend/pyproject.toml backend/poetry.lock* ./
RUN poetry lock --no-interaction --no-ansi \
 && poetry install --with dev --no-interaction --no-ansi --no-root \
 && pip install --no-cache-dir slack-bolt "aiohttp==3.9.5"

COPY backend/. .

EXPOSE 8000
ENTRYPOINT ["sh", "entrypoint.sh"]
