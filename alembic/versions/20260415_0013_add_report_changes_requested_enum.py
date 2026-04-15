"""add changes_requested enum value to report status/event enums

Revision ID: 20260415_0013
Revises: 20260415_0012
Create Date: 2026-04-15 02:00:00
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260415_0013"
down_revision: str | None = "20260415_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE report_status ADD VALUE IF NOT EXISTS 'changes_requested'")
    op.execute("ALTER TYPE report_event_type ADD VALUE IF NOT EXISTS 'changes_requested'")


def downgrade() -> None:
    raise NotImplementedError("This migration cannot safely remove enum values")
