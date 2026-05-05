"""Add company_id to assessments and reports for tenant scoping

Revision ID: 20260505_0002_add_company_fk_to_assessments_reports
Revises: 20260505_0001_multi_company_support
Create Date: 2026-05-05 01:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260505_0002_add_company_fk_to_assessments_reports"
down_revision = "20260505_0001_multi_company_support"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add nullable company_id to assessments
    op.add_column(
        "assessments",
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_index("ix_assessments_company_id", "assessments", ["company_id"], unique=False)
    op.create_foreign_key(
        "fk_assessments_company_id_companies",
        "assessments",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Add nullable company_id to reports
    op.add_column(
        "reports",
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_index("ix_reports_company_id", "reports", ["company_id"], unique=False)
    op.create_foreign_key(
        "fk_reports_company_id_companies",
        "reports",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # Drop FK and column from reports
    op.drop_constraint("fk_reports_company_id_companies", "reports", type_="foreignkey")
    op.drop_index("ix_reports_company_id", table_name="reports")
    op.drop_column("reports", "company_id")

    # Drop FK and column from assessments
    op.drop_constraint("fk_assessments_company_id_companies", "assessments", type_="foreignkey")
    op.drop_index("ix_assessments_company_id", table_name="assessments")
    op.drop_column("assessments", "company_id")
