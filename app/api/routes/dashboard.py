from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_roles
from app.db.session import get_db
from app.models.user import UserRole
from app.schemas.dashboard import (
    AdminActivityItemResponse,
    AdminAssessmentDistributionResponse,
    AdminAwaitingReviewItemResponse,
    AdminDashboardResponse,
    AdminRetentionStatusResponse,
    AdminSystemHealthResponse,
    AuditorDashboardResponse,
    CustomerDashboardResponse,
)
from app.services.dashboard import (
    get_admin_activity_feed,
    get_admin_assessment_distribution,
    get_admin_awaiting_review,
    get_admin_dashboard,
    get_admin_retention_status,
    get_admin_system_health,
    get_auditor_dashboard,
    get_customer_dashboard,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/admin",
    response_model=AdminDashboardResponse,
    summary="Admin Dashboard Summary",
    description="Admin-only endpoint returning top KPI cards for users, checklists, assessments, reports, and payments.",
)
def admin_dashboard(
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminDashboardResponse:
    return get_admin_dashboard(db)


@router.get(
    "/admin/awaiting-review",
    response_model=list[AdminAwaitingReviewItemResponse],
    summary="Admin Awaiting Review List",
    description="Admin-only endpoint returning latest submitted assessments waiting for review triage.",
)
def admin_awaiting_review(
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> list[AdminAwaitingReviewItemResponse]:
    return get_admin_awaiting_review(db)


@router.get(
    "/admin/activity",
    response_model=list[AdminActivityItemResponse],
    summary="Admin Activity Feed",
    description="Admin-only endpoint returning recent system events from audit logs, report workflow events, and successful payments.",
)
def admin_activity(
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> list[AdminActivityItemResponse]:
    return get_admin_activity_feed(db)


@router.get(
    "/admin/distribution",
    response_model=AdminAssessmentDistributionResponse,
    summary="Admin Assessment Distribution",
    description="Admin-only endpoint returning assessment lifecycle distribution counters.",
)
def admin_distribution(
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminAssessmentDistributionResponse:
    return get_admin_assessment_distribution(db)


@router.get(
    "/admin/retention",
    response_model=AdminRetentionStatusResponse,
    summary="Admin Retention And Deletion",
    description="Admin-only endpoint returning retention purge queue summary and next eligible items.",
)
def admin_retention(
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminRetentionStatusResponse:
    return get_admin_retention_status(db)


@router.get(
    "/admin/system-health",
    response_model=AdminSystemHealthResponse,
    summary="Admin System Health",
    description="Admin-only endpoint returning lightweight status indicators for payment, storage, and reporting subsystems.",
)
def admin_system_health(
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminSystemHealthResponse:
    return get_admin_system_health(db)


@router.get(
    "/auditor",
    response_model=AuditorDashboardResponse,
    summary="Auditor Dashboard Summary",
    description="Auditor and admin endpoint returning report queue counters and findings totals.",
)
def auditor_dashboard(
    _auditor=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> AuditorDashboardResponse:
    return get_auditor_dashboard(db)


@router.get(
    "/customer",
    response_model=CustomerDashboardResponse,
    summary="Customer Dashboard Summary",
    description="Customer endpoint returning purchase coverage, assessment activity, and latest report status.",
)
def customer_dashboard(
    customer=Depends(require_roles(UserRole.customer)),
    db: Session = Depends(get_db),
) -> CustomerDashboardResponse:
    return get_customer_dashboard(db, user_id=customer.id)
