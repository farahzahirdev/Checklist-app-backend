"""Notification orchestration service."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session
from app.tasks.email_tasks import send_email_task
from app.services.email_templates import get_template_renderer
from app.models.user import User
from app.models.assessment import Assessment
from app.models.report import Report
from app.models.company import Company

logger = logging.getLogger(__name__)


class NotificationEventType(StrEnum):
    """Supported notification event types."""

    ASSESSMENT_STARTED = "assessment_started"
    ASSESSMENT_SUBMITTED = "assessment_submitted"
    ASSESSMENT_REVIEW_COMPLETED = "assessment_review_completed"
    REPORT_CHANGES_REQUESTED = "report_changes_requested"
    REPORT_APPROVED = "report_approved"
    REPORT_PUBLISHED = "report_published"
    ASSESSMENT_EXPIRED = "assessment_expired"
    PASSWORD_RESET_ISSUED = "password_reset_issued"


@dataclass
class NotificationEvent:
    """Structured notification event."""

    event_type: NotificationEventType
    user_id: Optional[UUID] = None
    assessment_id: Optional[UUID] = None
    report_id: Optional[UUID] = None
    actor_id: Optional[UUID] = None
    context: dict | None = None  # Additional context for templating


class NotificationService:
    """Orchestrate notifications: event → recipients → template → task."""

    # Map event types to templates and subject keys
    EVENT_CONFIG = {
        NotificationEventType.ASSESSMENT_STARTED: {
            "template": "assessment_started.html",
            "subject_key": "assessment_started",
            "recipients": ["customer"],
        },
        NotificationEventType.ASSESSMENT_SUBMITTED: {
            "template": "assessment_submitted.html",
            "subject_key": "assessment_submitted",
            "recipients": ["customer"],
        },
        NotificationEventType.ASSESSMENT_REVIEW_COMPLETED: {
            "template": "assessment_review_completed.html",
            "subject_key": "assessment_review_completed",
            "recipients": ["customer"],
        },
        NotificationEventType.REPORT_CHANGES_REQUESTED: {
            "template": "report_changes_requested.html",
            "subject_key": "report_changes_requested",
            "recipients": ["customer"],
        },
        NotificationEventType.REPORT_APPROVED: {
            "template": "report_approved.html",
            "subject_key": "report_approved",
            "recipients": ["customer"],
        },
        NotificationEventType.REPORT_PUBLISHED: {
            "template": "report_published.html",
            "subject_key": "report_published",
            "recipients": ["customer", "company_billing"],
        },
        NotificationEventType.ASSESSMENT_EXPIRED: {
            "template": "assessment_expired.html",
            "subject_key": "assessment_expired",
            "recipients": ["customer"],
        },
        NotificationEventType.PASSWORD_RESET_ISSUED: {
            "template": "password_reset_issued.html",
            "subject_key": "password_reset_issued",
            "recipients": ["customer"],
        },
    }

    def __init__(self, db: Session):
        self.db = db
        self.renderer = get_template_renderer()

    def notify(self, event: NotificationEvent) -> bool:
        """
        Process a notification event and enqueue email task.

        Args:
            event: NotificationEvent with type, IDs, and context

        Returns:
            True if task enqueued successfully, False otherwise
        """
        if event.event_type not in self.EVENT_CONFIG:
            logger.warning(f"Unknown event type: {event.event_type}")
            return False

        try:
            config = self.EVENT_CONFIG[event.event_type]

            # Resolve recipients
            recipients = self._resolve_recipients(event, config["recipients"])
            if not recipients:
                logger.warning(
                    f"No recipients resolved for event {event.event_type} (user_id={event.user_id})"
                )
                return False

            # Build template context
            context = self._build_context(event, config)

            # Render templates
            html_content = self.renderer.render_html(config["template"], context)
            text_content = self.renderer.render_text(config["template"], context)

            # Get subject (use event type as fallback; ideally fetch from i18n)
            subject = context.get("subject", config["subject_key"])

            # Generate correlation ID for tracking
            correlation_id = f"{event.event_type}_{datetime.now().timestamp()}"

            # Enqueue email task
            send_email_task.delay(
                to_addresses=recipients,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
                correlation_id=correlation_id,
            )

            logger.info(
                f"[{correlation_id}] Notification queued for {event.event_type} to {recipients}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Error processing notification {event.event_type}: {e}", exc_info=True
            )
            return False

    def _resolve_recipients(
        self, event: NotificationEvent, recipient_types: list[str]
    ) -> list[str]:
        """Resolve email addresses for recipient types."""
        recipients = set()

        for recipient_type in recipient_types:
            if recipient_type == "customer":
                if event.user_id:
                    user = self.db.get(User, event.user_id)
                    if user and user.email:
                        recipients.add(user.email)

            elif recipient_type == "company_billing":
                # Resolve company billing email
                company_id = self._get_company_id(event)
                if company_id:
                    company = self.db.get(Company, company_id)
                    if company and company.email:
                        recipients.add(company.email)

        return list(recipients)

    def _get_company_id(self, event: NotificationEvent) -> UUID | None:
        """Resolve company ID from event context."""
        if event.context and "company_id" in event.context:
            return event.context["company_id"]

        # Try to infer from assessment
        if event.assessment_id:
            assessment = self.db.get(Assessment, event.assessment_id)
            if assessment and assessment.company_id:
                return assessment.company_id

        # Try to infer from report
        if event.report_id:
            report = self.db.get(Report, event.report_id)
            if report and report.company_id:
                return report.company_id

        return None

    def _build_context(self, event: NotificationEvent, config: dict) -> dict:
        """Build template context from event data."""
        context = event.context or {}

        # Add standard context based on event type
        if event.user_id:
            user = self.db.get(User, event.user_id)
            if user:
                context.setdefault("customer_email", user.email)
                context.setdefault("customer_name", user.email.split("@")[0])

        if event.assessment_id:
            assessment = self.db.get(Assessment, event.assessment_id)
            if assessment:
                context.setdefault("assessment_id", str(assessment.id))
                context.setdefault("assessment_status", assessment.status)
                if assessment.checklist:
                    context.setdefault("checklist_title", assessment.checklist.version)

        if event.report_id:
            report = self.db.get(Report, event.report_id)
            if report:
                context.setdefault("report_id", str(report.id))
                context.setdefault("report_status", report.status)
                context.setdefault("report_code", report.report_code or "")

        if event.actor_id:
            actor = self.db.get(User, event.actor_id)
            if actor:
                context.setdefault("actor_email", actor.email)

        # Use event type as subject fallback
        context.setdefault("subject", f"{event.event_type.replace('_', ' ').title()}")

        return context


def notify_event(db: Session, event: NotificationEvent) -> bool:
    """Convenience function to notify of an event."""
    service = NotificationService(db)
    return service.notify(event)
