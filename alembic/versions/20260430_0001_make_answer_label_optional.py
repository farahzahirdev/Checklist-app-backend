"""
Make answer option label (title) optional for checklist questions

Revision ID: 20260430_0001
Revises: 20260422_0002
Create Date: 2026-04-30
"""

from alembic import op
import sqlalchemy as sa

revision = '20260430_0001'
down_revision = '20260422_0002'
branch_labels = None
depends_on = None

def upgrade():
    op.alter_column('checklist_question_answer_options', 'label',
               existing_type=sa.String(length=255),
               nullable=True)

def downgrade():
    op.alter_column('checklist_question_answer_options', 'label',
               existing_type=sa.String(length=255),
               nullable=False)
