"""Add system settings table for dynamic runtime configuration.

Revision ID: 20260520_0001_system_settings_dynamic_config
Revises: 20260518_0001_add_report_pdf_password_encrypted
Create Date: 2026-05-20 00:01:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid


# revision identifiers, used by Alembic.
revision = "20260520_0001_system_settings_dynamic_config"
down_revision = "20260518_0001_add_report_pdf_password_encrypted"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("value_type", sa.String(length=20), nullable=False, server_default="string"),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_secret", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("key", name="uq_system_settings_key"),
    )
    op.create_index("ix_system_settings_key", "system_settings", ["key"], unique=True)
    op.create_index("ix_system_settings_category", "system_settings", ["category"], unique=False)

    system_settings_table = sa.table(
        "system_settings",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("key", sa.String(length=120)),
        sa.column("value", sa.Text()),
        sa.column("value_type", sa.String(length=20)),
        sa.column("category", sa.String(length=50)),
        sa.column("description", sa.Text()),
        sa.column("is_secret", sa.Boolean()),
        sa.column("is_locked", sa.Boolean()),
    )

    op.bulk_insert(
        system_settings_table,
        [
            {
                "id": uuid.uuid4(),
                "key": "email_enabled",
                "value": "false",
                "value_type": "bool",
                "category": "email",
                "description": "Enable outbound notification emails",
                "is_secret": False,
                "is_locked": False,
            },
            {
                "id": uuid.uuid4(),
                "key": "smtp_host",
                "value": "smtp.office365.com",
                "value_type": "string",
                "category": "email",
                "description": "SMTP host",
                "is_secret": False,
                "is_locked": False,
            },
            {
                "id": uuid.uuid4(),
                "key": "smtp_port",
                "value": "587",
                "value_type": "int",
                "category": "email",
                "description": "SMTP port",
                "is_secret": False,
                "is_locked": False,
            },
            {
                "id": uuid.uuid4(),
                "key": "smtp_use_tls",
                "value": "true",
                "value_type": "bool",
                "category": "email",
                "description": "Use TLS for SMTP connection",
                "is_secret": False,
                "is_locked": False,
            },
            {
                "id": uuid.uuid4(),
                "key": "email_from_address",
                "value": "noreply@auditready.cz",
                "value_type": "string",
                "category": "email",
                "description": "Email sender address",
                "is_secret": False,
                "is_locked": False,
            },
            {
                "id": uuid.uuid4(),
                "key": "email_from_name",
                "value": "AuditReady",
                "value_type": "string",
                "category": "email",
                "description": "Email sender display name",
                "is_secret": False,
                "is_locked": False,
            },
            {
                "id": uuid.uuid4(),
                "key": "email_reply_to",
                "value": "support@auditready.cz",
                "value_type": "string",
                "category": "email",
                "description": "Reply-to address for notifications",
                "is_secret": False,
                "is_locked": False,
            },
            {
                "id": uuid.uuid4(),
                "key": "email_max_retries",
                "value": "3",
                "value_type": "int",
                "category": "email",
                "description": "Maximum retry attempts for failed emails",
                "is_secret": False,
                "is_locked": False,
            },
            {
                "id": uuid.uuid4(),
                "key": "email_retry_delay_seconds",
                "value": "60",
                "value_type": "int",
                "category": "email",
                "description": "Base retry delay in seconds",
                "is_secret": False,
                "is_locked": False,
            },
            {
                "id": uuid.uuid4(),
                "key": "assessment_completion_days",
                "value": "7",
                "value_type": "int",
                "category": "lifecycle",
                "description": "Days available to complete an assessment",
                "is_secret": False,
                "is_locked": False,
            },
            {
                "id": uuid.uuid4(),
                "key": "evidence_retention_hours",
                "value": "48",
                "value_type": "int",
                "category": "lifecycle",
                "description": "Hours to retain evidence after report publish",
                "is_secret": False,
                "is_locked": False,
            },
        ],
    )

    op.execute("ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'settings_change'")


def downgrade() -> None:
    op.drop_index("ix_system_settings_category", table_name="system_settings")
    op.drop_index("ix_system_settings_key", table_name="system_settings")
    op.drop_table("system_settings")
