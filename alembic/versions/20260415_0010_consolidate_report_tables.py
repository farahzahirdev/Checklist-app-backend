"""schema cleanup: consolidate report tables - remove redundant evaluation table

Revision ID: 20260415_0010
Revises: 20260415_0009
Create Date: 2026-04-15 00:00:00

Decision: Keep report_section_summaries, remove assessment_section_evaluations

Rationale:
- The MVP workflow is: user submits assessment → admin reviews → admin writes per-section
  summary paragraphs → PDF generated
- report_section_summaries captures the admin's written text for each section during review
- This text is what appears in the PDF report
- assessment_section_evaluations (with maturity_score and auditor_note per assessment-section)
  is redundant; section-level scoring can be calculated from question-level answers
- Removing reduces over-engineering for MVP

Drops:
- assessment_section_evaluations table
- assessment_section_scores table (associated with evaluations)
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260415_0010"
down_revision: str | None = "20260415_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop dependent table first (scores point to evaluations)
    op.drop_table("assessment_section_scores")
    
    # Drop the evaluations table
    op.drop_table("assessment_section_evaluations")


def downgrade() -> None:
    raise NotImplementedError("This migration is destructive and cannot be safely downgraded")
