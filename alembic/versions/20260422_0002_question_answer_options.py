"""Add per-question answer options for checklist questions

Revision ID: 20260422_0002
Revises: 20260422_0001_question_score_and_title
Create Date: 2026-04-22 00:00:00

This migration creates a new table for admin-defined answer options attached to
checklist questions. Each question may now carry up to four answer options with
position, label, score, and optional choice code.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260422_0002"
down_revision: str | None = "20260422_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "checklist_question_answer_options",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("question_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("choice_code", sa.String(length=40), nullable=True),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["question_id"], ["checklist_questions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("question_id", "position", name="uq_question_answer_option_position"),
    )


def downgrade() -> None:
    op.drop_table("checklist_question_answer_options")
