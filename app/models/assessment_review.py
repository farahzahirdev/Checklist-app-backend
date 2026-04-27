"""Assessment Review models for admin feedback and suggestions."""
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Text, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base
from app.models.assessment import AssessmentStatus


class ReviewStatus(str):
    """Status of assessment review."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"


class SuggestionType(str):
    """Type of suggestion."""
    IMPROVEMENT = "improvement"
    REQUIRED_CHANGE = "required_change"
    BEST_PRACTICE = "best_practice"
    REFERENCE = "reference"
    CLARIFICATION = "clarification"


class AssessmentReview(Base):
    """Overall assessment review by admin."""
    __tablename__ = "assessment_reviews"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    assessment_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), 
        ForeignKey("assessments.id", ondelete="CASCADE"), 
        nullable=False,
        unique=True
    )
    reviewer_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True
    )
    status: Mapped[str] = mapped_column(
        SQLEnum('pending', 'in_progress', 'completed', 'rejected', name="review_status", native_enum=True),
        nullable=False,
        default=ReviewStatus.PENDING,
    )
    overall_score: Mapped[int | None] = mapped_column(nullable=True)
    max_score: Mapped[int | None] = mapped_column(nullable=True)
    completion_percentage: Mapped[float | None] = mapped_column(nullable=True)
    summary_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    strengths: Mapped[str | None] = mapped_column(Text, nullable=True)
    improvement_areas: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendations: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AnswerReview(Base):
    """Review and suggestions for specific assessment answers."""
    __tablename__ = "answer_reviews"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    assessment_review_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), 
        ForeignKey("assessment_reviews.id", ondelete="CASCADE"), 
        nullable=False
    )
    answer_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), 
        ForeignKey("assessment_answers.id", ondelete="CASCADE"), 
        nullable=False,
        unique=True
    )
    reviewer_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True
    )
    suggestion_type: Mapped[str] = mapped_column(
        SQLEnum(SuggestionType, name="suggestion_type", native_enum=True),
        nullable=False,
        default=SuggestionType.IMPROVEMENT,
    )
    suggestion_text: Mapped[str] = mapped_column(Text, nullable=False)
    reference_materials: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_action_required: Mapped[bool] = mapped_column(nullable=False, default=False)
    priority_level: Mapped[int] = mapped_column(nullable=False, default=1)  # 1-5 scale
    score_adjustment: Mapped[int | None] = mapped_column(nullable=True)  # +/- points
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ReviewHistory(Base):
    """History of review changes and actions."""
    __tablename__ = "review_history"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    assessment_review_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), 
        ForeignKey("assessment_reviews.id", ondelete="CASCADE"), 
        nullable=False
    )
    reviewer_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True
    )
    action_type: Mapped[str] = mapped_column(nullable=False)  # created, updated, submitted, etc.
    description: Mapped[str] = mapped_column(Text, nullable=False)
    previous_values: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    new_values: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
