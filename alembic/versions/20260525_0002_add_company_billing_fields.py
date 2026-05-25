"""add company billing fields

Revision ID: 20260525_0002
Revises: 20260525_0001
Create Date: 2026-05-25 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260525_0002"
down_revision: Union[str, None] = "20260525_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("billing_contact_name", sa.String(length=255), nullable=True))
    op.add_column("companies", sa.Column("billing_email", sa.String(length=320), nullable=True))
    op.add_column("companies", sa.Column("billing_phone", sa.String(length=50), nullable=True))
    op.add_column("companies", sa.Column("billing_address_line1", sa.String(length=255), nullable=True))
    op.add_column("companies", sa.Column("billing_address_line2", sa.String(length=255), nullable=True))
    op.add_column("companies", sa.Column("billing_city", sa.String(length=100), nullable=True))
    op.add_column("companies", sa.Column("billing_state", sa.String(length=100), nullable=True))
    op.add_column("companies", sa.Column("billing_postal_code", sa.String(length=50), nullable=True))
    op.add_column("companies", sa.Column("billing_country", sa.String(length=100), nullable=True))
    op.add_column("companies", sa.Column("billing_tax_id", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("companies", "billing_tax_id")
    op.drop_column("companies", "billing_country")
    op.drop_column("companies", "billing_postal_code")
    op.drop_column("companies", "billing_state")
    op.drop_column("companies", "billing_city")
    op.drop_column("companies", "billing_address_line2")
    op.drop_column("companies", "billing_address_line1")
    op.drop_column("companies", "billing_phone")
    op.drop_column("companies", "billing_email")
    op.drop_column("companies", "billing_contact_name")
