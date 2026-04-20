"""
Revision ID: 20260420_0001_remove_checklist_type_version_unique
Revises: 20260417_0002_access_window
Create Date: 2026-04-20
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260420_0001_remove_checklist_type_version_unique'
down_revision = '20260417_0002_access_window'
branch_labels = None
depends_on = None

def upgrade():
    # Allow longer alembic version numbers
    op.alter_column('alembic_version', 'version_num', type_=sa.String(64))
    op.drop_constraint('uq_checklists_type_version', 'checklists', type_='unique')

def downgrade():
    op.create_unique_constraint('uq_checklists_type_version', 'checklists', ['checklist_type_id', 'version'])
    # Optionally revert alembic_version.version_num to VARCHAR(32) (not strictly necessary)
    op.alter_column('alembic_version', 'version_num', type_=sa.String(32))
