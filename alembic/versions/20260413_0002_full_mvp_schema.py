"""full mvp schema

Revision ID: 20260413_0002
Revises: 20260410_0001
Create Date: 2026-04-13 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260413_0002"
down_revision: str | None = "20260410_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


access_event_type = postgresql.ENUM(
    "unlocked_after_payment",
    "assessment_started",
    "access_expired",
    "manually_extended",
    "manually_revoked",
    name="access_event_type",
    create_type=True,
)
checklist_status = postgresql.ENUM("draft", "published", "archived", name="checklist_status", create_type=True)
severity_level = postgresql.ENUM("low", "medium", "high", name="severity_level", create_type=True)
question_score_mode = postgresql.ENUM(
    "answer_only", "answer_with_adjustment", name="question_score_mode", create_type=True
)
answer_choice = postgresql.ENUM("yes", "partially", "dont_know", "no", name="answer_choice", create_type=True)
priority_level = postgresql.ENUM("low", "medium", "high", name="priority_level", create_type=True)
assessment_status = postgresql.ENUM(
    "not_started", "in_progress", "submitted", "expired", "closed", name="assessment_status", create_type=True
)
malware_scan_status = postgresql.ENUM(
    "pending", "clean", "infected", "failed", name="malware_scan_status", create_type=True
)
report_status = postgresql.ENUM(
    "draft_generated", "under_review", "changes_requested", "approved", "published", name="report_status", create_type=True
)
report_event_type = postgresql.ENUM(
    "draft_generated",
    "review_started",
    "summary_updated",
    "changes_requested",
    "approved",
    "published",
    name="report_event_type",
    create_type=True,
)
audit_action = postgresql.ENUM(
    "auth_login",
    "auth_logout",
    "auth_mfa_verify",
    "checklist_create",
    "checklist_update",
    "checklist_publish",
    "assessment_submit",
    "report_approve",
    "report_publish",
    "user_role_change",
    name="audit_action",
    create_type=True,
)
operational_event_type = postgresql.ENUM(
    "payment_webhook_received",
    "payment_webhook_processed",
    "report_generation_started",
    "report_generation_finished",
    "retention_job_started",
    "retention_job_finished",
    "file_scan_completed",
    name="operational_event_type",
    create_type=True,
)
operational_severity = postgresql.ENUM("info", "warning", "error", name="operational_severity", create_type=True)


def upgrade() -> None:
    bind = op.get_bind()
    access_event_type.create(bind, checkfirst=True)
    checklist_status.create(bind, checkfirst=True)
    severity_level.create(bind, checkfirst=True)
    question_score_mode.create(bind, checkfirst=True)
    answer_choice.create(bind, checkfirst=True)
    priority_level.create(bind, checkfirst=True)
    assessment_status.create(bind, checkfirst=True)
    malware_scan_status.create(bind, checkfirst=True)
    report_status.create(bind, checkfirst=True)
    report_event_type.create(bind, checkfirst=True)
    audit_action.create(bind, checkfirst=True)
    operational_event_type.create(bind, checkfirst=True)
    operational_severity.create(bind, checkfirst=True)

    op.create_table(
        "mfa_totp",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("secret_encrypted", sa.String(), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("backup_codes_hash", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_mfa_totp_user_id", "mfa_totp", ["user_id"], unique=False)

    op.create_table(
        "access_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("access_window_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "event_type",
            postgresql.ENUM(
                "unlocked_after_payment",
                "assessment_started",
                "access_expired",
                "manually_extended",
                "manually_revoked",
                name="access_event_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("event_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["access_window_id"], ["access_windows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "checklist_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "checklists",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("checklist_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM("draft", "published", "archived", name="checklist_status", create_type=False),
            nullable=False,
        ),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["checklist_type_id"], ["checklist_types.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("checklist_type_id", "version", name="uq_checklists_type_version"),
    )

    op.create_table(
        "checklist_sections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("checklist_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section_code", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("source_ref", sa.String(length=255), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["checklist_id"], ["checklists.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("checklist_id", "display_order", name="uq_sections_checklist_order"),
        sa.UniqueConstraint("checklist_id", "section_code", name="uq_sections_checklist_code"),
    )

    op.create_table(
        "checklist_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("checklist_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_code", sa.String(length=120), nullable=False),
        sa.Column("paragraph_title", sa.String(length=255), nullable=True),
        sa.Column("legal_requirement", sa.Text(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("expected_implementation", sa.Text(), nullable=True),
        sa.Column("guidance_score_4", sa.Text(), nullable=True),
        sa.Column("guidance_score_3", sa.Text(), nullable=True),
        sa.Column("guidance_score_2", sa.Text(), nullable=True),
        sa.Column("guidance_score_1", sa.Text(), nullable=True),
        sa.Column("recommendation_template", sa.Text(), nullable=True),
        sa.Column(
            "severity",
            postgresql.ENUM("low", "medium", "high", name="severity_level", create_type=False),
            nullable=False,
        ),
        sa.Column("report_domain", sa.String(length=120), nullable=True),
        sa.Column("report_chapter", sa.String(length=120), nullable=True),
        sa.Column("illustrative_image_url", sa.Text(), nullable=True),
        sa.Column("note_enabled", sa.Boolean(), nullable=False),
        sa.Column("evidence_enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "final_score_mode",
            postgresql.ENUM(
                "answer_only", "answer_with_adjustment", name="question_score_mode", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["checklist_id"], ["checklists.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["section_id"], ["checklist_sections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("checklist_id", "question_code", name="uq_questions_checklist_code"),
        sa.UniqueConstraint("section_id", "display_order", name="uq_questions_section_order"),
    )

    op.create_table(
        "checklist_translations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("checklist_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lang_code", sa.String(length=10), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["checklist_id"], ["checklists.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("checklist_id", "lang_code", name="uq_checklist_translations"),
    )

    op.create_table(
        "checklist_section_translations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lang_code", sa.String(length=10), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["section_id"], ["checklist_sections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("section_id", "lang_code", name="uq_section_translations"),
    )

    op.create_table(
        "checklist_question_translations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lang_code", sa.String(length=10), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("expected_implementation", sa.Text(), nullable=True),
        sa.Column("guidance_score_4", sa.Text(), nullable=True),
        sa.Column("guidance_score_3", sa.Text(), nullable=True),
        sa.Column("guidance_score_2", sa.Text(), nullable=True),
        sa.Column("guidance_score_1", sa.Text(), nullable=True),
        sa.Column("recommendation_template", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["checklist_questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("question_id", "lang_code", name="uq_question_translations"),
    )

    op.create_table(
        "assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("checklist_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("access_window_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "not_started",
                "in_progress",
                "submitted",
                "expired",
                "closed",
                name="assessment_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completion_percent", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["access_window_id"], ["access_windows.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["checklist_id"], ["checklists.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "assessment_answers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "answer",
            postgresql.ENUM("yes", "partially", "dont_know", "no", name="answer_choice", create_type=False),
            nullable=False,
        ),
        sa.Column("answer_score", sa.Integer(), nullable=False),
        sa.Column(
            "weighted_priority",
            postgresql.ENUM("low", "medium", "high", name="priority_level", create_type=False),
            nullable=True,
        ),
        sa.Column("note_text", sa.Text(), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["checklist_questions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assessment_id", "question_id", name="uq_assessment_question_answer"),
    )

    op.create_table(
        "assessment_evidence_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("answer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "scan_status",
            postgresql.ENUM(
                "pending", "clean", "infected", "failed", name="malware_scan_status", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["answer_id"], ["assessment_answers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["checklist_questions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "assessment_section_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("avg_score", sa.Numeric(precision=4, scale=2), nullable=False),
        sa.Column("answered_count", sa.Integer(), nullable=False),
        sa.Column("total_count", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["section_id"], ["checklist_sections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assessment_id", "section_id", name="uq_assessment_section_score"),
    )

    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "draft_generated",
                "under_review",
                "changes_requested",
                "approved",
                "published",
                name="report_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("draft_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("final_pdf_storage_key", sa.String(length=512), nullable=True),
        sa.Column("final_pdf_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("draft_deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("final_deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assessment_id"),
    )

    op.create_table(
        "report_section_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("chapter_code", sa.String(length=120), nullable=True),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["section_id"], ["checklist_sections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "report_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("answer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "priority",
            postgresql.ENUM("low", "medium", "high", name="priority_level", create_type=False),
            nullable=False,
        ),
        sa.Column("finding_text", sa.Text(), nullable=False),
        sa.Column("recommendation_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["answer_id"], ["assessment_answers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["checklist_questions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "report_review_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "event_type",
            postgresql.ENUM(
                "draft_generated",
                "review_started",
                "summary_updated",
                "changes_requested",
                "approved",
                "published",
                name="report_event_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("event_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "actor_role",
            postgresql.ENUM("admin", "auditor", "customer", name="user_role", create_type=False),
            nullable=True,
        ),
        sa.Column(
            "action",
            postgresql.ENUM(
                "auth_login",
                "auth_logout",
                "auth_mfa_verify",
                "checklist_create",
                "checklist_update",
                "checklist_publish",
                "assessment_submit",
                "report_approve",
                "report_publish",
                "user_role_change",
                name="audit_action",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("target_entity", sa.String(length=120), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("before_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "operational_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "event_type",
            postgresql.ENUM(
                "payment_webhook_received",
                "payment_webhook_processed",
                "report_generation_started",
                "report_generation_finished",
                "retention_job_started",
                "retention_job_finished",
                "file_scan_completed",
                name="operational_event_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "severity",
            postgresql.ENUM("info", "warning", "error", name="operational_severity", create_type=False),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("operational_events")
    op.drop_table("audit_logs")
    op.drop_table("report_review_events")
    op.drop_table("report_findings")
    op.drop_table("report_section_summaries")
    op.drop_table("reports")
    op.drop_table("assessment_section_scores")
    op.drop_table("assessment_evidence_files")
    op.drop_table("assessment_answers")
    op.drop_table("assessments")
    op.drop_table("checklist_question_translations")
    op.drop_table("checklist_section_translations")
    op.drop_table("checklist_translations")
    op.drop_table("checklist_questions")
    op.drop_table("checklist_sections")
    op.drop_table("checklists")
    op.drop_table("checklist_types")
    op.drop_table("access_events")
    op.drop_index("ix_mfa_totp_user_id", table_name="mfa_totp")
    op.drop_table("mfa_totp")

    bind = op.get_bind()
    operational_severity.drop(bind, checkfirst=True)
    operational_event_type.drop(bind, checkfirst=True)
    audit_action.drop(bind, checkfirst=True)
    report_event_type.drop(bind, checkfirst=True)
    report_status.drop(bind, checkfirst=True)
    malware_scan_status.drop(bind, checkfirst=True)
    assessment_status.drop(bind, checkfirst=True)
    priority_level.drop(bind, checkfirst=True)
    answer_choice.drop(bind, checkfirst=True)
    question_score_mode.drop(bind, checkfirst=True)
    severity_level.drop(bind, checkfirst=True)
    checklist_status.drop(bind, checkfirst=True)
    access_event_type.drop(bind, checkfirst=True)
