"""schema cleanup: remove unused columns

Revision ID: 20260415_0006
Revises: 20260415_0005
Create Date: 2026-04-15 00:00:00

Removes:
- final_score_mode column from checklist_questions (only one scoring model in MVP)
- unlocked_at column from assessments (duplicate of activated_at on access_windows)
- changes_requested value from report_status and report_event_type enums (no "send back" workflow in MVP)
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260415_0006"
down_revision: str | None = "20260415_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop final_score_mode column from checklist_questions
    op.drop_column("checklist_questions", "final_score_mode")

    # Drop unlocked_at column from assessments
    op.drop_column("assessments", "unlocked_at")

    # Remove changes_requested from report_status enum
    # PostgreSQL enums can't just remove a value, so we need to recreate the enum
    # First create a temporary enum with the new values
    op.execute("""
        ALTER TYPE report_status ADD VALUE 'temp_marker' BEFORE 'published';
    """)
    
    # Create new enum with old values minus changes_requested
    op.execute("""
        CREATE TYPE report_status_new AS ENUM (
            'draft_generated',
            'under_review',
            'approved',
            'published'
        );
    """)
    
    # Convert existing values
    op.execute("""
        ALTER TABLE reports ALTER COLUMN status TYPE report_status_new 
        USING status::text::report_status_new;
    """)
    
    # Drop old enum and rename new one
    op.execute("DROP TYPE report_status;")
    op.execute("ALTER TYPE report_status_new RENAME TO report_status;")
    
    # Remove changes_requested from report_event_type enum
    op.execute("""
        CREATE TYPE report_event_type_new AS ENUM (
            'draft_generated',
            'review_started',
            'summary_updated',
            'approved',
            'published'
        );
    """)
    
    # Convert existing values
    op.execute("""
        ALTER TABLE report_review_events ALTER COLUMN event_type TYPE report_event_type_new 
        USING event_type::text::report_event_type_new;
    """)
    
    # Drop old enum and rename new one
    op.execute("DROP TYPE report_event_type;")
    op.execute("ALTER TYPE report_event_type_new RENAME TO report_event_type;")


def downgrade() -> None:
    # This is a destructive migration; downgrade is not practical
    raise NotImplementedError("This migration is destructive and cannot be safely downgraded")
