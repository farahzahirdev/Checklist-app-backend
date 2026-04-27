"""Merge auditor permissions with existing heads

Revision ID: 20260427_0002_merge_auditor_permissions
Revises: 970e0b8e97af, 20260427_0001_add_auditor_admin_view_permissions
Create Date: 2026-04-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260427_0002_merge_auditor_permissions'
down_revision = ('970e0b8e97af', '20260427_0001_add_auditor_admin_view_permissions')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
