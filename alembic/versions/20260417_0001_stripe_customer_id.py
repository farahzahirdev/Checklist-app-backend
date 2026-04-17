"""
Add stripe_customer_id to users table

Revision ID: 20260417_0001_stripe_customer_id
Revises: 20260416_0001_rbac_initial
Create Date: 2026-04-17 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260417_0001_stripe_customer_id'
down_revision = '20260416_0001_rbac_initial'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('users', sa.Column('stripe_customer_id', sa.String(64), nullable=True, unique=True))

def downgrade() -> None:
    op.drop_column('users', 'stripe_customer_id')
