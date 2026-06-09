"""add product benefits

Revision ID: 20260609_0001
Revises: 20260608_0001
Create Date: 2026-06-09 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260609_0001'
down_revision: Union[str, None] = '20260608_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add benefits column to products table
    op.add_column('products', sa.Column('benefits', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove benefits column from products table
    op.drop_column('products', 'benefits')
