"""Add company_id to payments and access_windows

Revision ID: 20260505_0003_add_company_to_payments_access
Revises: 20260505_0002_add_company_fk_to_assessments_reports
Create Date: 2026-05-05 01:30:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260505_0003_add_company_to_payments_access"
down_revision = "20260505_0002_add_company_fk_to_assessments_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add company_id to payments
    op.add_column(
        "payments",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_payments_company_id", "payments", ["company_id"], unique=False)
    op.create_foreign_key(
        "fk_payments_company_id_companies",
        "payments",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Add company_id to access_windows
    op.add_column(
        "access_windows",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_access_windows_company_id", "access_windows", ["company_id"], unique=False)
    op.create_foreign_key(
        "fk_access_windows_company_id_companies",
        "access_windows",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_access_windows_company_id_companies", "access_windows", type_="foreignkey")
    op.drop_index("ix_access_windows_company_id", table_name="access_windows")
    op.drop_column("access_windows", "company_id")

    op.drop_constraint("fk_payments_company_id_companies", "payments", type_="foreignkey")
    op.drop_index("ix_payments_company_id", table_name="payments")
    op.drop_column("payments", "company_id")
