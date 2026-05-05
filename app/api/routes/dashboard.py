from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from uuid import UUID

from app.api.dependencies.auth import require_roles
from app.db.session import get_db
from app.models.user import UserRole
from app.utils.i18n import get_language_code
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
from app.schemas.customer_assessments import CustomerAssessmentDashboardResponse
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
    request: Request,
    company_id: UUID | None = None,
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminDashboardResponse:
    lang_code = get_language_code(request, db)
    return get_admin_dashboard(db, company_id=company_id, lang_code=lang_code)


@router.get(
    "/admin/awaiting-review",
    response_model=list[AdminAwaitingReviewItemResponse],
    summary="Admin Awaiting Review List",
    description="Admin-only endpoint returning latest submitted assessments waiting for review triage.",
)
def admin_awaiting_review(
    request: Request,
    company_id: UUID | None = None,
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> list[AdminAwaitingReviewItemResponse]:
    lang_code = get_language_code(request, db)
    return get_admin_awaiting_review(db, company_id=company_id, lang_code=lang_code)


@router.get(
    "/admin/activity",
    response_model=list[AdminActivityItemResponse],
    summary="Admin Activity Feed",
    description="Admin-only endpoint returning recent system events from audit logs, report workflow events, and successful payments.",
)
def admin_activity(
    request: Request,
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> list[AdminActivityItemResponse]:
    lang_code = get_language_code(request, db)
    return get_admin_activity_feed(db, lang_code=lang_code)


@router.get(
    "/admin/distribution",
    response_model=AdminAssessmentDistributionResponse,
    summary="Admin Assessment Distribution",
    description="Admin-only endpoint returning assessment lifecycle distribution counters.",
)
def admin_distribution(
    request: Request,
    company_id: UUID | None = None,
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminAssessmentDistributionResponse:
    lang_code = get_language_code(request, db)
    return get_admin_assessment_distribution(db, company_id=company_id, lang_code=lang_code)


@router.get(
    "/admin/retention",
    response_model=AdminRetentionStatusResponse,
    summary="Admin Retention And Deletion",
    description="Admin-only endpoint returning retention purge queue summary and next eligible items.",
)
def admin_retention(
    request: Request,
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminRetentionStatusResponse:
    lang_code = get_language_code(request, db)
    return get_admin_retention_status(db, lang_code=lang_code)


@router.get(
    "/admin/system-health",
    response_model=AdminSystemHealthResponse,
    summary="Admin System Health",
    description="Admin-only endpoint returning lightweight status indicators for payment, storage, and reporting subsystems.",
)
def admin_system_health(
    request: Request,
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminSystemHealthResponse:
    lang_code = get_language_code(request, db)
    return get_admin_system_health(db, lang_code=lang_code)


@router.get(
    "/auditor",
    response_model=AuditorDashboardResponse,
    summary="Auditor Dashboard Summary",
    description="Auditor and admin endpoint returning report queue counters and findings totals.",
)
def auditor_dashboard(
    request: Request,
    company_id: UUID | None = None,
    _auditor=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> AuditorDashboardResponse:
    lang_code = get_language_code(request, db)
    return get_auditor_dashboard(db, company_id=company_id, lang_code=lang_code)


@router.get(
    "/customer",
    response_model=CustomerDashboardResponse,
    summary="Customer Dashboard Summary",
    description="Customer endpoint returning purchase coverage, assessment activity, and latest report status.",
)
def customer_dashboard(
    request: Request,
    customer=Depends(require_roles(UserRole.customer)),
    db: Session = Depends(get_db),
) -> CustomerDashboardResponse:
    lang_code = get_language_code(request, db)
    return get_customer_dashboard(db, user_id=customer.id, lang_code=lang_code)


@router.get(
    "/customer/enhanced",
    response_model=CustomerAssessmentDashboardResponse,
    summary="Enhanced Customer Dashboard",
    description="Enhanced customer dashboard with detailed multi-assessment management capabilities.",
)
def customer_dashboard_enhanced(
    request: Request,
    customer=Depends(require_roles(UserRole.customer)),
    db: Session = Depends(get_db),
) -> CustomerAssessmentDashboardResponse:
    lang_code = get_language_code(request, db)
    from app.services.customer_assessments import get_customer_dashboard_enhanced
    return get_customer_dashboard_enhanced(db, user_id=customer.id, lang_code=lang_code)
