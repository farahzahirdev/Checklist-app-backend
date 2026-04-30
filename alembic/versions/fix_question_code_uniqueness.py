"""Fix question code uniqueness to section-level only"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fix_question_code_uniqueness'
down_revision = '360657baa2c7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the old constraint
    op.drop_constraint('uq_questions_checklist_code', 'checklist_questions', type_='unique')
    
    # Add the new constraint for section-level uniqueness
    op.create_unique_constraint('uq_questions_checklist_code', 'checklist_questions', ['section_id', 'question_code'])


def downgrade() -> None:
    # Drop the new constraint
    op.drop_constraint('uq_questions_checklist_code', 'checklist_questions', type_='unique')
    
    # Add back the old constraint for checklist-level uniqueness
    op.create_unique_constraint('uq_questions_checklist_code', 'checklist_questions', ['checklist_id', 'question_code'])
