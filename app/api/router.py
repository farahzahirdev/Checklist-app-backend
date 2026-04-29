from fastapi import APIRouter

from app.api.routes.admin_checklists import router as admin_checklists_router
from app.api.routes.assessment import router as assessment_router
from app.api.routes.assessment_review import router as assessment_review_router
from app.api.routes.auth import router as auth_router
from app.api.routes.customer_reports import router as customer_reports_router
from app.api.routes.audit_logs import router as audit_logs_router
from app.api.routes.customer_assessments import router as customer_assessments_router
from app.api.routes.customer_payments import router as customer_payments_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.health import router as health_router
from app.api.routes.media import router as media_router
from app.api.routes.payments import router as payments_router
from app.api.routes.rbac import router as rbac_router
from app.api.routes.user_management import router as user_management_router

from app.api.routes.report import router as report_router

from app.api.routes.access import router as access_router
from app.api.routes.checklists import router as customer_checklists_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(payments_router)
api_router.include_router(assessment_router)
api_router.include_router(assessment_review_router)
api_router.include_router(audit_logs_router)
api_router.include_router(customer_assessments_router)
api_router.include_router(customer_payments_router)
api_router.include_router(dashboard_router)
api_router.include_router(admin_checklists_router)
api_router.include_router(rbac_router)
api_router.include_router(user_management_router)
api_router.include_router(report_router)
api_router.include_router(access_router)
api_router.include_router(customer_checklists_router)
api_router.include_router(customer_reports_router)
api_router.include_router(media_router)
