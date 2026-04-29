"""Celery task package."""

from app.tasks.bulk_import import create_checklist_task

__all__ = ["create_checklist_task"]
