import logging
from datetime import timedelta

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
try:
    from app.tasks import bulk_import  # noqa: F401
except ImportError:
    pass

try:
    from app.tasks import lifecycle  # noqa: F401
except ImportError:
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
        "app.tasks.bulk_import.*": {"queue": "celery"},
        "lifecycle.*": {"queue": "celery"},
    },
    beat_schedule={
        # Expire stale assessments every hour (enforces 7-day window)
        "expire-stale-assessments": {
            "task": "lifecycle.expire_stale_assessments",
            "schedule": timedelta(hours=1),
        },
        # Purge evidence files every hour (picks up anything past 48h retention)
        "purge-assessment-evidence": {
            "task": "lifecycle.purge_assessment_evidence",
            "schedule": timedelta(hours=1),
        },
    },
)

logging.getLogger(__name__).info("Configured Celery app with broker %s", settings.celery_broker_url)
