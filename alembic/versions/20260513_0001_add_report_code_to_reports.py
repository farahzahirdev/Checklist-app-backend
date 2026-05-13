"""Add report_code to reports

Revision ID: 20260513_0001_add_report_code_to_reports
Revises: 8eee78d32ee3
Create Date: 2026-05-13 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260513_0001_add_report_code_to_reports"
down_revision = "8eee78d32ee3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "reports",
        sa.Column("report_code", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_reports_report_code", "reports", ["report_code"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_reports_report_code", table_name="reports")
    op.drop_column("reports", "report_code")
