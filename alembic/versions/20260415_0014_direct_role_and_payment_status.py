"""move role and payment status to direct string columns

Revision ID: 20260415_0014
Revises: 20260415_0013
Create Date: 2026-04-15 03:20:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260415_0014"
down_revision: str | None = "20260415_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("role", sa.String(length=20), nullable=True))
    op.execute(
        """
        UPDATE users
        SET role = CASE role_code_id
            WHEN 1 THEN 'admin'
            WHEN 2 THEN 'auditor'
            WHEN 3 THEN 'customer'
            ELSE 'customer'
        END
        """
    )
    op.alter_column("users", "role", nullable=False)
    op.drop_constraint("fk_users_role_code_id", "users", type_="foreignkey")
    op.drop_column("users", "role_code_id")

    op.add_column("payments", sa.Column("status", sa.String(length=20), nullable=True))
    op.execute(
        """
        UPDATE payments
        SET status = CASE status_code_id
            WHEN 1 THEN 'pending'
            WHEN 2 THEN 'succeeded'
            WHEN 3 THEN 'failed'
            ELSE 'pending'
        END
        """
    )
    op.alter_column("payments", "status", nullable=False)
    op.drop_constraint("fk_payments_status_code_id", "payments", type_="foreignkey")
    op.drop_column("payments", "status_code_id")

    op.add_column("audit_logs", sa.Column("actor_role", sa.String(length=20), nullable=True))
    op.execute(
        """
        UPDATE audit_logs
        SET actor_role = CASE actor_role_code_id
            WHEN 1 THEN 'admin'
            WHEN 2 THEN 'auditor'
            WHEN 3 THEN 'customer'
            ELSE NULL
        END
        """
    )
    op.drop_constraint("fk_audit_logs_actor_role_code_id", "audit_logs", type_="foreignkey")
    op.drop_column("audit_logs", "actor_role_code_id")

    op.drop_table("payment_status_codes")
    op.drop_table("role_codes")


def downgrade() -> None:
    raise NotImplementedError("This migration cannot be safely downgraded")
