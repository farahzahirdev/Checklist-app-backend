"""Enhanced schemas for customer multi-assessment management."""
from datetime import datetime
from uuid import UUID
from enum import StrEnum

from pydantic import BaseModel, Field

from app.models.assessment import AssessmentStatus, AnswerChoice, PriorityLevel
from app.models.checklist import ChecklistStatus


class AssessmentSummary(BaseModel):
    """Brief assessment summary for list views."""
    id: UUID
    checklist_id: UUID
    checklist_title: str
    checklist_type_code: str
    checklist_version: str
    status: AssessmentStatus
    completion_percent: float
    started_at: datetime | None = None
    submitted_at: datetime | None = None
    expires_at: datetime
    days_until_expiry: int
    has_report: bool = False
    report_status: str | None = None
    last_activity: datetime | None = None


class AssessmentDetail(BaseModel):
    """Detailed assessment information with progress tracking."""
    id: UUID
    checklist_id: UUID
    checklist_title: str
    checklist_type_code: str
    checklist_type_name: str
    checklist_version: str
    status: AssessmentStatus
    completion_percent: float
    started_at: datetime | None = None
    submitted_at: datetime | None = None
    expires_at: datetime
    days_until_expiry: int
    access_window_id: UUID
    total_questions: int
    answered_questions: int
    sections_completed: int
    total_sections: int
    estimated_time_remaining_minutes: int | None = None
    last_activity: datetime | None = None
    report_id: UUID | None = None
    report_status: str | None = None


class AssessmentProgress(BaseModel):
    """Progress tracking for an assessment."""
    assessment_id: UUID
    overall_completion: float
    sections: list["SectionProgress"]
    questions_answered: int
    total_questions: int
    time_spent_minutes: int
    estimated_time_remaining_minutes: int | None = None


class SectionProgress(BaseModel):
    """Progress for a specific section."""
    section_id: UUID
    section_code: str
    section_title: str
    display_order: int
    questions_answered: int
    total_questions: int
    completion_percent: float
    is_accessible: bool
    is_completed: bool


class QuestionSummary(BaseModel):
    """Summary of a question within assessment context."""
    question_id: UUID
    question_code: str
    question_text: str
    section_code: str
    section_title: str
    display_order: int
    is_answered: bool
    has_evidence: bool = False
    has_notes: bool = False
    is_mandatory: bool = False
    severity: str | None = None
    points: int


class AssessmentActivity(BaseModel):
    """Activity log for an assessment."""
    activity_id: UUID
    assessment_id: UUID
    activity_type: str
    description: str
    timestamp: datetime
    metadata: dict | None = None


class CustomerAssessmentListResponse(BaseModel):
    """Response for customer assessment list endpoint."""
    assessments: list[AssessmentSummary]
    total: int
    filters_applied: dict | None = None
    generated_at: datetime


class CustomerAssessmentDashboardResponse(BaseModel):
    """Enhanced customer dashboard with detailed assessment information."""
    summary: "DashboardSummary"
    active_assessments: list[AssessmentSummary]
    recent_submissions: list[AssessmentSummary]
    expiring_soon: list[AssessmentSummary]
    available_checklists: list["AvailableChecklist"]
    quick_actions: list["QuickAction"]
    generated_at: datetime


class DashboardSummary(BaseModel):
    """Summary statistics for customer dashboard."""
    total_purchased_checklists: int
    active_assessments_count: int
    submitted_assessments_count: int
    completed_assessments_count: int
    expired_assessments_count: int
    reports_available: int
    average_completion_time_days: float | None = None
    overall_completion_rate: float


class AvailableChecklist(BaseModel):
    """Checklist available for customer to start."""
    checklist_id: UUID
    title: str
    checklist_type_code: str
    checklist_type_name: str
    version: str
    description: str | None = None
    estimated_duration_minutes: int | None = None
    price_cents: int
    currency: str
    is_purchased: bool
    can_start: bool
    access_window_id: UUID | None = None


class QuickAction(BaseModel):
    """Quick action for customer dashboard."""
    action_id: str
    action_type: str
    label: str
    description: str
    assessment_id: UUID | None = None
    checklist_id: UUID | None = None
    is_enabled: bool = True
    priority: int = 0


class AssessmentActionRequest(BaseModel):
    """Request for assessment actions (pause, resume, extend, etc.)."""
    action: str = Field(..., description="Action to perform: pause, resume, extend, archive")
    reason: str | None = Field(None, description="Reason for the action")
    metadata: dict | None = Field(None, description="Additional metadata")


class AssessmentActionResponse(BaseModel):
    """Response for assessment action."""
    success: bool
    message: str
    assessment_id: UUID
    action_performed: str
    new_status: AssessmentStatus | None = None
    updated_expires_at: datetime | None = None


class BulkAssessmentRequest(BaseModel):
    """Request for bulk assessment operations."""
    assessment_ids: list[UUID]
    action: str = Field(..., description="Bulk action: extend, archive, delete_drafts")
    parameters: dict | None = Field(None, description="Action-specific parameters")


class BulkAssessmentResponse(BaseModel):
    """Response for bulk assessment operations."""
    success_count: int
    failure_count: int
    results: list["BulkActionResult"]
    summary: str


class BulkActionResult(BaseModel):
    """Result of individual bulk operation."""
    assessment_id: UUID
    success: bool
    message: str
    new_status: AssessmentStatus | None = None


class AssessmentAnalytics(BaseModel):
    """Analytics for customer assessment performance."""
    total_assessments: int
    completion_rate: float
    average_score: float | None = None
    average_time_to_completion_days: float | None = None
    most_active_checklist_type: str | None = None
    improvement_areas: list[str]
    strengths: list[str]
    monthly_activity: list["MonthlyActivity"]
    generated_at: datetime


class MonthlyActivity(BaseModel):
    """Monthly assessment activity."""
    month: str
    year: int
    assessments_started: int
    assessments_completed: int
    assessments_submitted: int


class AssessmentComparison(BaseModel):
    """Comparison between multiple assessments."""
    assessments: list[AssessmentSummary]
    comparison_metrics: dict[str, float]
    insights: list[str]
    recommendations: list[str]
    generated_at: datetime


# Update forward references
AssessmentProgress.model_rebuild()
CustomerAssessmentDashboardResponse.model_rebuild()
