from datetime import datetime
from enum import StrEnum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


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


class AnswerChoice(StrEnum):
    yes = "yes"
    partially = "partially"
    dont_know = "dont_know"
    no = "no"

    @classmethod
    def to_id(cls, choice: "AnswerChoice | str") -> int:
        value = cls(choice)
        mapping = {cls.yes: 1, cls.partially: 2, cls.dont_know: 3, cls.no: 4}
        return mapping[value]

    @classmethod
    def from_id(cls, answer_option_code_id: int | None) -> "AnswerChoice | None":
        mapping = {1: cls.yes, 2: cls.partially, 3: cls.dont_know, 4: cls.no}
        return mapping.get(answer_option_code_id)


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
    auditor_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_maturity_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
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

    # Relationships
    checklist: Mapped["Checklist"] = relationship("Checklist")
    answers: Mapped[list["AssessmentAnswer"]] = relationship(
        "AssessmentAnswer", back_populates="assessment", cascade="all, delete-orphan"
    )
    evidence_files: Mapped[list["AssessmentEvidenceFile"]] = relationship(
        "AssessmentEvidenceFile", back_populates="assessment", cascade="all, delete-orphan"
    )
    section_scores: Mapped[list["AssessmentSectionScore"]] = relationship(
        "AssessmentSectionScore", back_populates="assessment", cascade="all, delete-orphan"
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
    answer_option_code_id: Mapped[int | None] = mapped_column(
        SmallInteger,
        ForeignKey("answer_option_codes.id", ondelete="RESTRICT"),
        nullable=True,
    )
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

    # Relationships
    assessment: Mapped["Assessment"] = relationship("Assessment", back_populates="answers")
    question: Mapped["ChecklistQuestion"] = relationship("ChecklistQuestion")
    evidence_files: Mapped[list["AssessmentEvidenceFile"]] = relationship(
        "AssessmentEvidenceFile", back_populates="answer", cascade="all, delete-orphan"
    )

    @property
    def answer(self) -> AnswerChoice | None:
        return AnswerChoice.from_id(self.answer_option_code_id)

    @answer.setter
    def answer(self, value: AnswerChoice | str | None) -> None:
        self.answer_option_code_id = None if value is None else AnswerChoice.to_id(value)


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
    media_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media.id", ondelete="CASCADE"), nullable=False
    )
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    assessment: Mapped["Assessment"] = relationship("Assessment", back_populates="evidence_files")
    answer: Mapped["AssessmentAnswer | None"] = relationship("AssessmentAnswer", back_populates="evidence_files")
    question: Mapped["ChecklistQuestion"] = relationship("ChecklistQuestion")
    media: Mapped["Media"] = relationship("Media", foreign_keys=[media_id])


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

    # Relationships
    assessment: Mapped["Assessment"] = relationship("Assessment", back_populates="section_scores")
    section: Mapped["ChecklistSection"] = relationship("ChecklistSection")
