from datetime import datetime

from pydantic import BaseModel

from app.models.report import ReportStatus


class AdminDashboardResponse(BaseModel):
    users_total: int
    customers_total: int
    checklists_published: int
    assessments_submitted: int
    reports_published: int
    payments_succeeded: int
    generated_at: datetime


class AuditorDashboardResponse(BaseModel):
    reports_under_review: int
    reports_changes_requested: int
    draft_reports_waiting: int
    findings_total: int
    generated_at: datetime


class CustomerDashboardResponse(BaseModel):
    paid_checklists_count: int
    active_assessments_count: int
    submitted_assessments_count: int
    latest_report_status: ReportStatus | None = None
    generated_at: datetime
