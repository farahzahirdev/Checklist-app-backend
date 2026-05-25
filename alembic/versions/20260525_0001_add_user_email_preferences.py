"""add user email preferences

Revision ID: 20260525_0001
Revises: 20260522_0003
Create Date: 2026-05-25 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260525_0001"
down_revision: Union[str, None] = "20260522_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_notifications_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("users", sa.Column("email_pref_reports_alert", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("users", sa.Column("email_pref_payment_success_alert", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("users", sa.Column("email_pref_assessment_submitted", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("users", sa.Column("email_pref_assessment_started", sa.Boolean(), nullable=False, server_default=sa.text("true")))

    op.alter_column("users", "email_notifications_enabled", server_default=None)
    op.alter_column("users", "email_pref_reports_alert", server_default=None)
    op.alter_column("users", "email_pref_payment_success_alert", server_default=None)
    op.alter_column("users", "email_pref_assessment_submitted", server_default=None)
    op.alter_column("users", "email_pref_assessment_started", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "email_pref_assessment_started")
    op.drop_column("users", "email_pref_assessment_submitted")
    op.drop_column("users", "email_pref_payment_success_alert")
    op.drop_column("users", "email_pref_reports_alert")
    op.drop_column("users", "email_notifications_enabled")
