"""Merge all heads

Revision ID: 20260427_0003
Revises: 20260427_0002, 20260427_0002_merge_auditor_permissions
Create Date: 2026-04-27 17:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260427_0003'
down_revision = ('20260427_0002', '20260427_0002_merge_auditor_permissions')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
