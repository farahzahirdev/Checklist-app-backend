from datetime import datetime
from enum import StrEnum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.checklist import SeverityLevel


class AnswerChoice(StrEnum):
    yes = "yes"
    partially = "partially"
    dont_know = "dont_know"
    no = "no"


class PriorityLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class AssessmentStatus(StrEnum):
    not_started = "not_started"
    in_progress = "in_progress"
    submitted = "submitted"
    expired = "expired"
    closed = "closed"


class MalwareScanStatus(StrEnum):
    pending = "pending"
    clean = "clean"
    infected = "infected"
    failed = "failed"


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    checklist_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("checklists.id", ondelete="RESTRICT"), nullable=False)
    access_window_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("access_windows.id", ondelete="RESTRICT"), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[AssessmentStatus] = mapped_column(
        Enum(AssessmentStatus, name="assessment_status", native_enum=True),
        nullable=False,
        default=AssessmentStatus.not_started,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completion_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    retention_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AssessmentAnswer(Base):
    __tablename__ = "assessment_answers"
    __table_args__ = (UniqueConstraint("assessment_id", "question_id", name="uq_assessment_question_answer"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("checklist_questions.id", ondelete="RESTRICT"), nullable=False
    )
    answer: Mapped[AnswerChoice] = mapped_column(Enum(AnswerChoice, name="answer_choice", native_enum=True), nullable=False)
    answer_score: Mapped[int] = mapped_column(Integer, nullable=False)
    weighted_priority: Mapped[PriorityLevel | None] = mapped_column(
        Enum(PriorityLevel, name="priority_level", native_enum=True), nullable=True
    )
    note_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AssessmentEvidenceFile(Base):
    __tablename__ = "assessment_evidence_files"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False
    )
    answer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessment_answers.id", ondelete="SET NULL"), nullable=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("checklist_questions.id", ondelete="RESTRICT"), nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    scan_status: Mapped[MalwareScanStatus] = mapped_column(
        Enum(MalwareScanStatus, name="malware_scan_status", native_enum=True),
        nullable=False,
        default=MalwareScanStatus.pending,
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AssessmentSectionScore(Base):
    __tablename__ = "assessment_section_scores"
    __table_args__ = (UniqueConstraint("assessment_id", "section_id", name="uq_assessment_section_score"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("checklist_sections.id", ondelete="CASCADE"), nullable=False
    )
    avg_score: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    answered_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
