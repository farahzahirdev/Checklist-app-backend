"""add email audit actions

Revision ID: 20260522_0001
Revises: 20260520_0004_localize_system_settings_descriptions
Create Date: 2026-05-22 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260522_0001"
down_revision: Union[str, None] = "20260520_0004_localize_system_settings_descriptions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_EMAIL_AUDIT_ACTIONS = [
    "email_notification_queued",
    "email_queue_failed",
    "email_delivery_sent",
    "email_delivery_failed",
    "email_delivery_skipped",
    "email_retry_scheduled",
    "email_retries_exhausted",
]


def upgrade() -> None:
    for value in NEW_EMAIL_AUDIT_ACTIONS:
        op.execute(f"ALTER TYPE audit_action ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    # PostgreSQL enum value removal is non-trivial and unsafe without type recreation.
    # Keep downgrade as no-op to avoid destructive enum rewrites in production.
    pass
