from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.assessment import PriorityLevel
from app.models.report import ReportStatus


class ReportSummaryItem(BaseModel):
    id: UUID
    section_id: UUID | None = None
    chapter_code: str | None = None
    summary_text: str
    created_at: datetime
    updated_at: datetime


class ReportFindingItem(BaseModel):
    id: UUID
    question_id: UUID
    answer_id: UUID
    priority: PriorityLevel
    finding_text: str
    recommendation_text: str | None = None
    created_at: datetime


class ReportResponse(BaseModel):
    id: UUID
    assessment_id: UUID
    status: ReportStatus
    draft_generated_at: datetime | None = None
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    approved_by: UUID | None = None
    approved_at: datetime | None = None
    final_pdf_storage_key: str | None = None
    final_pdf_published_at: datetime | None = None
    findings_count: int
    summaries_count: int


class GenerateDraftReportRequest(BaseModel):
    assessment_id: UUID


class ReviewActionRequest(BaseModel):
    note: str | None = None


class PublishReportRequest(BaseModel):
    final_pdf_storage_key: str = Field(min_length=1, max_length=512)


class UpsertReportSummaryRequest(BaseModel):
    section_id: UUID | None = None
    chapter_code: str | None = Field(default=None, max_length=120)
    summary_text: str = Field(min_length=10, max_length=5000)




class CustomerReportDataResponse(BaseModel):
    """Comprehensive report data for customer-facing PDF generation"""
    report_id: UUID
    assessment_id: UUID
    customer_name: str
    customer_email: str
    checklist_title: str
    assessment_date: datetime
    report_status: ReportStatus
    
    # Score data
    overall_score: float
    max_possible_score: int
    completion_percentage: float
    
    # Section scores for radar chart
    section_scores: list[dict] = Field(description="List of {section_name, score, max_score, percentage}")
    
    # Chapter overview
    chapter_data: list[dict] = Field(description="List of {chapter_code, title, score, findings_count, recommendations}")
    
    # Findings (nonconformities/weak points)
    findings: list[dict] = Field(description="List of {question_text, answer, priority, recommendation}")
    
    # Admin summaries
    section_summaries: list[dict] = Field(description="Admin-written section summaries")
    
    # Public suggestions
    public_suggestions: list[dict] = Field(description="Public admin suggestions for customer")
    
    # Metadata
    generated_at: datetime
    approved_at: datetime | None = None
    published_at: datetime | None = None
