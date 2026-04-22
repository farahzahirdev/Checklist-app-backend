"""Add question points, answer logic, and paragraph title translation

Revision ID: 20260422_0001
Revises: 20260420_0001_remove_checklist_type_version_unique
Create Date: 2026-04-22 00:00:00

This revision adds direct scoring support for checklist questions, restores
paragraph title support for translations, and introduces a small answer logic
flag to preserve question scoring mode information.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260422_0001"
down_revision: str | None = "20260420_0001_remove_checklist_type_version_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "checklist_questions",
        sa.Column("points", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "checklist_questions",
        sa.Column("answer_logic", sa.String(length=40), nullable=False, server_default=sa.text("'answer_only'")),
    )
    op.add_column(
        "checklist_question_translations",
        sa.Column("paragraph_title", sa.String(length=255), nullable=True),
    )

    # Remove server defaults now that the columns are populated.
    op.alter_column("checklist_questions", "points", server_default=None)
    op.alter_column("checklist_questions", "answer_logic", server_default=None)


def downgrade() -> None:
    op.drop_column("checklist_question_translations", "paragraph_title")
    op.drop_column("checklist_questions", "answer_logic")
    op.drop_column("checklist_questions", "points")
