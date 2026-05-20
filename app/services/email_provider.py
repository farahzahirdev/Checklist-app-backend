"""Email provider abstraction and implementations."""
from __future__ import annotations

import logging
import smtplib
from abc import ABC, abstractmethod
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    """Structured email message."""
    to: list[str]
    subject: str
    html_content: str
    text_content: str | None = None
    from_address: str = ""
    from_name: str = ""
    reply_to: str | None = None


class EmailProvider(ABC):
    """Abstract email provider interface."""

    @abstractmethod
    def send(self, message: EmailMessage) -> bool:
        """Send email. Returns True if successful, False otherwise."""
        pass


class SMTPEmailProvider(EmailProvider):
    """SMTP email provider (supports Microsoft 365, Gmail, custom SMTP)."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_username: str,
        smtp_password: str,
        smtp_use_tls: bool = True,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.smtp_use_tls = smtp_use_tls

    def send(self, message: EmailMessage) -> bool:
        """Send email via SMTP."""
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = message.subject
            msg["From"] = f"{message.from_name} <{message.from_address}>"
            msg["To"] = ", ".join(message.to)

            if message.reply_to:
                msg["Reply-To"] = message.reply_to

            # Attach plain text version
            if message.text_content:
                msg.attach(MIMEText(message.text_content, "plain", "utf-8"))

            # Attach HTML version
            msg.attach(MIMEText(message.html_content, "html", "utf-8"))

            # Connect and send
            if self.smtp_use_tls:
                with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                    server.starttls()
                    server.login(self.smtp_username, self.smtp_password)
                    server.sendmail(message.from_address, message.to, msg.as_string())
            else:
                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=10) as server:
                    server.login(self.smtp_username, self.smtp_password)
                    server.sendmail(message.from_address, message.to, msg.as_string())

            logger.info(f"Email sent to {message.to} with subject: {message.subject}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error while sending email: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}")
            return False


def get_email_provider(settings) -> EmailProvider | None:
    """Factory function to get configured email provider."""
    if not settings.email_enabled:
        logger.debug("Email notifications disabled")
        return None

    if settings.email_provider == "smtp":
        if not all([settings.smtp_host, settings.smtp_username, settings.smtp_password]):
            logger.warning("SMTP provider configured but missing credentials")
            return None
        return SMTPEmailProvider(
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            smtp_username=settings.smtp_username,
            smtp_password=settings.smtp_password,
            smtp_use_tls=settings.smtp_use_tls,
        )

    logger.warning(f"Unknown email provider: {settings.email_provider}")
    return None
