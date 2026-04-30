"""merge heads

Revision ID: ce71bfc7845f
Revises: 20260428_add_changes_requested, 20260430_0001
Create Date: 2026-04-30 15:46:49.065265
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ce71bfc7845f'
down_revision = ('20260428_add_changes_requested', '20260430_0001')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
