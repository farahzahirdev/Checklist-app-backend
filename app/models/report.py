from datetime import datetime
from enum import StrEnum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.assessment import PriorityLevel


class ReportStatus(StrEnum):
    draft_generated = "draft_generated"
    under_review = "under_review"
    approved = "approved"
    published = "published"


class ReportEventType(StrEnum):
    draft_generated = "draft_generated"
    review_started = "review_started"
    summary_updated = "summary_updated"
    approved = "approved"
    published = "published"


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, name="report_status", native_enum=True),
        nullable=False,
        default=ReportStatus.draft_generated,
    )
    draft_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    final_pdf_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    final_pdf_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    draft_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    final_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ReportSectionSummary(Base):
    __tablename__ = "report_section_summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    section_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("checklist_sections.id", ondelete="SET NULL"), nullable=True
    )
    chapter_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    updated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ReportFinding(Base):
    __tablename__ = "report_findings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("checklist_questions.id", ondelete="RESTRICT"), nullable=False
    )
    answer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessment_answers.id", ondelete="CASCADE"), nullable=False
    )
    priority: Mapped[PriorityLevel] = mapped_column(
        Enum(PriorityLevel, name="priority_level", native_enum=True, create_constraint=False), nullable=False
    )
    finding_text: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ReportReviewEvent(Base):
    __tablename__ = "report_review_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    event_type: Mapped[ReportEventType] = mapped_column(
        Enum(ReportEventType, name="report_event_type", native_enum=True), nullable=False
    )
    event_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
