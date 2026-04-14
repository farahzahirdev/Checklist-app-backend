"""manager schema alignment: languages, code tables, evaluations, dashboards support

Revision ID: 20260414_0004
Revises: 20260414_0003
Create Date: 2026-04-14 00:00:00
"""

from collections.abc import Sequence
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260414_0004"
down_revision: str | None = "20260414_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        "languages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "role_codes",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "payment_status_codes",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "checklist_status_codes",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "severity_codes",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "answer_option_codes",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("score", sa.SmallInteger(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "expected_implementations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "severity_translations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("severity_code_id", sa.SmallInteger(), nullable=False),
        sa.Column("language_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["severity_code_id"], ["severity_codes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["language_id"], ["languages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("severity_code_id", "language_id", name="uq_severity_translations"),
    )
    op.create_table(
        "answer_option_translations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("answer_option_code_id", sa.SmallInteger(), nullable=False),
        sa.Column("language_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["answer_option_code_id"], ["answer_option_codes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["language_id"], ["languages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("answer_option_code_id", "language_id", name="uq_answer_option_translations"),
    )
    op.create_table(
        "expected_implementation_translations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expected_implementation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("language_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["expected_implementation_id"], ["expected_implementations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["language_id"], ["languages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("expected_implementation_id", "language_id", name="uq_expected_impl_translations"),
    )

    role_codes_table = sa.table(
        "role_codes",
        sa.column("id", sa.SmallInteger()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    payment_status_codes_table = sa.table(
        "payment_status_codes",
        sa.column("id", sa.SmallInteger()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    checklist_status_codes_table = sa.table(
        "checklist_status_codes",
        sa.column("id", sa.SmallInteger()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    severity_codes_table = sa.table(
        "severity_codes",
        sa.column("id", sa.SmallInteger()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    answer_option_codes_table = sa.table(
        "answer_option_codes",
        sa.column("id", sa.SmallInteger()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("score", sa.SmallInteger()),
        sa.column("is_active", sa.Boolean()),
    )

    op.bulk_insert(
        role_codes_table,
        [
            {"id": 1, "code": "admin", "name": "Admin", "is_active": True},
            {"id": 2, "code": "auditor", "name": "Auditor", "is_active": True},
            {"id": 3, "code": "customer", "name": "Customer", "is_active": True},
        ],
    )
    op.bulk_insert(
        payment_status_codes_table,
        [
            {"id": 1, "code": "pending", "name": "Pending", "is_active": True},
            {"id": 2, "code": "succeeded", "name": "Succeeded", "is_active": True},
            {"id": 3, "code": "failed", "name": "Failed", "is_active": True},
        ],
    )
    op.bulk_insert(
        checklist_status_codes_table,
        [
            {"id": 1, "code": "draft", "name": "Draft", "is_active": True},
            {"id": 2, "code": "published", "name": "Published", "is_active": True},
            {"id": 3, "code": "archived", "name": "Archived", "is_active": True},
        ],
    )
    op.bulk_insert(
        severity_codes_table,
        [
            {"id": 1, "code": "low", "name": "Low", "is_active": True},
            {"id": 2, "code": "medium", "name": "Medium", "is_active": True},
            {"id": 3, "code": "high", "name": "High", "is_active": True},
        ],
    )
    op.bulk_insert(
        answer_option_codes_table,
        [
            {"id": 1, "code": "yes", "name": "Yes", "score": 4, "is_active": True},
            {"id": 2, "code": "partially", "name": "Partially", "score": 3, "is_active": True},
            {"id": 3, "code": "dont_know", "name": "Dont know", "score": 2, "is_active": True},
            {"id": 4, "code": "no", "name": "No", "score": 1, "is_active": True},
        ],
    )

    op.add_column("users", sa.Column("role_code_id", sa.SmallInteger(), nullable=True))
    op.create_foreign_key("fk_users_role_code_id", "users", "role_codes", ["role_code_id"], ["id"], ondelete="RESTRICT")
    op.execute(
        """
        UPDATE users
        SET role_code_id = CASE role::text
            WHEN 'admin' THEN 1
            WHEN 'auditor' THEN 2
            WHEN 'customer' THEN 3
            ELSE NULL
        END
        """
    )
    op.alter_column("users", "role_code_id", nullable=False)

    op.add_column("payments", sa.Column("status_code_id", sa.SmallInteger(), nullable=True))
    op.create_foreign_key(
        "fk_payments_status_code_id", "payments", "payment_status_codes", ["status_code_id"], ["id"], ondelete="RESTRICT"
    )
    op.execute(
        """
        UPDATE payments
        SET status_code_id = CASE status::text
            WHEN 'pending' THEN 1
            WHEN 'succeeded' THEN 2
            WHEN 'failed' THEN 3
            ELSE NULL
        END
        """
    )
    op.alter_column("payments", "status_code_id", nullable=False)

    op.add_column("checklists", sa.Column("status_code_id", sa.SmallInteger(), nullable=True))
    op.create_foreign_key(
        "fk_checklists_status_code_id", "checklists", "checklist_status_codes", ["status_code_id"], ["id"], ondelete="RESTRICT"
    )
    op.execute(
        """
        UPDATE checklists
        SET status_code_id = CASE status::text
            WHEN 'draft' THEN 1
            WHEN 'published' THEN 2
            WHEN 'archived' THEN 3
            ELSE NULL
        END
        """
    )
    op.alter_column("checklists", "status_code_id", nullable=False)

    op.add_column("checklist_questions", sa.Column("severity_code_id", sa.SmallInteger(), nullable=True))
    op.create_foreign_key(
        "fk_checklist_questions_severity_code_id",
        "checklist_questions",
        "severity_codes",
        ["severity_code_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute(
        """
        UPDATE checklist_questions
        SET severity_code_id = CASE severity::text
            WHEN 'low' THEN 1
            WHEN 'medium' THEN 2
            WHEN 'high' THEN 3
            ELSE NULL
        END
        """
    )
    op.alter_column("checklist_questions", "severity_code_id", nullable=False)

    op.add_column("assessment_answers", sa.Column("answer_option_code_id", sa.SmallInteger(), nullable=True))
    op.create_foreign_key(
        "fk_assessment_answers_answer_option_code_id",
        "assessment_answers",
        "answer_option_codes",
        ["answer_option_code_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute(
        """
        UPDATE assessment_answers
        SET answer_option_code_id = CASE answer::text
            WHEN 'yes' THEN 1
            WHEN 'partially' THEN 2
            WHEN 'dont_know' THEN 3
            WHEN 'no' THEN 4
            ELSE NULL
        END
        """
    )
    op.alter_column("assessment_answers", "answer_option_code_id", nullable=False)

    op.add_column("checklist_questions", sa.Column("expected_implementation_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_checklist_questions_expected_implementation_id",
        "checklist_questions",
        "expected_implementations",
        ["expected_implementation_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("checklist_translations", sa.Column("language_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("checklist_section_translations", sa.Column("language_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("checklist_question_translations", sa.Column("language_id", postgresql.UUID(as_uuid=True), nullable=True))

    op.create_foreign_key(
        "fk_checklist_translations_language_id",
        "checklist_translations",
        "languages",
        ["language_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_checklist_section_translations_language_id",
        "checklist_section_translations",
        "languages",
        ["language_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_checklist_question_translations_language_id",
        "checklist_question_translations",
        "languages",
        ["language_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    distinct_codes = set()
    rows = bind.execute(sa.text("SELECT DISTINCT lang_code FROM checklist_translations WHERE lang_code IS NOT NULL")).fetchall()
    distinct_codes.update(row[0] for row in rows)
    rows = bind.execute(sa.text("SELECT DISTINCT lang_code FROM checklist_section_translations WHERE lang_code IS NOT NULL")).fetchall()
    distinct_codes.update(row[0] for row in rows)
    rows = bind.execute(sa.text("SELECT DISTINCT lang_code FROM checklist_question_translations WHERE lang_code IS NOT NULL")).fetchall()
    distinct_codes.update(row[0] for row in rows)
    if not distinct_codes:
        distinct_codes.add("en")

    languages_table = sa.table(
        "languages",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("is_default", sa.Boolean()),
        sa.column("is_active", sa.Boolean()),
    )
    language_rows = []
    for code in sorted(distinct_codes):
        normalized = code.strip().lower()
        if not normalized:
            continue
        language_rows.append(
            {
                "id": uuid.uuid4(),
                "code": normalized,
                "name": normalized.upper(),
                "is_default": normalized == "en",
                "is_active": True,
            }
        )
    op.bulk_insert(languages_table, language_rows)

    op.execute(
        """
        UPDATE checklist_translations t
        SET language_id = l.id
        FROM languages l
        WHERE lower(t.lang_code) = l.code
        """
    )
    op.execute(
        """
        UPDATE checklist_section_translations t
        SET language_id = l.id
        FROM languages l
        WHERE lower(t.lang_code) = l.code
        """
    )
    op.execute(
        """
        UPDATE checklist_question_translations t
        SET language_id = l.id
        FROM languages l
        WHERE lower(t.lang_code) = l.code
        """
    )

    op.alter_column("checklist_translations", "language_id", nullable=False)
    op.alter_column("checklist_section_translations", "language_id", nullable=False)
    op.alter_column("checklist_question_translations", "language_id", nullable=False)

    op.create_unique_constraint(
        "uq_checklist_translations_language", "checklist_translations", ["checklist_id", "language_id"]
    )
    op.create_unique_constraint(
        "uq_checklist_section_translations_language",
        "checklist_section_translations",
        ["section_id", "language_id"],
    )
    op.create_unique_constraint(
        "uq_checklist_question_translations_language",
        "checklist_question_translations",
        ["question_id", "language_id"],
    )

    op.add_column("assessments", sa.Column("unlocked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("assessments", sa.Column("auditor_note", sa.Text(), nullable=True))
    op.add_column("assessments", sa.Column("final_maturity_score", sa.Numeric(5, 2), nullable=True))
    op.execute("UPDATE assessments SET unlocked_at = COALESCE(started_at, created_at) WHERE unlocked_at IS NULL")

    op.create_table(
        "assessment_section_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluator_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("maturity_score", sa.Numeric(4, 2), nullable=True),
        sa.Column("auditor_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["section_id"], ["checklist_sections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evaluator_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assessment_id", "section_id", name="uq_assessment_section_evaluation"),
    )


def downgrade() -> None:
    op.drop_table("assessment_section_evaluations")

    op.drop_column("assessments", "final_maturity_score")
    op.drop_column("assessments", "auditor_note")
    op.drop_column("assessments", "unlocked_at")

    op.drop_constraint("uq_checklist_question_translations_language", "checklist_question_translations", type_="unique")
    op.drop_constraint("uq_checklist_section_translations_language", "checklist_section_translations", type_="unique")
    op.drop_constraint("uq_checklist_translations_language", "checklist_translations", type_="unique")

    op.drop_constraint("fk_checklist_question_translations_language_id", "checklist_question_translations", type_="foreignkey")
    op.drop_constraint("fk_checklist_section_translations_language_id", "checklist_section_translations", type_="foreignkey")
    op.drop_constraint("fk_checklist_translations_language_id", "checklist_translations", type_="foreignkey")

    op.drop_column("checklist_question_translations", "language_id")
    op.drop_column("checklist_section_translations", "language_id")
    op.drop_column("checklist_translations", "language_id")

    op.drop_constraint("fk_checklist_questions_expected_implementation_id", "checklist_questions", type_="foreignkey")
    op.drop_column("checklist_questions", "expected_implementation_id")

    op.drop_constraint(
        "fk_assessment_answers_answer_option_code_id",
        "assessment_answers",
        type_="foreignkey",
    )
    op.drop_column("assessment_answers", "answer_option_code_id")

    op.drop_constraint("fk_checklist_questions_severity_code_id", "checklist_questions", type_="foreignkey")
    op.drop_column("checklist_questions", "severity_code_id")

    op.drop_constraint("fk_checklists_status_code_id", "checklists", type_="foreignkey")
    op.drop_column("checklists", "status_code_id")

    op.drop_constraint("fk_payments_status_code_id", "payments", type_="foreignkey")
    op.drop_column("payments", "status_code_id")

    op.drop_constraint("fk_users_role_code_id", "users", type_="foreignkey")
    op.drop_column("users", "role_code_id")

    op.drop_table("expected_implementation_translations")
    op.drop_table("answer_option_translations")
    op.drop_table("severity_translations")
    op.drop_table("expected_implementations")
    op.drop_table("answer_option_codes")
    op.drop_table("severity_codes")
    op.drop_table("checklist_status_codes")
    op.drop_table("payment_status_codes")
    op.drop_table("role_codes")
    op.drop_table("languages")
