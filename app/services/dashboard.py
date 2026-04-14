from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.models.assessment import Assessment, AssessmentStatus
from app.models.checklist import Checklist, ChecklistStatus
from app.models.payment import Payment, PaymentStatus
from app.models.report import Report, ReportFinding, ReportStatus
from app.models.user import User, UserRole
from app.schemas.dashboard import AdminDashboardResponse, AuditorDashboardResponse, CustomerDashboardResponse


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_admin_dashboard(db: Session) -> AdminDashboardResponse:
    users_total = db.scalar(select(func.count(User.id))) or 0
    customers_total = db.scalar(select(func.count(User.id)).where(User.role == UserRole.customer)) or 0
    checklists_published = db.scalar(select(func.count(Checklist.id)).where(Checklist.status == ChecklistStatus.published)) or 0
    assessments_submitted = (
        db.scalar(select(func.count(Assessment.id)).where(Assessment.status == AssessmentStatus.submitted)) or 0
    )
    reports_published = db.scalar(select(func.count(Report.id)).where(Report.status == ReportStatus.published)) or 0
    payments_succeeded = db.scalar(select(func.count(Payment.id)).where(Payment.status == PaymentStatus.succeeded)) or 0

    return AdminDashboardResponse(
        users_total=users_total,
        customers_total=customers_total,
        checklists_published=checklists_published,
        assessments_submitted=assessments_submitted,
        reports_published=reports_published,
        payments_succeeded=payments_succeeded,
        generated_at=_now(),
    )


def get_auditor_dashboard(db: Session) -> AuditorDashboardResponse:
    reports_under_review = db.scalar(select(func.count(Report.id)).where(Report.status == ReportStatus.under_review)) or 0
    reports_changes_requested = (
        db.scalar(select(func.count(Report.id)).where(Report.status == ReportStatus.changes_requested)) or 0
    )
    draft_reports_waiting = db.scalar(select(func.count(Report.id)).where(Report.status == ReportStatus.draft_generated)) or 0
    findings_total = db.scalar(select(func.count(ReportFinding.id))) or 0

    return AuditorDashboardResponse(
        reports_under_review=reports_under_review,
        reports_changes_requested=reports_changes_requested,
        draft_reports_waiting=draft_reports_waiting,
        findings_total=findings_total,
        generated_at=_now(),
    )


def get_customer_dashboard(db: Session, *, user_id: UUID) -> CustomerDashboardResponse:
    paid_checklists_count = (
        db.scalar(
            select(func.count(distinct(Payment.checklist_id))).where(
                Payment.user_id == user_id,
                Payment.status == PaymentStatus.succeeded,
                Payment.checklist_id.is_not(None),
            )
        )
        or 0
    )
    active_assessments_count = (
        db.scalar(
            select(func.count(Assessment.id)).where(
                Assessment.user_id == user_id,
                Assessment.status.in_([AssessmentStatus.not_started, AssessmentStatus.in_progress]),
            )
        )
        or 0
    )
    submitted_assessments_count = (
        db.scalar(
            select(func.count(Assessment.id)).where(
                Assessment.user_id == user_id,
                Assessment.status == AssessmentStatus.submitted,
            )
        )
        or 0
    )

    latest_report_status = db.scalar(
        select(Report.status)
        .join(Assessment, Assessment.id == Report.assessment_id)
        .where(Assessment.user_id == user_id)
        .order_by(Report.updated_at.desc())
        .limit(1)
    )

    return CustomerDashboardResponse(
        paid_checklists_count=paid_checklists_count,
        active_assessments_count=active_assessments_count,
        submitted_assessments_count=submitted_assessments_count,
        latest_report_status=latest_report_status,
        generated_at=_now(),
    )
