"""bind payments to checklist

Revision ID: 20260414_0003
Revises: 20260413_0002
Create Date: 2026-04-14 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260414_0003"
down_revision: str | None = "20260413_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("checklist_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_payments_checklist_id",
        "payments",
        "checklists",
        ["checklist_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_payments_checklist_id", "payments", type_="foreignkey")
    op.drop_column("payments", "checklist_id")
