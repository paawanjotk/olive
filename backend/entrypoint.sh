#!/bin/sh
set -e

# Worker mode: run the Celery worker, skip migrations (the API container owns them).
if [ "$1" = "worker" ]; then
  echo "Starting Celery worker..."
  exec celery -A app.worker worker --loglevel=info --pool=threads --concurrency=4
fi

echo "Running database migrations..."
alembic upgrade head

echo "Starting Ollive backend..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
