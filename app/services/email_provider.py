"""Email provider abstraction and implementations."""
from __future__ import annotations

import logging
import smtplib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from json import JSONDecodeError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

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
        self.last_error: str | None = None

    def send(self, message: EmailMessage) -> bool:
        """Send email via SMTP."""
        try:
            self.last_error = None
            msg = MIMEMultipart("alternative")
            msg["Subject"] = message.subject
            msg["From"] = f"{message.from_name} <{message.from_address}>"
            msg["To"] = ", ".join(message.to)

            if message.reply_to:
                msg["Reply-To"] = message.reply_to

            if message.text_content:
                msg.attach(MIMEText(message.text_content, "plain", "utf-8"))

            msg.attach(MIMEText(message.html_content, "html", "utf-8"))

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
            self.last_error = f"SMTP authentication failed: {e}"
            logger.error(f"SMTP authentication failed: {e}")
            return False
        except smtplib.SMTPException as e:
            self.last_error = f"SMTP error: {e}"
            logger.error(f"SMTP error while sending email: {e}")
            return False
        except Exception as e:
            self.last_error = f"Unexpected SMTP error: {e}"
            logger.error(f"Unexpected error sending email: {e}")
            return False


class MicrosoftGraphEmailProvider(EmailProvider):
    """Microsoft Graph API email provider (OAuth)."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        tenant_id: str,
        mailbox: str,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.mailbox = mailbox
        self._access_token: str | None = None
        self._access_token_expiry: int = 0
        self.last_error: str | None = None

    def _token_endpoint(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"

    @staticmethod
    def _safe_response_excerpt(response: requests.Response) -> str:
        """Build a concise and safe HTTP error summary from Graph/AAD responses."""
        try:
            body = response.json()
            if isinstance(body, dict):
                # Common shape: {"error": "...", "error_description": "..."}
                err = body.get("error")
                desc = body.get("error_description")
                if err or desc:
                    return f"status={response.status_code} error={err!r} error_description={desc!r}"

                # Some APIs use nested error payloads.
                nested = body.get("error") if isinstance(body.get("error"), dict) else None
                if nested:
                    code = nested.get("code")
                    msg = nested.get("message")
                    return f"status={response.status_code} code={code!r} message={msg!r}"

                return f"status={response.status_code} body={str(body)[:400]!r}"
            return f"status={response.status_code} body={str(body)[:400]!r}"
        except (ValueError, JSONDecodeError):
            text = (response.text or "").strip().replace("\n", " ")
            return f"status={response.status_code} body={text[:400]!r}"

    def _get_access_token_client_credentials(self) -> str:
        data: dict[str, str] = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
            "scope": "https://graph.microsoft.com/.default",
        }
        resp = requests.post(self._token_endpoint(), data=data, timeout=15)
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            detail = self._safe_response_excerpt(resp)
            raise RuntimeError(f"Graph token endpoint rejected client_credentials request: {detail}") from exc
        token_data = resp.json()
        return token_data["access_token"], int(token_data.get("expires_in", 3600))

    def _get_access_token(self) -> str:
        now = int(time.time())
        if self._access_token and now < self._access_token_expiry - 60:
            return self._access_token

        # Primary mode: app-only token (client credentials).
        try:
            token, expires_in = self._get_access_token_client_credentials()
            self._access_token = token
            self._access_token_expiry = now + int(expires_in)
            return self._access_token
        except Exception as client_cred_exc:
            detail = str(client_cred_exc)
            raise RuntimeError(
                "Graph client_credentials token request failed. "
                "Ensure Azure app has Mail.Send Application permission and admin consent is granted. "
                f"Details: {detail}"
            ) from client_cred_exc

        return self._access_token

    def send(self, message: EmailMessage) -> bool:
        try:
            self.last_error = None
            access_token = self._get_access_token()
            url = f"https://graph.microsoft.com/v1.0/users/{self.mailbox}/sendMail"
            payload: dict = {
                "message": {
                    "subject": message.subject,
                    "body": {
                        "contentType": "HTML",
                        "content": message.html_content,
                    },
                    "toRecipients": [
                        {"emailAddress": {"address": addr}} for addr in message.to
                    ],
                },
                "saveToSentItems": "true",
            }
            if message.from_address:
                payload["message"]["from"] = {"emailAddress": {"address": message.from_address}}
            if message.reply_to:
                payload["message"]["replyTo"] = [{"emailAddress": {"address": message.reply_to}}]
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            if resp.status_code in {401, 403}:
                detail = self._safe_response_excerpt(resp)
                raise RuntimeError(
                    "Graph sendMail unauthorized/forbidden. Verify Mail.Send Application permission "
                    f"and admin consent for the Azure app. Details: {detail}"
                )
            try:
                resp.raise_for_status()
            except requests.HTTPError as exc:
                detail = self._safe_response_excerpt(resp)
                raise RuntimeError(f"Graph sendMail request failed: {detail}") from exc
            logger.info(f"Graph email sent to {message.to} with subject: {message.subject}")
            return True
        except Exception as e:
            self.last_error = f"Graph API error: {e}"
            logger.error(f"Graph API error sending email: {e}")
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

    if settings.email_provider == "graph":
        if not all([
            settings.graph_client_id,
            settings.graph_client_secret,
            settings.graph_tenant_id,
            settings.graph_mailbox,
        ]):
            logger.warning("Graph provider configured but missing credentials")
            return None
        return MicrosoftGraphEmailProvider(
            client_id=settings.graph_client_id,
            client_secret=settings.graph_client_secret,
            tenant_id=settings.graph_tenant_id,
            mailbox=settings.graph_mailbox,
        )

    logger.warning(f"Unknown email provider: {settings.email_provider}")
    return None
