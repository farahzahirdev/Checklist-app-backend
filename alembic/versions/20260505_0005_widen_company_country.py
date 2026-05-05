"""Widen companies.country to store full country names

Revision ID: 20260505_0005_widen_company_country
Revises: 20260505_0004_add_company_description
Create Date: 2026-05-05 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260505_0005_widen_company_country"
down_revision = "20260505_0004_add_company_description"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "companies",
        "country",
        existing_type=sa.String(length=2),
        type_=sa.String(length=100),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "companies",
        "country",
        existing_type=sa.String(length=100),
        type_=sa.String(length=2),
        existing_nullable=True,
    )