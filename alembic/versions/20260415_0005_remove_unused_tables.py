"""schema cleanup: remove unused tables and enums

Revision ID: 20260415_0005
Revises: 20260414_0004
Create Date: 2026-04-15 00:00:00

Removes:
- operational_events table and operational_event_type, operational_severity enums
- access_events table and access_event_type enum
- expected_implementations and expected_implementation_translations tables
- expected_implementation_id FK from checklist_questions
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260415_0005"
down_revision: str | None = "20260414_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop the FK from checklist_questions to expected_implementations
    op.drop_constraint("fk_checklist_questions_expected_implementation_id", "checklist_questions", type_="foreignkey")
    op.drop_column("checklist_questions", "expected_implementation_id")

    # Drop expected_implementation_translations table
    op.drop_table("expected_implementation_translations")

    # Drop expected_implementations table
    op.drop_table("expected_implementations")

    # Drop access_events table
    op.drop_table("access_events")

    # Drop operational_events table
    op.drop_table("operational_events")

    # Drop the PostgreSQL enum types
    op.execute("DROP TYPE IF EXISTS operational_event_type")
    op.execute("DROP TYPE IF EXISTS operational_severity")
    op.execute("DROP TYPE IF EXISTS access_event_type")


def downgrade() -> None:
    # This is a destructive migration; downgrade is not practical
    # (would need to recreate data that was deleted)
    raise NotImplementedError("This migration is destructive and cannot be safely downgraded")
