from datetime import date, datetime
from enum import StrEnum
import uuid

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ChecklistStatus(StrEnum):
    draft = "draft"
    published = "published"
    archived = "archived"

    @classmethod
    def to_id(cls, status: "ChecklistStatus | str") -> int:
        value = cls(status)
        mapping = {cls.draft: 1, cls.published: 2, cls.archived: 3}
        return mapping[value]

    @classmethod
    def from_id(cls, status_code_id: int | None) -> "ChecklistStatus | None":
        mapping = {1: cls.draft, 2: cls.published, 3: cls.archived}
        return mapping.get(status_code_id)


class SeverityLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"

    @classmethod
    def to_id(cls, severity: "SeverityLevel | str") -> int:
        value = cls(severity)
        mapping = {cls.low: 1, cls.medium: 2, cls.high: 3}
        return mapping[value]

    @classmethod
    def from_id(cls, severity_code_id: int | None) -> "SeverityLevel | None":
        mapping = {1: cls.low, 2: cls.medium, 3: cls.high}
        return mapping.get(severity_code_id)


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
    # Removed unique constraint on (checklist_type_id, version)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    checklist_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("checklist_types.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status_code_id: Mapped[int | None] = mapped_column(
        SmallInteger,
        ForeignKey("checklist_status_codes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    updated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    @property
    def status(self) -> ChecklistStatus | None:
        return ChecklistStatus.from_id(self.status_code_id)

    @status.setter
    def status(self, value: ChecklistStatus | str | None) -> None:
        self.status_code_id = None if value is None else ChecklistStatus.to_id(value)


class ChecklistSection(Base):
    __tablename__ = "checklist_sections"
    __table_args__ = (
        UniqueConstraint("checklist_id", "section_code", name="uq_sections_checklist_code"),
        UniqueConstraint("checklist_id", "display_order", name="uq_sections_checklist_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    checklist_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("checklists.id", ondelete="CASCADE"), nullable=False)
    section_code: Mapped[str] = mapped_column(String(100), nullable=False)
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
    parent_question_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("checklist_questions.id", ondelete="CASCADE"),
        nullable=True,
    )
    question_code: Mapped[str] = mapped_column(String(120), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    answer_logic: Mapped[str] = mapped_column(String(40), nullable=False, default="answer_only")
    severity_code_id: Mapped[int | None] = mapped_column(
        SmallInteger,
        ForeignKey("severity_codes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    report_domain: Mapped[str | None] = mapped_column(String(120), nullable=True)
    report_chapter: Mapped[str | None] = mapped_column(String(120), nullable=True)
    illustrative_image_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media.id", ondelete="SET NULL"), nullable=True
    )
    note_for_user: Mapped[str | None] = mapped_column(Text, nullable=True)
    note_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    evidence_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    parent_question: Mapped["ChecklistQuestion | None"] = relationship(
        "ChecklistQuestion",
        remote_side="ChecklistQuestion.id",
        back_populates="sub_questions",
    )
    sub_questions: Mapped[list["ChecklistQuestion"]] = relationship(
        "ChecklistQuestion",
        back_populates="parent_question",
        cascade="all, delete-orphan",
    )
    answer_options: Mapped[list["ChecklistQuestionAnswerOption"]] = relationship(
        "ChecklistQuestionAnswerOption",
        back_populates="question",
        cascade="all, delete-orphan",
    )
    illustrative_image: Mapped["Media | None"] = relationship(
        "Media",
        foreign_keys=[illustrative_image_id],
    )

    @property
    def severity(self) -> SeverityLevel | None:
        return SeverityLevel.from_id(self.severity_code_id)

    @severity.setter
    def severity(self, value: SeverityLevel | str | None) -> None:
        self.severity_code_id = None if value is None else SeverityLevel.to_id(value)


class ChecklistQuestionAnswerOption(Base):
    __tablename__ = "checklist_question_answer_options"
    __table_args__ = (UniqueConstraint("question_id", "position", name="uq_question_answer_option_position"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("checklist_questions.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    choice_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    illustrative_image_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    question: Mapped["ChecklistQuestion"] = relationship(
        "ChecklistQuestion",
        back_populates="answer_options",
    )
    illustrative_image: Mapped["Media | None"] = relationship(
        "Media",
        foreign_keys=[illustrative_image_id],
    )


class ChecklistTranslation(Base):
    __tablename__ = "checklist_translations"
    __table_args__ = (UniqueConstraint("checklist_id", "language_id", name="uq_checklist_translations"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    checklist_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("checklists.id", ondelete="CASCADE"), nullable=False)
    language_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("languages.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ChecklistSectionTranslation(Base):
    __tablename__ = "checklist_section_translations"
    __table_args__ = (UniqueConstraint("section_id", "language_id", name="uq_section_translations"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("checklist_sections.id", ondelete="CASCADE"), nullable=False
    )
    language_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("languages.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ChecklistQuestionTranslation(Base):
    __tablename__ = "checklist_question_translations"
    __table_args__ = (UniqueConstraint("question_id", "language_id", name="uq_question_translations"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("checklist_questions.id", ondelete="CASCADE"), nullable=False
    )
    language_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("languages.id", ondelete="RESTRICT"),
        nullable=False,
    )
    paragraph_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_implementation: Mapped[str | None] = mapped_column(Text, nullable=True)
    guidance_score_4: Mapped[str | None] = mapped_column(Text, nullable=True)
    guidance_score_3: Mapped[str | None] = mapped_column(Text, nullable=True)
    guidance_score_2: Mapped[str | None] = mapped_column(Text, nullable=True)
    guidance_score_1: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
