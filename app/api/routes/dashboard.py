from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_roles
from app.db.session import get_db
from app.models.user import UserRole
from app.schemas.dashboard import AdminDashboardResponse, AuditorDashboardResponse, CustomerDashboardResponse
from app.services.dashboard import get_admin_dashboard, get_auditor_dashboard, get_customer_dashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/admin",
    response_model=AdminDashboardResponse,
    summary="Admin Dashboard Summary",
    description="Returns admin KPIs for users, checklists, payments, assessments, and report publication progress.",
)
def admin_dashboard(
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminDashboardResponse:
    return get_admin_dashboard(db)


@router.get(
    "/auditor",
    response_model=AuditorDashboardResponse,
    summary="Auditor Dashboard Summary",
    description="Returns auditor-focused report and findings queue counters.",
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
    description="Returns customer checklist purchase coverage, assessment activity, and latest report status.",
)
def customer_dashboard(
    customer=Depends(require_roles(UserRole.customer)),
    db: Session = Depends(get_db),
) -> CustomerDashboardResponse:
    return get_customer_dashboard(db, user_id=customer.id)
