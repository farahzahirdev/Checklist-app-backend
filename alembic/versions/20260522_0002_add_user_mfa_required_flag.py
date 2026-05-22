"""add user mfa_required flag

Revision ID: 20260522_0002
Revises: 20260522_0001
Create Date: 2026-05-22 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260522_0002"
down_revision: Union[str, None] = "20260522_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("mfa_required", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.execute("UPDATE users SET mfa_required = true WHERE mfa_required IS NULL")
    op.alter_column("users", "mfa_required", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "mfa_required")
