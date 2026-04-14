from datetime import date, datetime
from enum import StrEnum
import uuid

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChecklistStatus(StrEnum):
    draft = "draft"
    published = "published"
    archived = "archived"


class SeverityLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class QuestionScoreMode(StrEnum):
    answer_only = "answer_only"
    answer_with_adjustment = "answer_with_adjustment"


class ChecklistType(Base):
    __tablename__ = "checklist_types"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Checklist(Base):
    __tablename__ = "checklists"
    __table_args__ = (UniqueConstraint("checklist_type_id", "version", name="uq_checklists_type_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    checklist_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("checklist_types.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_code_id: Mapped[int | None] = mapped_column(
        SmallInteger,
        ForeignKey("checklist_status_codes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[ChecklistStatus] = mapped_column(
        Enum(ChecklistStatus, name="checklist_status", native_enum=True), nullable=False, default=ChecklistStatus.draft
    )
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    updated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ChecklistSection(Base):
    __tablename__ = "checklist_sections"
    __table_args__ = (
        UniqueConstraint("checklist_id", "section_code", name="uq_sections_checklist_code"),
        UniqueConstraint("checklist_id", "display_order", name="uq_sections_checklist_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    checklist_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("checklists.id", ondelete="CASCADE"), nullable=False)
    section_code: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ChecklistQuestion(Base):
    __tablename__ = "checklist_questions"
    __table_args__ = (
        UniqueConstraint("checklist_id", "question_code", name="uq_questions_checklist_code"),
        UniqueConstraint("section_id", "display_order", name="uq_questions_section_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    checklist_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("checklists.id", ondelete="CASCADE"), nullable=False)
    section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("checklist_sections.id", ondelete="CASCADE"), nullable=False
    )
    question_code: Mapped[str] = mapped_column(String(120), nullable=False)
    paragraph_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    legal_requirement: Mapped[str] = mapped_column(Text, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_implementation: Mapped[str | None] = mapped_column(Text, nullable=True)
    guidance_score_4: Mapped[str | None] = mapped_column(Text, nullable=True)
    guidance_score_3: Mapped[str | None] = mapped_column(Text, nullable=True)
    guidance_score_2: Mapped[str | None] = mapped_column(Text, nullable=True)
    guidance_score_1: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity_code_id: Mapped[int | None] = mapped_column(
        SmallInteger,
        ForeignKey("severity_codes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    expected_implementation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("expected_implementations.id", ondelete="SET NULL"),
        nullable=True,
    )
    severity: Mapped[SeverityLevel] = mapped_column(
        Enum(SeverityLevel, name="severity_level", native_enum=True), nullable=False
    )
    report_domain: Mapped[str | None] = mapped_column(String(120), nullable=True)
    report_chapter: Mapped[str | None] = mapped_column(String(120), nullable=True)
    illustrative_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    note_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    evidence_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    final_score_mode: Mapped[QuestionScoreMode] = mapped_column(
        Enum(QuestionScoreMode, name="question_score_mode", native_enum=True),
        nullable=False,
        default=QuestionScoreMode.answer_only,
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ChecklistTranslation(Base):
    __tablename__ = "checklist_translations"
    __table_args__ = (UniqueConstraint("checklist_id", "lang_code", name="uq_checklist_translations"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    checklist_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("checklists.id", ondelete="CASCADE"), nullable=False)
    lang_code: Mapped[str] = mapped_column(String(10), nullable=False)
    language_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("languages.id", ondelete="RESTRICT"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ChecklistSectionTranslation(Base):
    __tablename__ = "checklist_section_translations"
    __table_args__ = (UniqueConstraint("section_id", "lang_code", name="uq_section_translations"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("checklist_sections.id", ondelete="CASCADE"), nullable=False
    )
    lang_code: Mapped[str] = mapped_column(String(10), nullable=False)
    language_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("languages.id", ondelete="RESTRICT"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ChecklistQuestionTranslation(Base):
    __tablename__ = "checklist_question_translations"
    __table_args__ = (UniqueConstraint("question_id", "lang_code", name="uq_question_translations"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("checklist_questions.id", ondelete="CASCADE"), nullable=False
    )
    lang_code: Mapped[str] = mapped_column(String(10), nullable=False)
    language_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("languages.id", ondelete="RESTRICT"),
        nullable=True,
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_implementation: Mapped[str | None] = mapped_column(Text, nullable=True)
    guidance_score_4: Mapped[str | None] = mapped_column(Text, nullable=True)
    guidance_score_3: Mapped[str | None] = mapped_column(Text, nullable=True)
    guidance_score_2: Mapped[str | None] = mapped_column(Text, nullable=True)
    guidance_score_1: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
