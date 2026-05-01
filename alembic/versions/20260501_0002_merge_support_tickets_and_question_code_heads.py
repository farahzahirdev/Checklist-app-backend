"""merge support/password and question-code heads

Revision ID: 20260501_0002_merge_support_tickets_and_question_code_heads
Revises: 20260501_0001_support_tickets_and_password_reset, fix_question_code_uniqueness
Create Date: 2026-05-01 12:00:00.000000
"""


# revision identifiers, used by Alembic.
revision = "20260501_0002_merge_support_tickets_and_question_code_heads"
down_revision = ("20260501_0001_support_tickets_and_password_reset", "fix_question_code_uniqueness")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
