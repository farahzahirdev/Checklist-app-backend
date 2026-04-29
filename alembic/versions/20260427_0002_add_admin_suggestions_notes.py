"""Add admin suggestions and notes to reports

Revision ID: 20260427_0002
Revises: 20260427_0001_add_auditor_admin_view_permissions
Create Date: 2026-04-27 17:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260427_0002'
down_revision = '20260427_0001_add_auditor_admin_view_permissions'
branch_labels = None
depends_on = None


def upgrade():
    # Create report_admin_suggestions table
    op.create_table(
        'report_admin_suggestions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('report_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('admin_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('suggestion_text', sa.Text(), nullable=False),
        sa.Column('is_public', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['admin_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['report_id'], ['reports.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_report_admin_suggestions_report_id'), 'report_admin_suggestions', ['report_id'], unique=False)

    # Create report_admin_notes table
    op.create_table(
        'report_admin_notes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('report_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('admin_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('note_text', sa.Text(), nullable=False),
        sa.Column('note_type', sa.String(length=50), nullable=False, default='general'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['admin_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['report_id'], ['reports.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_report_admin_notes_report_id'), 'report_admin_notes', ['report_id'], unique=False)


def downgrade():
    # Drop report_admin_notes table
    op.drop_index(op.f('ix_report_admin_notes_report_id'), table_name='report_admin_notes')
    op.drop_table('report_admin_notes')
    
    # Drop report_admin_suggestions table
    op.drop_index(op.f('ix_report_admin_suggestions_report_id'), table_name='report_admin_suggestions')
    op.drop_table('report_admin_suggestions')
