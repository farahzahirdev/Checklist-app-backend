"""Localize seeded system setting descriptions.

Revision ID: 20260520_0004_localize_system_settings_descriptions
Revises: 20260520_0003_merge_product_and_settings_heads
Create Date: 2026-05-20 00:04:00
"""

from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa


revision = "20260520_0004_localize_system_settings_descriptions"
down_revision = "20260520_0003_merge_product_and_settings_heads"
branch_labels = None
depends_on = None


LOCALIZED_DESCRIPTIONS = {
    "email_enabled": {"cs": "Povolit odchozí e-mailová upozornění", "en": "Enable outbound notification emails"},
    "smtp_host": {"cs": "SMTP hostitel", "en": "SMTP host"},
    "smtp_port": {"cs": "SMTP port", "en": "SMTP port"},
    "smtp_use_tls": {"cs": "Použít TLS pro SMTP připojení", "en": "Use TLS for SMTP connection"},
    "email_from_address": {"cs": "E-mailová adresa odesílatele", "en": "Email sender address"},
    "email_from_name": {"cs": "Zobrazované jméno odesílatele", "en": "Email sender display name"},
    "email_reply_to": {"cs": "Adresa pro odpověď na oznámení", "en": "Reply-to address for notifications"},
    "email_max_retries": {"cs": "Maximální počet pokusů o opakování neúspěšného e-mailu", "en": "Maximum retry attempts for failed emails"},
    "email_retry_delay_seconds": {"cs": "Základní prodleva opakování v sekundách", "en": "Base retry delay in seconds"},
    "assessment_completion_days": {"cs": "Počet dní dostupných pro dokončení hodnocení", "en": "Days available to complete an assessment"},
    "evidence_retention_hours": {"cs": "Počet hodin uchování důkazů po zveřejnění zprávy", "en": "Hours to retain evidence after report publish"},
}

OLD_DESCRIPTIONS = {
    "email_enabled": "Enable outbound notification emails",
    "smtp_host": "SMTP host",
    "smtp_port": "SMTP port",
    "smtp_use_tls": "Use TLS for SMTP connection",
    "email_from_address": "Email sender address",
    "email_from_name": "Email sender display name",
    "email_reply_to": "Reply-to address for notifications",
    "email_max_retries": "Maximum retry attempts for failed emails",
    "email_retry_delay_seconds": "Base retry delay in seconds",
    "assessment_completion_days": "Days available to complete an assessment",
    "evidence_retention_hours": "Hours to retain evidence after report publish",
}


def upgrade() -> None:
    settings = sa.table(
        "system_settings",
        sa.column("key", sa.String()),
        sa.column("description", sa.Text()),
    )

    for key, description in LOCALIZED_DESCRIPTIONS.items():
        op.execute(
            settings.update()
            .where(settings.c.key == key)
            .where(sa.or_(settings.c.description.is_(None), settings.c.description == OLD_DESCRIPTIONS[key]))
            .values(description=json.dumps(description, ensure_ascii=False))
        )


def downgrade() -> None:
    settings = sa.table(
        "system_settings",
        sa.column("key", sa.String()),
        sa.column("description", sa.Text()),
    )

    for key, description in OLD_DESCRIPTIONS.items():
        op.execute(
            settings.update()
            .where(settings.c.key == key)
            .where(settings.c.description == json.dumps(LOCALIZED_DESCRIPTIONS[key], ensure_ascii=False))
            .values(description=description)
        )
