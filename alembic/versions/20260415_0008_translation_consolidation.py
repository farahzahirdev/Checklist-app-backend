"""schema cleanup: translation consolidation - use language_id only

Revision ID: 20260415_0008
Revises: 20260415_0007
Create Date: 2026-04-15 00:00:00

Removes lang_code column from translation tables and rebuilds unique constraints:
- checklist_translations: drop lang_code, rebuild unique with language_id
- checklist_section_translations: drop lang_code, rebuild unique with language_id
- checklist_question_translations: drop lang_code, rebuild unique with language_id
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260415_0008"
down_revision: str | None = "20260415_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop and rebuild constraints for checklist_translations
    op.drop_constraint("uq_checklist_translations", "checklist_translations", type_="unique")
    op.drop_column("checklist_translations", "lang_code")
    op.create_unique_constraint(
        "uq_checklist_translations",
        "checklist_translations",
        ["checklist_id", "language_id"],
    )
    
    # Drop and rebuild constraints for checklist_section_translations
    op.drop_constraint("uq_section_translations", "checklist_section_translations", type_="unique")
    op.drop_column("checklist_section_translations", "lang_code")
    op.create_unique_constraint(
        "uq_section_translations",
        "checklist_section_translations",
        ["section_id", "language_id"],
    )
    
    # Drop and rebuild constraints for checklist_question_translations
    op.drop_constraint("uq_question_translations", "checklist_question_translations", type_="unique")
    op.drop_column("checklist_question_translations", "lang_code")
    op.create_unique_constraint(
        "uq_question_translations",
        "checklist_question_translations",
        ["question_id", "language_id"],
    )


def downgrade() -> None:
    raise NotImplementedError("This migration is destructive and cannot be safely downgraded")
