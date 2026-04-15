"""add user note field to checklist questions

Revision ID: 20260415_0012
Revises: 20260415_0011
Create Date: 2026-04-15 01:10:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260415_0012"
down_revision: str | None = "20260415_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("checklist_questions", sa.Column("note_for_user", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("checklist_questions", "note_for_user")
