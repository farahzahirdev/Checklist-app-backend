from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import distinct, func, or_, select
from sqlalchemy.orm import Session

from app.models.assessment import Assessment, AssessmentStatus
from app.models.audit_log import AuditLog
from app.models.checklist import Checklist, ChecklistStatus
from app.models.payment import Payment, PaymentStatus
from app.models.report import Report, ReportFinding, ReportReviewEvent, ReportStatus
from app.models.user import User, UserRole
from app.schemas.dashboard import (
    AdminActivityItemResponse,
    AdminAssessmentDistributionResponse,
    AdminAwaitingReviewItemResponse,
    AdminDashboardResponse,
    AdminRetentionQueueItemResponse,
    AdminRetentionStatusResponse,
    AdminSystemHealthResponse,
    AuditorDashboardResponse,
    CustomerDashboardResponse,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_admin_dashboard(db: Session) -> AdminDashboardResponse:
    now = _now()
    users_total = db.scalar(select(func.count(User.id))) or 0
    customers_total = db.scalar(
        select(func.count(User.id)).where(User.role == UserRole.customer)
    ) or 0
    checklists_published = db.scalar(
        select(func.count(Checklist.id)).where(Checklist.status_code_id == ChecklistStatus.to_id(ChecklistStatus.published))
    ) or 0
    assessments_submitted = (
        db.scalar(select(func.count(Assessment.id)).where(Assessment.status == AssessmentStatus.submitted)) or 0
    )
    reports_published = db.scalar(select(func.count(Report.id)).where(Report.status == ReportStatus.published)) or 0
    payments_succeeded = db.scalar(
        select(func.count(Payment.id)).where(Payment.status == PaymentStatus.succeeded)
    ) or 0
    total_assessments = db.scalar(select(func.count(Assessment.id))) or 0
    pending_review = db.scalar(select(func.count(Assessment.id)).where(Assessment.status == AssessmentStatus.submitted)) or 0
    expired_assessments = db.scalar(
        select(func.count(Assessment.id)).where(
            or_(
                Assessment.status == AssessmentStatus.expired,
                Assessment.expires_at < now,
            )
        )
    ) or 0

    return AdminDashboardResponse(
        users_total=users_total,
        customers_total=customers_total,
        checklists_published=checklists_published,
        assessments_submitted=assessments_submitted,
        reports_published=reports_published,
        payments_succeeded=payments_succeeded,
        total_assessments=total_assessments,
        pending_review=pending_review,
        expired_assessments=expired_assessments,
        generated_at=now,
    )


def get_admin_awaiting_review(db: Session, *, limit: int = 10) -> list[AdminAwaitingReviewItemResponse]:
    rows = db.execute(
        select(Assessment, User.email, Checklist.description, Report.id, Report.status)
        .join(User, User.id == Assessment.user_id)
        .join(Checklist, Checklist.id == Assessment.checklist_id)
        .outerjoin(Report, Report.assessment_id == Assessment.id)
        .where(Assessment.status == AssessmentStatus.submitted)
        .order_by(Assessment.submitted_at.desc())
        .limit(limit)
    ).all()

    return [
        AdminAwaitingReviewItemResponse(
            assessment_id=assessment.id,
            customer_email=email,
            checklist_id=assessment.checklist_id,
            checklist_label=checklist_description or "Unnamed checklist",
            submitted_at=assessment.submitted_at,
            report_id=report_id,
            report_status=report_status,
        )
        for assessment, email, checklist_description, report_id, report_status in rows
    ]


def get_admin_activity_feed(db: Session, *, limit: int = 20) -> list[AdminActivityItemResponse]:
    audit_rows = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).all()
    review_rows = db.scalars(select(ReportReviewEvent).order_by(ReportReviewEvent.created_at.desc()).limit(limit)).all()
    payment_rows = db.scalars(
        select(Payment)
        .where(Payment.status == PaymentStatus.succeeded, Payment.paid_at.is_not(None))
        .order_by(Payment.paid_at.desc())
        .limit(limit)
    ).all()

    items: list[AdminActivityItemResponse] = []
    for row in audit_rows:
        items.append(
            AdminActivityItemResponse(
                occurred_at=row.created_at,
                source="audit_log",
                action=row.action.value,
                entity_type=row.target_entity,
                entity_id=row.target_id,
                actor_user_id=row.actor_user_id,
                note=None,
            )
        )

    for row in review_rows:
        items.append(
            AdminActivityItemResponse(
                occurred_at=row.created_at,
                source="report_review",
                action=row.event_type.value,
                entity_type="report",
                entity_id=row.report_id,
                actor_user_id=row.actor_user_id,
                note=row.event_note,
            )
        )

    for row in payment_rows:
        items.append(
            AdminActivityItemResponse(
                occurred_at=row.paid_at,
                source="payment",
                action="payment_succeeded",
                entity_type="payment",
                entity_id=row.id,
                actor_user_id=row.user_id,
                note=f"{row.amount_cents} {row.currency}",
            )
        )

    items.sort(key=lambda item: item.occurred_at, reverse=True)
    return items[:limit]


