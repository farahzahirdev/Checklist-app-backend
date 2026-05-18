"""Add encrypted PDF password field to reports.

Revision ID: 20260518_0001_add_report_pdf_password_encrypted
Revises: 20260515_0001_question_translation_answer_options
Create Date: 2026-05-18 00:01:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260518_0001_add_report_pdf_password_encrypted"
down_revision = "20260515_0001_question_translation_answer_options"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reports", sa.Column("final_pdf_password_encrypted", sa.String(length=1024), nullable=True))


def downgrade() -> None:
    op.drop_column("reports", "final_pdf_password_encrypted")
