"""Email sending tasks for Celery."""
from __future__ import annotations

import logging
from celery import shared_task
from app.core.config import get_settings
from app.services.email_provider import EmailMessage, MicrosoftGraphEmailProvider, get_email_provider
from app.db.session import SessionLocal
from app.services.settings_manager import get_runtime_bool, get_runtime_int, get_runtime_str

logger = logging.getLogger(__name__)


def _build_graph_fallback_provider(settings) -> MicrosoftGraphEmailProvider | None:
    if not all([
        settings.graph_client_id,
        settings.graph_client_secret,
        settings.graph_tenant_id,
        settings.graph_mailbox,
        settings.graph_refresh_token,
    ]):
        return None
    return MicrosoftGraphEmailProvider(
        client_id=settings.graph_client_id,
        client_secret=settings.graph_client_secret,
        tenant_id=settings.graph_tenant_id,
        mailbox=settings.graph_mailbox,
        refresh_token=settings.graph_refresh_token,
        redirect_uri=settings.graph_redirect_uri,
    )


def send_email_now(
    *,
    to_addresses: list[str],
    subject: str,
    html_content: str,
    text_content: str | None = None,
    from_address: str | None = None,
    from_name: str | None = None,
    reply_to: str | None = None,
    correlation_id: str | None = None,
) -> dict:
    """Send email immediately in-process (fallback path when queueing fails)."""
    settings = get_settings()
    db = SessionLocal()
    try:
        # Runtime overrides from DB (with env fallback).
        settings.email_enabled = get_runtime_bool(db, "email_enabled", settings.email_enabled)
        settings.email_provider = get_runtime_str(db, "email_provider", settings.email_provider)
        settings.smtp_host = get_runtime_str(db, "smtp_host", settings.smtp_host)
        settings.smtp_port = get_runtime_int(db, "smtp_port", settings.smtp_port)
        settings.smtp_username = get_runtime_str(db, "smtp_username", settings.smtp_username)
        settings.smtp_password = get_runtime_str(db, "smtp_password", settings.smtp_password)
        settings.smtp_use_tls = get_runtime_bool(db, "smtp_use_tls", settings.smtp_use_tls)
        settings.email_from_address = get_runtime_str(db, "email_from_address", settings.email_from_address)
        settings.email_from_name = get_runtime_str(db, "email_from_name", settings.email_from_name)
        settings.email_reply_to = get_runtime_str(db, "email_reply_to", settings.email_reply_to or "")
        settings.email_retry_delay_seconds = get_runtime_int(
            db,
            "email_retry_delay_seconds",
            settings.email_retry_delay_seconds,
        )
        # Microsoft Graph OAuth runtime overrides
        settings.graph_client_id = get_runtime_str(db, "graph_client_id", settings.graph_client_id)
        settings.graph_client_secret = get_runtime_str(db, "graph_client_secret", settings.graph_client_secret)
        settings.graph_tenant_id = get_runtime_str(db, "graph_tenant_id", settings.graph_tenant_id)
        settings.graph_mailbox = get_runtime_str(db, "graph_mailbox", settings.graph_mailbox)
        settings.graph_redirect_uri = get_runtime_str(db, "graph_redirect_uri", settings.graph_redirect_uri)
        settings.graph_refresh_token = get_runtime_str(db, "graph_refresh_token", settings.graph_refresh_token)
    finally:
        db.close()

    provider = get_email_provider(settings)

    if provider is None:
        # If SMTP is selected but unavailable/misconfigured, attempt Graph fallback when configured.
        if settings.email_provider == "smtp":
            provider = _build_graph_fallback_provider(settings)
            if provider is not None:
                logger.warning(
                    f"[{correlation_id}] SMTP provider unavailable; attempting Microsoft Graph fallback"
                )

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
    if not success and settings.email_provider == "smtp":
        graph_fallback = _build_graph_fallback_provider(settings)
        if graph_fallback is not None:
            logger.warning(
                f"[{correlation_id}] SMTP send failed; retrying once via Microsoft Graph fallback"
            )
            success = graph_fallback.send(message)

    if success:
        logger.info(f"[{correlation_id}] Email sent successfully to {to_addresses}")
        return {
            "status": "sent",
            "to": to_addresses,
            "subject": subject,
            "correlation_id": correlation_id,
        }

    return {
        "status": "failed",
        "to": to_addresses,
        "error": "Email provider returned False",
        "correlation_id": correlation_id,
    }


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
    try:
        result = send_email_now(
            to_addresses=to_addresses,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            from_address=from_address,
            from_name=from_name,
            reply_to=reply_to,
            correlation_id=correlation_id,
        )
        if result.get("status") != "sent":
            logger.warning(f"[{correlation_id}] Email send failed; retrying")
            raise Exception("Email provider returned False")
        return result

    except Exception as exc:
        logger.error(f"[{correlation_id}] Error sending email: {exc}")

        settings = get_settings()
        db = SessionLocal()
        try:
            settings.email_retry_delay_seconds = get_runtime_int(
                db,
                "email_retry_delay_seconds",
                settings.email_retry_delay_seconds,
            )
        finally:
            db.close()

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
