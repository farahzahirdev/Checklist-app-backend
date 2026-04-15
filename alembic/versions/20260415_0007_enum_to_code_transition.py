"""schema migration: transition from enums to code table foreign keys

Revision ID: 20260415_0007
Revises: 20260415_0006
Create Date: 2026-04-15 00:00:00

Converts enum columns to foreign keys of code tables:
- users.role → users.role_code_id (already has FK, dropping enum column)
- payments.status → payments.status_code_id (already has FK, dropping enum column)
- checklists.status → checklists.status_code_id (already has FK, dropping enum column)
- checklist_questions.severity → checklist_questions.severity_code_id (already has FK, dropping enum column)
- assessment_answers.answer → assessment_answers.answer_option_code_id (already has FK, dropping enum column)

Then drops the PostgreSQL enum types.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260415_0007"
down_revision: str | None = "20260415_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop the enum columns (the code FKs already exist)
    op.drop_column("users", "role")
    op.drop_column("payments", "status")
    op.drop_column("checklists", "status")
    op.drop_column("checklist_questions", "severity")
    op.drop_column("assessment_answers", "answer")
    
    # Drop the PostgreSQL enum types
    op.execute("DROP TYPE IF EXISTS user_role")
    op.execute("DROP TYPE IF EXISTS payment_status")
    op.execute("DROP TYPE IF EXISTS checklist_status")
    op.execute("DROP TYPE IF EXISTS severity_level")
    op.execute("DROP TYPE IF EXISTS answer_choice")


def downgrade() -> None:
    # This is a destructive migration; downgrade is not practical
    raise NotImplementedError("This migration is destructive and cannot be safely downgraded")
