from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "ollive",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Workflow runs are long; let them finish rather than killing mid-graph.
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
