"""Add stripe_product_id to checklists table

Revision ID: 20260423_0001
Revises: 20260422_0002
Create Date: 2026-04-23 17:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260423_0001'
down_revision: Union[str, None] = '20260422_0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add stripe_product_id column to checklists table
    op.add_column('checklists', sa.Column('stripe_product_id', sa.String(length=255), nullable=True))
    # Create index for faster lookups
    op.create_index(op.f('ix_checklists_stripe_product_id'), 'checklists', ['stripe_product_id'], unique=False)


def downgrade() -> None:
    # Remove index and column
    op.drop_index(op.f('ix_checklists_stripe_product_id'), table_name='checklists')
    op.drop_column('checklists', 'stripe_product_id')