def get_admin_assessment_distribution(db: Session) -> AdminAssessmentDistributionResponse:
    ready_to_start = db.scalar(
        select(func.count(Assessment.id)).where(Assessment.status == AssessmentStatus.not_started)
    ) or 0
    in_progress = db.scalar(select(func.count(Assessment.id)).where(Assessment.status == AssessmentStatus.in_progress)) or 0
    waiting_for_review = db.scalar(select(func.count(Assessment.id)).where(Assessment.status == AssessmentStatus.submitted)) or 0
    published = db.scalar(select(func.count(Report.id)).where(Report.status == ReportStatus.published)) or 0
    expired = db.scalar(select(func.count(Assessment.id)).where(Assessment.status == AssessmentStatus.expired)) or 0

    return AdminAssessmentDistributionResponse(
        ready_to_start=ready_to_start,
        in_progress=in_progress,
        waiting_for_review=waiting_for_review,
        published=published,
        expired=expired,
        generated_at=_now(),
    )


def get_admin_retention_status(db: Session, *, limit: int = 10) -> AdminRetentionStatusResponse:
    now = _now()
    pending_assessment_rows = db.scalars(
        select(Assessment)
        .where(Assessment.retention_expires_at.is_not(None), Assessment.retention_expires_at <= now, Assessment.purged_at.is_(None))
        .order_by(Assessment.retention_expires_at.asc())
        .limit(limit)
    ).all()

    pending_report_rows = db.scalars(
        select(Report)
        .where(
            or_(
                Report.draft_deleted_at.is_not(None),
                Report.final_deleted_at.is_not(None),
            )
        )
        .order_by(Report.updated_at.desc())
        .limit(limit)
    ).all()

    items: list[AdminRetentionQueueItemResponse] = []
    for row in pending_assessment_rows:
        items.append(
            AdminRetentionQueueItemResponse(
                entity_type="assessment",
                entity_id=row.id,
                reason="retention_window_elapsed",
                eligible_at=row.retention_expires_at,
            )
        )

    for row in pending_report_rows:
        eligible_at = row.final_deleted_at or row.draft_deleted_at
        if eligible_at is None:
            continue
        items.append(
            AdminRetentionQueueItemResponse(
                entity_type="report",
                entity_id=row.id,
                reason="soft_deleted",
                eligible_at=eligible_at,
            )
        )

    items.sort(key=lambda item: item.eligible_at)
    items = items[:limit]

    pending_purge_count = len(items)
    recent_purged_count = db.scalar(
        select(func.count(Assessment.id)).where(Assessment.purged_at.is_not(None), Assessment.purged_at >= now.replace(hour=0, minute=0, second=0, microsecond=0))
    ) or 0

    return AdminRetentionStatusResponse(
        pending_purge_count=pending_purge_count,
        recent_purged_count=recent_purged_count,
        items=items,
        generated_at=now,
    )


def get_admin_system_health(db: Session) -> AdminSystemHealthResponse:
    day_ago = _now() - timedelta(days=1)
    total_recent_payments = db.scalar(
        select(func.count(Payment.id)).where(Payment.created_at >= day_ago)
    ) or 0
    failed_recent_payments = db.scalar(
        select(func.count(Payment.id)).where(
            Payment.created_at >= day_ago,
            Payment.status == PaymentStatus.failed,
        )
    ) or 0

    payments_status = "ok"
    if total_recent_payments > 0 and failed_recent_payments / total_recent_payments >= 0.3:
        payments_status = "degraded"

    reports_missing_pdf = db.scalar(
        select(func.count(Report.id)).where(Report.status == ReportStatus.published, Report.final_pdf_storage_key.is_(None))
    ) or 0
    reports_status = "ok" if reports_missing_pdf == 0 else "degraded"

    storage_status = "ok"

    return AdminSystemHealthResponse(
        payments_status=payments_status,
        storage_status=storage_status,
        reports_status=reports_status,
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
