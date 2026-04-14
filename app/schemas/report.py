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
    summary_text: str = Field(min_length=1)
