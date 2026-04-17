"""
Add checklist_id to access_windows for post-payment checklist selection

Revision ID: 20260417_0002_access_window
Revises: 20260417_0001_stripe_cust_id
Create Date: 2026-04-17 01:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260417_0002_access_window'
down_revision = '20260417_0001_stripe_cust_id'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('access_windows', sa.Column('checklist_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_access_windows_checklist_id_checklists',
        'access_windows', 'checklists',
        ['checklist_id'], ['id'],
        ondelete='SET NULL'
    )

def downgrade() -> None:
    op.drop_constraint('fk_access_windows_checklist_id_checklists', 'access_windows', type_='foreignkey')
    op.drop_column('access_windows', 'checklist_id')
