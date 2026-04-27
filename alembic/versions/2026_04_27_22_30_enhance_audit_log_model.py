"""Enhance audit log model with additional fields

Revision ID: 2026_04_27_22_30
Revises: 2026_04_27_22_15
Create Date: 2026-04-27 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2026_04_27_22_30'
down_revision: Union[str, None] = '2026_04_27_22_15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to audit_logs table
    op.add_column('audit_logs', sa.Column('target_user_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('audit_logs', sa.Column('session_id', sa.String(length=100), nullable=True))
    op.add_column('audit_logs', sa.Column('changes_summary', sa.Text(), nullable=True))
    op.add_column('audit_logs', sa.Column('success', sa.Boolean(), nullable=False, server_default=sa.text('true')))
    op.add_column('audit_logs', sa.Column('error_message', sa.Text(), nullable=True))
    op.add_column('audit_logs', sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    
    # Add indexes for the new columns
    op.create_index('ix_audit_logs_target_user_id', 'audit_logs', ['target_user_id'], unique=False)
    op.create_index('ix_audit_logs_session_id', 'audit_logs', ['session_id'], unique=False)
    op.create_index('ix_audit_logs_success', 'audit_logs', ['success'], unique=False)
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'], unique=False)
    
    # Update existing records to have success=True by default
    op.execute("UPDATE audit_logs SET success = true WHERE success IS NULL")


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_audit_logs_created_at', table_name='audit_logs')
    op.drop_index('ix_audit_logs_success', table_name='audit_logs')
    op.drop_index('ix_audit_logs_session_id', table_name='audit_logs')
    op.drop_index('ix_audit_logs_target_user_id', table_name='audit_logs')
    
    # Drop columns
    op.drop_column('audit_logs', 'metadata')
    op.drop_column('audit_logs', 'error_message')
    op.drop_column('audit_logs', 'success')
    op.drop_column('audit_logs', 'changes_summary')
    op.drop_column('audit_logs', 'session_id')
    op.drop_column('audit_logs', 'target_user_id')
