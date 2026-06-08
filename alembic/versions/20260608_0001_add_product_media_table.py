"""add product media table

Revision ID: 20260608_0001
Revises: 20260605_0002
Create Date: 2026-06-08 15:48:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260608_0001'
down_revision: Union[str, None] = '20260605_0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create product_media table
    op.create_table(
        'product_media',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('media_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('display_order', sa.Integer(), server_default='0', nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['media_id'], ['media.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_product_media_product_id'), 'product_media', ['product_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_product_media_product_id'), table_name='product_media')
    op.drop_table('product_media')
