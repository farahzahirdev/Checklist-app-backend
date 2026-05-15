"""Add answer_options JSON to question translations

Revision ID: 20260515_0001_question_translation_answer_options
Revises: 20260513_0001_add_report_code_to_reports
Create Date: 2026-05-15 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260515_0001_question_translation_answer_options"
down_revision = "20260513_0001_add_report_code_to_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "checklist_question_translations",
        sa.Column("answer_options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("checklist_question_translations", "answer_options")
