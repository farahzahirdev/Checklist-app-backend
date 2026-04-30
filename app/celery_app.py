import logging

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "checklist_app",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Auto-discover tasks from all registered app modules
celery_app.autodiscover_tasks(["app.tasks"])

# Import tasks to ensure they are registered
# This avoids circular import by importing after celery_app is fully initialized
try:
    from app.tasks import bulk_import  # noqa: F401
except ImportError:
    # Tasks will be registered when imported elsewhere
    pass

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_default_queue="celery",
    task_routes={
        "app.tasks.bulk_import.*": {"queue": "celery"},  # Use celery queue that worker is listening to
    },
)

logging.getLogger(__name__).info("Configured Celery app with broker %s", settings.celery_broker_url)
