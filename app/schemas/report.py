from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.assessment import PriorityLevel
from app.models.report import ReportStatus


class ReportSummaryItem(BaseModel):
    id: UUID | None = None
    report_id: UUID | None = None
    section_id: UUID | None = None
    section_code: str | None = None
    section_title: str | None = None
    chapter_code: str | None = None
    summary_text: str | None = None
    score: int | None = None
    max_score: int | None = None
    percentage: float | None = None
    question_count: int | None = None
    answered_question_count: int | None = None
    created_by: UUID | None = None
    updated_by: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


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
    report_code: str | None = None
    company_id: UUID | None = None
    company_name: str | None = None
    company_website: str | None = None
    company_industry: str | None = None
    company_size: str | None = None
    company_region: str | None = None
    company_country: str | None = None
    company_description: str | None = None
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
    section_overviews: list[ReportSummaryItem] = Field(default_factory=list)


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


class ReportQuestionScoreItem(BaseModel):
    question_id: UUID
    question_code: str
    question_title: str
    report_domain: str | None = None
    score: int
    max_score: int
    percentage: float


class ReportSectionScoreItem(BaseModel):
    section_id: UUID
    section_code: str
    section_title: str
    report_domain: str | None = None
    score: int
    max_score: int
    percentage: float
    question_count: int
    answered_question_count: int
    question_scores: list[ReportQuestionScoreItem] = Field(default_factory=list)


class ReportScoreDistributionItem(BaseModel):
    score: int
    count: int
    percentage: float



class CustomerReportDataResponse(BaseModel):
    """Comprehensive report data for customer-facing PDF generation"""
    report_id: str
    report_uuid: UUID
    assessment_id: UUID
    customer_name: str
    customer_email: str
    company_name: str | None = None
    company_website: str | None = None
    company_industry: str | None = None
    company_size: str | None = None
    company_region: str | None = None
    company_country: str | None = None
    company_description: str | None = None
    checklist_title: str
    assessment_date: datetime
    report_status: ReportStatus
    
    # Score data
    overall_score: float
    max_possible_score: int
    total_score_percentage: float
    completion_percentage: float
    total_questions: int
    answered_questions: int
    standard_covered_all: bool
    question_score_distribution: list[ReportScoreDistributionItem] = Field(default_factory=list)
    
    # Section scores for radar chart
    section_scores: list[ReportSectionScoreItem] = Field(description="List of section score summaries with per-question percentages")
    
    # Chapter overview
    chapter_data: list[dict] = Field(description="List of {chapter_code, title, score, findings_count, recommendations}")

    # Domain overview
    domain_data: list[dict] = Field(default_factory=list, description="List of {domain, title, score, max_score, percentage, question_count}")
    
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
