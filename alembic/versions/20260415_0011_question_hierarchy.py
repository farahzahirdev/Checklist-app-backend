"""add parent-child relation for checklist questions

Revision ID: 20260415_0011
Revises: 20260415_0010
Create Date: 2026-04-15 00:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260415_0011"
down_revision: str | None = "20260415_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "checklist_questions",
        sa.Column("parent_question_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_checklist_questions_parent_question_id",
        "checklist_questions",
        "checklist_questions",
        ["parent_question_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_checklist_questions_parent_question_id",
        "checklist_questions",
        ["parent_question_id"],
        unique=False,
    )
    op.create_check_constraint(
        "ck_checklist_questions_parent_not_self",
        "checklist_questions",
        "parent_question_id IS NULL OR parent_question_id <> id",
    )


def downgrade() -> None:
    op.drop_constraint("ck_checklist_questions_parent_not_self", "checklist_questions", type_="check")
    op.drop_index("ix_checklist_questions_parent_question_id", table_name="checklist_questions")
    op.drop_constraint("fk_checklist_questions_parent_question_id", "checklist_questions", type_="foreignkey")
    op.drop_column("checklist_questions", "parent_question_id")
