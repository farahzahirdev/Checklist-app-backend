from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.report import ReportStatus


class AdminDashboardResponse(BaseModel):
    users_total: int
    customers_total: int
    checklists_published: int
    assessments_submitted: int
    reports_published: int
    payments_succeeded: int
    total_assessments: int
    pending_review: int
    expired_assessments: int
    generated_at: datetime


class AdminAwaitingReviewItemResponse(BaseModel):
    assessment_id: UUID
    customer_email: str
    checklist_id: UUID
    checklist_label: str
    submitted_at: datetime | None = None
    report_id: UUID | None = None
    report_status: ReportStatus | None = None


class AdminActivityItemResponse(BaseModel):
    occurred_at: datetime
    source: str
    action: str
    entity_type: str
    entity_id: UUID | None = None
    actor_user_id: UUID | None = None
    note: str | None = None


class AdminAssessmentDistributionResponse(BaseModel):
    ready_to_start: int
    in_progress: int
    waiting_for_review: int
    published: int
    expired: int
    generated_at: datetime


class AdminRetentionQueueItemResponse(BaseModel):
    entity_type: str
    entity_id: UUID
    reason: str
    eligible_at: datetime


class AdminRetentionStatusResponse(BaseModel):
    pending_purge_count: int
    recent_purged_count: int
    items: list[AdminRetentionQueueItemResponse]
    generated_at: datetime


class AdminSystemHealthResponse(BaseModel):
    payments_status: str
    storage_status: str
    reports_status: str
    generated_at: datetime


class AuditorDashboardResponse(BaseModel):
    reports_under_review: int
    reports_changes_requested: int
    draft_reports_waiting: int
    findings_total: int
    users_total: int | None = None
    checklists_published: int | None = None
    assessments_submitted: int | None = None
    total_assessments: int | None = None
    generated_at: datetime


class CustomerDashboardResponse(BaseModel):
    paid_checklists_count: int
    active_assessments_count: int
    submitted_assessments_count: int
    latest_report_status: ReportStatus | None = None
    generated_at: datetime
