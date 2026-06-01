"""Email template rendering utility."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape
from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Template directory path
TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "emails"


class EmailTemplateRenderer:
    """Render email templates with context and branding."""

    def __init__(self):
        """Initialize Jinja2 environment."""
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(["html", "txt"]),
        )
        self.settings = get_settings()

    def render(
        self,
        template_name: str,
        context: dict | None = None,
        format: str = "html",
        db = None,
    ) -> str:
        """
        Render an email template.

        Args:
            template_name: Name of the template file (e.g., 'assessment_submitted.html')
            context: Dictionary of variables to pass to the template
            format: 'html' or 'txt'
            db: Optional database session to fetch runtime settings

        Returns:
            Rendered template string
        """
        if context is None:
            context = {}

        # Determine production_base_url for template links: prefer frontend URL.
        production_base_url = context.get("production_frontend_url") or context.get("production_base_url")
        if production_base_url is None and db is not None:
            try:
                from app.services.settings_manager import get_runtime_str
                production_base_url = get_runtime_str(db, "production_frontend_url", self.settings.production_frontend_url)
                if not production_base_url:
                    production_base_url = get_runtime_str(db, "production_base_url", self.settings.production_base_url)
            except Exception:
                production_base_url = self.settings.production_frontend_url or self.settings.production_base_url
        if production_base_url is None:
            production_base_url = self.settings.production_frontend_url or self.settings.production_base_url

        # Add global branding context
        context.update(
            {
                "app_name": self.settings.app_name,
                "from_email": self.settings.email_from_address,
                "from_name": self.settings.email_from_name,
                "production_base_url": production_base_url,
                "production_frontend_url": production_base_url,
                "support_email": self.settings.email_reply_to or self.settings.email_from_address,
                "app_year": 2026,  # Update annually or make dynamic
            }
        )

        try:
            template = self.env.get_template(template_name)
            return template.render(**context)
        except TemplateNotFound:
            raise
        except Exception as e:
            logger.error(f"Error rendering template {template_name}: {e}")
            raise

    def render_html(self, template_name: str, context: dict | None = None) -> str:
        """Render HTML template."""
        return self.render(template_name, context, format="html")

    def render_text(self, template_name: str, context: dict | None = None) -> str:
        """Render plain text template."""
        text_template = template_name.replace(".html", ".txt")
        try:
            return self.render(text_template, context, format="txt")
        except TemplateNotFound:
            html_content = self.render_html(template_name, context)
            return re.sub(r"<[^>]+>", " ", html_content).replace("&nbsp;", " ")


def get_template_renderer() -> EmailTemplateRenderer:
    """Factory function to get template renderer instance."""
    return EmailTemplateRenderer()
