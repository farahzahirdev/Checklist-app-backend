"""Email sending tasks for Celery."""
from __future__ import annotations

import logging
from celery import shared_task
from app.core.config import get_settings
from app.services.email_provider import EmailMessage, get_email_provider
from app.db.session import SessionLocal
from app.services.settings_manager import get_runtime_bool, get_runtime_int, get_runtime_str

logger = logging.getLogger(__name__)


@shared_task(
    name="email.send_email",
    queue="celery",
    max_retries=3,
    default_retry_delay=60,
    bind=True,
)
def send_email_task(
    self,
    to_addresses: list[str],
    subject: str,
    html_content: str,
    text_content: str | None = None,
    from_address: str | None = None,
    from_name: str | None = None,
    reply_to: str | None = None,
    correlation_id: str | None = None,
) -> dict:
    """
    Send an email asynchronously.
    
    Args:
        to_addresses: List of recipient email addresses
        subject: Email subject
        html_content: HTML email body
        text_content: Plain text email body (optional)
        from_address: Sender email address (uses config default if None)
        from_name: Sender display name (uses config default if None)
        reply_to: Reply-to address (optional)
        correlation_id: For tracking/logging purposes
        
    Returns:
        dict with status and details
    """
    settings = get_settings()
    db = SessionLocal()
    try:
        # Runtime overrides from DB (with env fallback).
        settings.email_enabled = get_runtime_bool(db, "email_enabled", settings.email_enabled)
        settings.smtp_host = get_runtime_str(db, "smtp_host", settings.smtp_host)
        settings.smtp_port = get_runtime_int(db, "smtp_port", settings.smtp_port)
        settings.smtp_use_tls = get_runtime_bool(db, "smtp_use_tls", settings.smtp_use_tls)
        settings.email_from_address = get_runtime_str(db, "email_from_address", settings.email_from_address)
        settings.email_from_name = get_runtime_str(db, "email_from_name", settings.email_from_name)
        settings.email_reply_to = get_runtime_str(db, "email_reply_to", settings.email_reply_to or "")
        settings.email_retry_delay_seconds = get_runtime_int(
            db,
            "email_retry_delay_seconds",
            settings.email_retry_delay_seconds,
        )
    finally:
        db.close()

    provider = get_email_provider(settings)

    if provider is None:
        logger.warning(
            f"[{correlation_id}] Email provider not configured; skipping send to {to_addresses}"
        )
        return {
            "status": "skipped",
            "reason": "provider_disabled",
            "to": to_addresses,
            "correlation_id": correlation_id,
        }

    try:
        message = EmailMessage(
            to=to_addresses,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            from_address=from_address or settings.email_from_address,
            from_name=from_name or settings.email_from_name,
            reply_to=reply_to or settings.email_reply_to or None,
        )

        success = provider.send(message)

        if success:
            logger.info(f"[{correlation_id}] Email sent successfully to {to_addresses}")
            return {
                "status": "sent",
                "to": to_addresses,
                "subject": subject,
                "correlation_id": correlation_id,
            }
        else:
            logger.warning(f"[{correlation_id}] Email send failed; retrying")
            raise Exception("Email provider returned False")

    except Exception as exc:
        logger.error(f"[{correlation_id}] Error sending email: {exc}")

        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            retry_delay = settings.email_retry_delay_seconds * (2 ** self.request.retries)
            logger.info(f"[{correlation_id}] Retrying email send in {retry_delay}s")
            raise self.retry(exc=exc, countdown=retry_delay)

        logger.error(f"[{correlation_id}] Email send failed after {self.max_retries} retries")
        return {
            "status": "failed",
            "to": to_addresses,
            "error": str(exc),
            "retries": self.request.retries,
            "correlation_id": correlation_id,
        }
