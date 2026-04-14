"""schema migration: transition from enums to code table foreign keys

Revision ID: 20260415_0007
Revises: 20260415_0006
Create Date: 2026-04-15 00:00:00

Converts enum columns to foreign keys of code tables:
- audit_logs.actor_role → audit_logs.actor_role_code_id
- users.role → users.role_code_id (already has FK, dropping enum column)
- payments.status → payments.status_code_id (already has FK, dropping enum column)
- checklists.status → checklists.status_code_id (already has FK, dropping enum column)
- checklist_questions.severity → checklist_questions.severity_code_id (already has FK, dropping enum column)
- assessment_answers.answer → assessment_answers.answer_option_code_id (already has FK, dropping enum column)

Then drops the PostgreSQL enum types.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260415_0007"
down_revision: str | None = "20260415_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Migrate audit logs role enum to role code FK before dropping user_role type.
    op.add_column("audit_logs", sa.Column("actor_role_code_id", sa.SmallInteger(), nullable=True))
    op.create_foreign_key(
        "fk_audit_logs_actor_role_code_id",
        "audit_logs",
        "role_codes",
        ["actor_role_code_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute(
        """
        UPDATE audit_logs
        SET actor_role_code_id = CASE actor_role::text
            WHEN 'admin' THEN 1
            WHEN 'auditor' THEN 2
            WHEN 'customer' THEN 3
            ELSE NULL
        END
        """
    )
    op.drop_column("audit_logs", "actor_role")

    # Drop enum-backed columns whose code FK columns already exist.
    op.drop_column("users", "role")
    op.drop_column("payments", "status")
    op.drop_column("checklists", "status")
    op.drop_column("checklist_questions", "severity")
    op.drop_column("assessment_answers", "answer")

    # Drop the PostgreSQL enum types
    op.execute("DROP TYPE IF EXISTS user_role")
    op.execute("DROP TYPE IF EXISTS payment_status")
    op.execute("DROP TYPE IF EXISTS checklist_status")
    op.execute("DROP TYPE IF EXISTS severity_level")
    op.execute("DROP TYPE IF EXISTS answer_choice")


def downgrade() -> None:
    # This is a destructive migration; downgrade is not practical
    raise NotImplementedError("This migration is destructive and cannot be safely downgraded")
