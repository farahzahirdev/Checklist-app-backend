"""schema cleanup: consolidate text fields to translation tables only

Revision ID: 20260415_0009
Revises: 20260415_0008
Create Date: 2026-04-15 00:00:00

Removes text fields from core tables (must exist in translation tables already):
- checklists: drop title, description
- checklist_sections: drop title
- checklist_questions: drop paragraph_title, legal_requirement, question_text, explanation,
  expected_implementation, guidance_score_4, guidance_score_3, guidance_score_2, 
  guidance_score_1, recommendation_template
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260415_0009"
down_revision: str | None = "20260415_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop title and description from checklists
    op.drop_column("checklists", "title")
    op.drop_column("checklists", "description")
    
    # Drop title from checklist_sections
    op.drop_column("checklist_sections", "title")
    
    # Drop all text fields from checklist_questions
    op.drop_column("checklist_questions", "paragraph_title")
    op.drop_column("checklist_questions", "legal_requirement")
    op.drop_column("checklist_questions", "question_text")
    op.drop_column("checklist_questions", "explanation")
    op.drop_column("checklist_questions", "expected_implementation")
    op.drop_column("checklist_questions", "guidance_score_4")
    op.drop_column("checklist_questions", "guidance_score_3")
    op.drop_column("checklist_questions", "guidance_score_2")
    op.drop_column("checklist_questions", "guidance_score_1")
    op.drop_column("checklist_questions", "recommendation_template")


def downgrade() -> None:
    raise NotImplementedError("This migration is destructive and cannot be safely downgraded")
