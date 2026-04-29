"""Add assessment review tables

Revision ID: 2026_04_27_22_15
Revises: 2024_03_15_10_30_create_initial_tables
Create Date: 2026-04-27 22:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2026_04_27_22_15'
down_revision: Union[str, None] = '20260427_0002_merge_auditor_permissions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create review_status enum (if not exists)
    try:
        op.execute("CREATE TYPE review_status AS ENUM ('pending', 'in_progress', 'completed', 'rejected')")
    except:
        # Enum already exists, skip
        pass
    
    # Create suggestion_type enum (if not exists)
    try:
        op.execute("CREATE TYPE suggestion_type AS ENUM ('improvement', 'required_change', 'best_practice', 'reference', 'clarification')")
    except:
        # Enum already exists, skip
        pass
    
    # Create assessment_reviews table (without enum columns first)
    op.create_table(
        'assessment_reviews',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('assessment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reviewer_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('overall_score', sa.Integer(), nullable=True),
        sa.Column('max_score', sa.Integer(), nullable=True),
        sa.Column('completion_percentage', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('summary_notes', sa.Text(), nullable=True),
        sa.Column('strengths', sa.Text(), nullable=True),
        sa.Column('improvement_areas', sa.Text(), nullable=True),
        sa.Column('recommendations', sa.Text(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('assessment_id'),
        sa.CheckConstraint('overall_score >= 0', name='check_overall_score_positive'),
        sa.CheckConstraint('max_score >= 0', name='check_max_score_positive'),
        sa.CheckConstraint('completion_percentage >= 0 AND completion_percentage <= 100', name='check_completion_percentage_range')
    )
    
    # Add status column separately
    try:
        op.execute("ALTER TABLE assessment_reviews ADD COLUMN status review_status NOT NULL DEFAULT 'pending'")
    except:
        # Column might already exist
        pass
    op.create_index(op.f('ix_assessment_reviews_assessment_id'), 'assessment_reviews', ['assessment_id'], unique=False)
    op.create_index(op.f('ix_assessment_reviews_reviewer_id'), 'assessment_reviews', ['reviewer_id'], unique=False)
    op.create_index(op.f('ix_assessment_reviews_status'), 'assessment_reviews', ['status'], unique=False)
    
    # Create answer_reviews table (without enum columns first)
    op.create_table(
        'answer_reviews',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('assessment_review_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('answer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reviewer_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('suggestion_text', sa.Text(), nullable=False),
        sa.Column('reference_materials', sa.Text(), nullable=True),
        sa.Column('is_action_required', sa.Boolean(), nullable=False),
        sa.Column('priority_level', sa.Integer(), nullable=False),
        sa.Column('score_adjustment', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['answer_id'], ['assessment_answers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assessment_review_id'], ['assessment_reviews.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('answer_id'),
        sa.CheckConstraint('priority_level >= 1 AND priority_level <= 5', name='check_priority_level_range')
    )
    
    # Add suggestion_type column separately
    try:
        op.execute("ALTER TABLE answer_reviews ADD COLUMN suggestion_type suggestion_type NOT NULL DEFAULT 'improvement'")
    except:
        # Column might already exist
        pass
    op.create_index(op.f('ix_answer_reviews_answer_id'), 'answer_reviews', ['answer_id'], unique=False)
    op.create_index(op.f('ix_answer_reviews_assessment_review_id'), 'answer_reviews', ['assessment_review_id'], unique=False)
    op.create_index(op.f('ix_answer_reviews_reviewer_id'), 'answer_reviews', ['reviewer_id'], unique=False)
    op.create_index(op.f('ix_answer_reviews_is_action_required'), 'answer_reviews', ['is_action_required'], unique=False)
    op.create_index(op.f('ix_answer_reviews_priority_level'), 'answer_reviews', ['priority_level'], unique=False)
    
    # Create review_history table
    op.create_table(
        'review_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('assessment_review_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reviewer_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action_type', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('previous_values', sa.Text(), nullable=True),
        sa.Column('new_values', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['assessment_review_id'], ['assessment_reviews.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_review_history_assessment_review_id'), 'review_history', ['assessment_review_id'], unique=False)
    op.create_index(op.f('ix_review_history_reviewer_id'), 'review_history', ['reviewer_id'], unique=False)
    op.create_index(op.f('ix_review_history_created_at'), 'review_history', ['created_at'], unique=False)
    
    # Create triggers for updated_at timestamps
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    
    op.execute("""
        CREATE TRIGGER update_assessment_reviews_updated_at 
            BEFORE UPDATE ON assessment_reviews 
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)
    
    op.execute("""
        CREATE TRIGGER update_answer_reviews_updated_at 
            BEFORE UPDATE ON answer_reviews 
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS update_assessment_reviews_updated_at ON assessment_reviews")
    op.execute("DROP TRIGGER IF EXISTS update_answer_reviews_updated_at ON answer_reviews")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")
    
    # Drop tables
    op.drop_index(op.f('ix_review_history_created_at'), table_name='review_history')
    op.drop_index(op.f('ix_review_history_reviewer_id'), table_name='review_history')
    op.drop_index(op.f('ix_review_history_assessment_review_id'), table_name='review_history')
    op.drop_table('review_history')
    
    op.drop_index(op.f('ix_answer_reviews_priority_level'), table_name='answer_reviews')
    op.drop_index(op.f('ix_answer_reviews_is_action_required'), table_name='answer_reviews')
    op.drop_index(op.f('ix_answer_reviews_reviewer_id'), table_name='answer_reviews')
    op.drop_index(op.f('ix_answer_reviews_assessment_review_id'), table_name='answer_reviews')
    op.drop_index(op.f('ix_answer_reviews_answer_id'), table_name='answer_reviews')
    op.drop_table('answer_reviews')
    
    op.drop_index(op.f('ix_assessment_reviews_status'), table_name='assessment_reviews')
    op.drop_index(op.f('ix_assessment_reviews_reviewer_id'), table_name='assessment_reviews')
    op.drop_index(op.f('ix_assessment_reviews_assessment_id'), table_name='assessment_reviews')
    op.drop_table('assessment_reviews')
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS suggestion_type")
    op.execute("DROP TYPE IF EXISTS review_status")
