"""add user preferred language

Revision ID: 20260522_0003
Revises: 20260522_0002
Create Date: 2026-05-22 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260522_0003"
down_revision: Union[str, None] = "20260522_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("preferred_language", sa.String(length=5), nullable=False, server_default="en"))
    op.execute("UPDATE users SET preferred_language = 'en' WHERE preferred_language IS NULL OR preferred_language = ''")
    op.alter_column("users", "preferred_language", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "preferred_language")
