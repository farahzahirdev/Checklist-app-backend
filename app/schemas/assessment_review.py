"""Schemas for assessment review API."""
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class AnswerReviewCreate(BaseModel):
    """Schema for creating answer review."""
    suggestion_type: str = Field(..., description="Type of suggestion")
    suggestion_text: str = Field(..., min_length=10, description="Detailed suggestion text")
    reference_materials: Optional[str] = Field(None, description="Reference materials or links")
    is_action_required: bool = Field(False, description="Whether action is required from customer")
    priority_level: int = Field(1, ge=1, le=5, description="Priority level (1-5)")
    score_adjustment: Optional[int] = Field(None, description="Score adjustment in points")


class AnswerReviewUpdate(BaseModel):
    """Schema for updating answer review."""
    suggestion_type: Optional[str] = Field(None, description="Type of suggestion")
    suggestion_text: Optional[str] = Field(None, min_length=10, description="Updated suggestion text")
    reference_materials: Optional[str] = Field(None, description="Updated reference materials")
    is_action_required: Optional[bool] = Field(None, description="Updated action requirement")
    priority_level: Optional[int] = Field(None, ge=1, le=5, description="Updated priority level")
    score_adjustment: Optional[int] = Field(None, description="Updated score adjustment")


class AnswerReviewResponse(BaseModel):
    """Schema for answer review response."""
    id: UUID
    assessment_review_id: UUID
    answer_id: UUID
    reviewer_id: Optional[UUID]
    suggestion_type: str
    suggestion_text: str
    reference_materials: Optional[str]
    is_action_required: bool
    priority_level: int
    score_adjustment: Optional[int]
    created_at: datetime
    updated_at: datetime
    
    # Additional fields for context
    question_text: Optional[str] = None
    question_code: Optional[str] = None
    customer_answer: Optional[str] = None
    customer_score: Optional[int] = None
    section_name: Optional[str] = None

    model_config = {"from_attributes": True}


class AssessmentReviewCreate(BaseModel):
    """Schema for creating assessment review."""
    overall_score: Optional[int] = Field(None, ge=0, description="Overall assessment score")
    max_score: Optional[int] = Field(None, ge=0, description="Maximum possible score")
    completion_percentage: Optional[float] = Field(None, ge=0, le=100, description="Completion percentage")
    summary_notes: Optional[str] = Field(None, description="Overall summary notes")
    strengths: Optional[str] = Field(None, description="Identified strengths")
    improvement_areas: Optional[str] = Field(None, description="Areas needing improvement")
    recommendations: Optional[str] = Field(None, description="Recommendations for customer")


class AssessmentReviewUpdate(BaseModel):
    """Schema for updating assessment review."""
    status: Optional[str] = Field(None, description="Review status")
    overall_score: Optional[int] = Field(None, ge=0, description="Updated overall score")
    max_score: Optional[int] = Field(None, ge=0, description="Updated max score")
    completion_percentage: Optional[float] = Field(None, ge=0, le=100, description="Updated completion percentage")
    summary_notes: Optional[str] = Field(None, description="Updated summary notes")
    strengths: Optional[str] = Field(None, description="Updated strengths")
    improvement_areas: Optional[str] = Field(None, description="Updated improvement areas")
    recommendations: Optional[str] = Field(None, description="Updated recommendations")


class AssessmentReviewResponse(BaseModel):
    """Schema for assessment review response."""
    id: UUID
    assessment_id: UUID
    reviewer_id: Optional[UUID]
    status: str
    overall_score: Optional[int]
    max_score: Optional[int]
    completion_percentage: Optional[float]
    summary_notes: Optional[str]
    strengths: Optional[str]
    improvement_areas: Optional[str]
    recommendations: Optional[str]
    reviewed_at: Optional[datetime]
    submitted_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    # Additional context
    customer_email: Optional[str] = None
    customer_name: Optional[str] = None
    checklist_title: Optional[str] = None
    checklist_version: Optional[str] = None
    assessment_status: Optional[str] = None
    submitted_at: Optional[datetime] = None
    answer_reviews_count: int = 0
    action_required_count: int = 0

    model_config = {"from_attributes": True}


class AnswerWithReview(BaseModel):
    """Schema for answer with its review."""
    answer_id: UUID
    question_id: UUID
    question_code: str
    question_text: str
    section_code: str
    section_name: str
    customer_answer: str
    customer_score: int
    weighted_priority: Optional[str]
    note_text: Optional[str]
    answered_at: datetime
    
    # Review information
    review: Optional[AnswerReviewResponse] = None
    has_review: bool = False
    is_action_required: bool = False
    review_priority: int = 0


class AssessmentAnswerListResponse(BaseModel):
    """Schema for assessment answers list."""
    assessment_id: UUID
    customer_email: str
    customer_name: str
    checklist_title: str
    checklist_version: str
    assessment_status: str
    submitted_at: Optional[datetime]
    
    # Answers with reviews
    answers: List[AnswerWithReview]
    total_answers: int
    reviewed_answers: int
    action_required_answers: int
    
    # Summary statistics
    average_score: float
    completion_percentage: float
    
    generated_at: datetime


class ReviewSummary(BaseModel):
    """Schema for review summary statistics."""
    total_assessments_pending_review: int
    total_assessments_in_progress: int
    total_assessments_completed: int
    total_answer_reviews: int
    total_action_required: int
    average_review_time_hours: Optional[float]
    recent_reviews: List[AssessmentReviewResponse]

    model_config = {"from_attributes": True}


class BulkAnswerReviewCreate(BaseModel):
    """Schema for bulk answer review creation."""
    answer_reviews: List[AnswerReviewCreate]
    assessment_notes: Optional[str] = Field(None, description="Overall assessment notes")


class BulkAnswerReviewResponse(BaseModel):
    """Schema for bulk answer review response."""
    success_count: int
    failure_count: int
    results: List["BulkAnswerReviewResult"]
    assessment_review_id: Optional[UUID]


class BulkAnswerReviewResult(BaseModel):
    """Result of individual bulk answer review operation."""
    answer_id: UUID
    success: bool
    message: str
    review_id: Optional[UUID] = None


class ReviewAnalytics(BaseModel):
    """Schema for review analytics."""
    total_reviews_completed: int
    average_review_score: float
    most_common_suggestion_types: List[dict]
    average_suggestions_per_assessment: float
    action_required_rate: float
    reviewer_performance: List[dict]
    monthly_review_trends: List[dict]
    generated_at: datetime


# Forward references
BulkAnswerReviewResponse.model_rebuild()
