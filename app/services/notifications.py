"""Notification orchestration service."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Optional
from uuid import UUID
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.tasks.email_tasks import send_email_now, send_email_task
from app.services.audit_log import create_audit_log
from app.services.email_templates import get_template_renderer
from app.models.user import User, UserRole
from app.models.assessment import Assessment
from app.models.report import Report
from app.models.company import Company
from app.core.config import get_settings
from app.services.settings_manager import get_runtime_int
from app.utils.i18n import DEFAULT_LANGUAGE_CODE

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
    PAYMENT_SUCCESS = "payment_success"
    SIGNUP_WELCOME = "signup_welcome"
    EMAIL_VERIFICATION_REQUESTED = "email_verification_requested"
    MFA_SUPPORT_REQUEST = "mfa_support_request"


@dataclass
class NotificationEvent:
    """Structured notification event."""

    event_type: NotificationEventType
    user_id: Optional[UUID] = None
    assessment_id: Optional[UUID] = None
    report_id: Optional[UUID] = None
    actor_id: Optional[UUID] = None
    lang_code: str = DEFAULT_LANGUAGE_CODE
    context: dict | None = None  # Additional context for templating


class NotificationService:
    """Orchestrate notifications: event -> recipients -> template -> task."""

    # Map event types to templates and subject keys
    EVENT_CONFIG = {
        NotificationEventType.ASSESSMENT_STARTED: {
            "template": "assessment_started.html",
            "subject": {"cs": "Hodnocení bylo zahájeno", "en": "Assessment started"},
            "recipients": ["customer"],
        },
        NotificationEventType.ASSESSMENT_SUBMITTED: {
            "template": "assessment_submitted.html",
            "subject": {"cs": "Hodnocení bylo odesláno", "en": "Assessment submitted"},
            "recipients": ["customer", "admin"],
        },
        NotificationEventType.ASSESSMENT_REVIEW_COMPLETED: {
            "template": "assessment_review_completed.html",
            "subject": {"cs": "Kontrola hodnocení je dokončena", "en": "Assessment review completed"},
            "recipients": ["admin"],
        },
        NotificationEventType.REPORT_CHANGES_REQUESTED: {
            "template": "report_changes_requested.html",
            "subject": {"cs": "Zpráva vyžaduje změny", "en": "Report changes requested"},
            "recipients": ["actor"],
        },
        NotificationEventType.REPORT_APPROVED: {
            "template": "report_approved.html",
            "subject": {"cs": "Zpráva byla schválena", "en": "Report approved"},
            "recipients": ["actor"],
        },
        NotificationEventType.REPORT_PUBLISHED: {
            "template": "report_published.html",
            "subject": {"cs": "Zpráva byla zveřejněna", "en": "Report published"},
            "recipients": ["customer", "company_billing"],
        },
        NotificationEventType.ASSESSMENT_EXPIRED: {
            "template": "assessment_expired.html",
            "subject": {"cs": "Platnost hodnocení vypršela", "en": "Assessment expired"},
            "recipients": ["customer"],
        },
        NotificationEventType.PASSWORD_RESET_ISSUED: {
            "template": "password_reset_issued.html",
            "subject": {"cs": "Heslo bylo resetováno", "en": "Password reset issued"},
            "recipients": ["customer"],
        },
        NotificationEventType.PAYMENT_SUCCESS: {
            "template": "payment_success.html",
            "subject": {"cs": "Platba byla úspěšná", "en": "Payment successful"},
            "recipients": ["customer"],
        },
        NotificationEventType.SIGNUP_WELCOME: {
            "template": "signup_welcome.html",
            "subject": {"cs": "Vítejte v AuditReady", "en": "Thanks for signing up to AuditReady"},
            "recipients": ["customer"],
        },
        NotificationEventType.EMAIL_VERIFICATION_REQUESTED: {
            "template": "email_verification_requested.html",
            "subject": {"cs": "Ověření e-mailu", "en": "Verify your email"},
            "recipients": ["customer"],
        },
        NotificationEventType.MFA_SUPPORT_REQUEST: {
            "template": "mfa_support_request.html",
            "subject": {"cs": "Požadavek na MFA podporu", "en": "MFA support request"},
            "recipients": ["admin"],
        },
    }

    def __init__(self, db: Session):
        self.db = db
        self.renderer = get_template_renderer()
        self.settings = get_settings()

    def _audit_email_notification(
        self,
        *,
        action: str,
        event: NotificationEvent,
        correlation_id: str,
        recipients: list[str],
        success: bool,
        changes_summary: str,
        error_message: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Write email-notification lifecycle events into admin-visible audit logs."""
        try:
            target_id = event.report_id or event.assessment_id or event.user_id
            create_audit_log(
                db=self.db,
                action=action,
                target_entity="notification_email",
                actor_user_id=event.actor_id,
                target_id=target_id,
                target_user_id=event.user_id,
                changes_summary=changes_summary,
                success=success,
                error_message=error_message,
                metadata={
                    "correlation_id": correlation_id,
                    "notification_event_type": event.event_type.value,
                    "recipients": recipients,
                    "assessment_id": str(event.assessment_id) if event.assessment_id else None,
                    "report_id": str(event.report_id) if event.report_id else None,
                    "lang_code": event.lang_code,
                    **(metadata or {}),
                },
            )
        except Exception as audit_error:
            logger.error(
                "Failed to write notification email audit log: %s",
                audit_error,
                exc_info=True,
            )

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
            correlation_id = f"{event.event_type}_{datetime.now().timestamp()}"

            # Resolve recipients
            recipients = self._resolve_recipients(event, config["recipients"])
            if not recipients:
                logger.warning(
                    f"No recipients resolved for event {event.event_type} (user_id={event.user_id})"
                )
                self._audit_email_notification(
                    action="email_delivery_skipped",
                    event=event,
                    correlation_id=correlation_id,
                    recipients=[],
                    success=False,
                    changes_summary=(
                        f"Skipped notification email for {event.event_type}: no recipients resolved"
                    ),
                    error_message="No recipients resolved",
                    metadata={"delivery_status": "skipped", "reason": "no_recipients"},
                )
                return False

            language_batches = self._group_recipients_by_language(recipients, event)

            for lang_code, lang_recipients in language_batches.items():
                if not lang_recipients:
                    continue

                event_for_lang = NotificationEvent(
                    event_type=event.event_type,
                    user_id=event.user_id,
                    assessment_id=event.assessment_id,
                    report_id=event.report_id,
                    actor_id=event.actor_id,
                    lang_code=lang_code,
                    context=event.context,
                )

                # Build template context and render content per language batch.
                context = self._build_context(event_for_lang, config)
                html_content = self.renderer.render_html(config["template"], context)
                text_content = self.renderer.render_text(config["template"], context)
                subject = self._resolve_subject(config["subject"], context.get("lang", DEFAULT_LANGUAGE_CODE))

                audit_context = {
                    "target_entity": "notification_email",
                    "actor_user_id": str(event.actor_id) if event.actor_id else None,
                    "target_user_id": str(event.user_id) if event.user_id else None,
                    "target_id": str(event.report_id or event.assessment_id or event.user_id)
                    if (event.report_id or event.assessment_id or event.user_id)
                    else None,
                    "notification_event_type": event.event_type.value,
                    "assessment_id": str(event.assessment_id) if event.assessment_id else None,
                    "report_id": str(event.report_id) if event.report_id else None,
                    "lang_code": lang_code,
                    "dispatch_mode": "celery_queue",
                }

                try:
                    send_email_task.delay(
                        to_addresses=lang_recipients,
                        subject=subject,
                        html_content=html_content,
                        text_content=text_content,
                        correlation_id=correlation_id,
                        audit_context=audit_context,
                    )
                    self._audit_email_notification(
                        action="email_notification_queued",
                        event=event,
                        correlation_id=correlation_id,
                        recipients=lang_recipients,
                        success=True,
                        changes_summary=f"Queued notification email for {event.event_type}",
                        metadata={"delivery_status": "queued", "transport": "celery", "lang_code": lang_code},
                    )
                except Exception as queue_error:
                    logger.error(
                        f"[{correlation_id}] Failed to enqueue notification {event.event_type}; sending immediately: {queue_error}"
                    )
                    self._audit_email_notification(
                        action="email_queue_failed",
                        event=event,
                        correlation_id=correlation_id,
                        recipients=lang_recipients,
                        success=False,
                        changes_summary=(
                            f"Failed to enqueue notification email for {event.event_type}; using fallback send"
                        ),
                        error_message=str(queue_error),
                        metadata={"delivery_status": "queue_failed", "transport": "celery", "lang_code": lang_code},
                    )
                    fallback_audit_context = {
                        **audit_context,
                        "dispatch_mode": "direct_fallback",
                        "queue_error": str(queue_error),
                    }
                    fallback_result = send_email_now(
                        to_addresses=lang_recipients,
                        subject=subject,
                        html_content=html_content,
                        text_content=text_content,
                        correlation_id=correlation_id,
                        audit_context=fallback_audit_context,
                    )
                    if fallback_result.get("status") != "sent":
                        logger.error(
                            f"[{correlation_id}] Fallback email send failed for {event.event_type}: {fallback_result}"
                        )
                        return False

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
                    if (
                        user
                        and user.email
                        and user.role == UserRole.customer
                        and self._is_user_event_enabled(user, event.event_type)
                    ):
                        recipients.add(user.email)

            elif recipient_type == "actor":
                if event.actor_id:
                    actor = self.db.get(User, event.actor_id)
                    if actor and actor.email and self._is_user_event_enabled(actor, event.event_type):
                        recipients.add(actor.email)

            elif recipient_type == "admin":
                admin_users = self.db.scalars(
                    select(User).where(
                        User.role.in_([UserRole.admin, UserRole.auditor])
                    )
                ).all()
                for admin_user in admin_users:
                    if admin_user.email and self._is_user_event_enabled(admin_user, event.event_type):
                        recipients.add(admin_user.email)

            elif recipient_type == "company_billing":
                # Resolve company billing email
                company_id = self._get_company_id(event)
                if company_id:
                    company = self.db.get(Company, company_id)
                    if company and company.email:
                        recipients.add(company.email)

        return list(recipients)

    def _is_user_event_enabled(self, user: User, event_type: NotificationEventType) -> bool:
        if event_type in {
            NotificationEventType.EMAIL_VERIFICATION_REQUESTED,
            NotificationEventType.MFA_SUPPORT_REQUEST,
        }:
            return True

        if not bool(getattr(user, "email_notifications_enabled", True)):
            return False

        report_events = {
            NotificationEventType.ASSESSMENT_REVIEW_COMPLETED,
            NotificationEventType.REPORT_CHANGES_REQUESTED,
            NotificationEventType.REPORT_APPROVED,
            NotificationEventType.REPORT_PUBLISHED,
        }
        if event_type in report_events:
            return bool(getattr(user, "email_pref_reports_alert", True))

        if event_type == NotificationEventType.PAYMENT_SUCCESS:
            return bool(getattr(user, "email_pref_payment_success_alert", True))

        if event_type == NotificationEventType.ASSESSMENT_SUBMITTED:
            return bool(getattr(user, "email_pref_assessment_submitted", True))

        if event_type in {NotificationEventType.ASSESSMENT_STARTED, NotificationEventType.ASSESSMENT_EXPIRED}:
            return bool(getattr(user, "email_pref_assessment_started", True))

        return True

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

    def _resolve_subject(self, subject_map: dict[str, str], lang_code: str) -> str:
        lang = (lang_code or DEFAULT_LANGUAGE_CODE).lower()
        if lang == "cz":
            lang = "cs"
        return subject_map.get(lang) or subject_map.get(DEFAULT_LANGUAGE_CODE) or next(iter(subject_map.values()))

    def _normalize_lang(self, lang_code: str | None) -> str:
        lang = (lang_code or DEFAULT_LANGUAGE_CODE).lower().strip()
        if lang == "cz":
            return "cs"
        if lang not in {"en", "cs"}:
            return DEFAULT_LANGUAGE_CODE
        return lang

    def _resolve_recipient_language(self, email: str, event: NotificationEvent) -> str:
        user = self.db.scalar(select(User).where(User.email == email.lower()))
        if user and getattr(user, "preferred_language", None):
            return self._normalize_lang(user.preferred_language)
        return self._normalize_lang(event.lang_code)

    def _group_recipients_by_language(self, recipients: list[str], event: NotificationEvent) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = {}
        for recipient in recipients:
            lang = self._resolve_recipient_language(recipient, event)
            grouped.setdefault(lang, []).append(recipient)
        return grouped

    def _resolve_frontend_base_url(self, context: dict) -> str:
        base_url = (context.get("production_frontend_url") or "").strip()
        if not base_url:
            base_url = (context.get("production_base_url") or "").strip()
        if not base_url:
            try:
                from app.services.settings_manager import get_runtime_str
                base_url = get_runtime_str(self.db, "production_frontend_url", self.settings.production_frontend_url)
                if not base_url:
                    base_url = get_runtime_str(self.db, "production_base_url", self.settings.production_base_url)
            except Exception:
                base_url = self.settings.production_frontend_url or self.settings.production_base_url

        base_url = (base_url or "").strip()
        if not base_url:
            return ""
        if not base_url.startswith(("http://", "https://")):
            base_url = f"http://{base_url.lstrip('/')}"

        parsed = urlsplit(base_url)
        path = parsed.path.rstrip("/")
        # Guard against common API-base settings; password-reset links must target frontend pages.
        if path in {"/api", "/api/v1", "/api/api/v1"} or path.startswith("/api/"):
            path = ""

        normalized = urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))
        return normalized.rstrip("/")

    def _build_context(self, event: NotificationEvent, config: dict) -> dict:
        """Build template context from event data."""
        context = event.context or {}
        context.setdefault("lang", event.lang_code or DEFAULT_LANGUAGE_CODE)

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

                days = get_runtime_int(self.db, "assessment_completion_days", self.settings.assessment_completion_days)
                context.setdefault("access_window_days", days)

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
                context.setdefault("actor_name", actor.email.split("@")[0])

        base_url = self._resolve_frontend_base_url(context)
        if base_url:
            context.setdefault("production_base_url", base_url)
            context.setdefault("production_frontend_url", base_url)

        if event.event_type == NotificationEventType.PASSWORD_RESET_ISSUED and context.get("reset_token"):
            if base_url:
                context.setdefault("production_base_url", base_url)
                context.setdefault("reset_password_url", f"{base_url}/reset-password?token={context['reset_token']}")

        if event.event_type == NotificationEventType.EMAIL_VERIFICATION_REQUESTED and context.get("verification_token"):
            if base_url:
                context.setdefault("production_base_url", base_url)
                context.setdefault("verify_email_url", f"{base_url}/verify-email?token={context['verification_token']}")

        return context


def notify_event(db: Session, event: NotificationEvent) -> bool:
    """Convenience function to notify of an event."""
    service = NotificationService(db)
    return service.notify(event)
