from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from starlette.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.middleware.i18n import I18nMiddleware
from app.services.i18n_service import get_current_language
from app.utils.i18n_messages import translate
from app.schemas.access import AccessWindowResponse
from app.schemas.admin_checklist import (
	AdminChecklistCreateRequest,
	AdminChecklistResponse,
	AdminChecklistUpdateRequest,
	AdminQuestionCreateRequest,
	AdminQuestionResponse,
	AdminSectionCreateRequest,
	AdminSectionResponse,
	EvidenceRuleResponse,
)
from app.schemas.assessment import (
	AssessmentAnswerResponse,
	AssessmentAnswerUpsertRequest,
	AssessmentSessionResponse,
	AssessmentSubmitResponse,
	StartAssessmentRequest,
)
from app.schemas.media import MediaResponse, MediaUploadResponse
from app.schemas.auth import (
	AuthResponse,
	AuthUserResponse,
	LoginRequest,
	MfaChallengeVerifyRequest,
	MfaVerifyRequest,
	MfaVerifyResponse,
	MfaSetupDetailsResponse,
	RegistrationRequest,
	RoleAssignment,
)
from app.schemas.common import MessageResponse
from app.schemas.db import AccessWindowCreate, AccessWindowRead, PaymentCreate, PaymentRead, UserCreate, UserRead
from app.schemas.health import HealthResponse
from app.schemas.payment import AdminPaymentStatusUpdateRequest, PaymentSetupRequest, PaymentSetupResponse, PaymentState, StripeWebhookAck
from app.schemas.rbac import (
	PermissionResponse,
	PermissionCheckResponse,
	RoleResponse,
	RoleDetailResponse,
	UserRoleResponse,
	UserPermissionResponse,
	MultiPermissionCheckResponse,
)
from app.schemas.report import (
	GenerateDraftReportRequest,
	PublishReportRequest,
	ReportFindingItem,
	ReportResponse,
	ReportSummaryItem,
	ReviewActionRequest,
	UpsertReportSummaryRequest,
)
from app.schemas.user_management import (
	AdminChangePasswordRequest,
	AdminProfileResponse,
	AdminProfileUpdateRequest,
	UserResponse,
	UserDetailResponse,
	UserListResponse,
	UserChangeRoleRequest,
	UserAssignPermissionsRequest,
	UserResetPermissionsRequest,
	UserPasswordResetRequest,
	UserPasswordResetResponse,
	CustomerResponse,
	CustomerDetailResponse,
	CustomerListResponse,
	CustomerBanRequest,
	CustomerActivateRequest,
	AdminRoleSwitchRequest,
	AdminRoleSwitchResponse,
	AdminRoleSwitchEndRequest,
	CustomerDashboardAccessRequest,
	DashboardDataResponse,
)

from app.schemas.support_ticket import (
	SupportTicketCreateRequest,
	SupportTicketListResponse,
	SupportTicketMessageResponse,
	SupportTicketReplyRequest,
	SupportTicketResponse,
	SupportTicketStatusUpdateRequest,
)

from app.schemas.password_reset import AdminPasswordResetRequest, AdminPasswordResetResponse
settings = get_settings()
configure_logging(settings.app_name)

app = FastAPI(
	title=settings.app_name,
	description=(
		"Backend API for checklist management, customer assessments, payments, "
		"and report review/publish workflow."
	),
	openapi_tags=[
		{"name": "health", "description": "Service health and uptime endpoints."},
		{
			"name": "auth",
			"description": "Account registration, login, MFA enrollment, MFA login challenge verification, and role assignment APIs.",
		},
		{"name": "payments", "description": "Stripe payment setup and webhook processing APIs."},
		{"name": "assessment", "description": "Assessment session start, answer save, and submit APIs."},
		{
			"name": "dashboard",
			"description": "Role-based dashboard APIs for admin, auditor, and customer experiences.",
		},
		{"name": "admin-checklists", "description": "Admin APIs for checklist, section, and question lifecycle management."},
		{"name": "reports", "description": "Admin report generation, review, approval, and publish workflow APIs."},
		{"name": "support", "description": "Customer support ticket submission and admin response APIs."},
		{"name": "media", "description": "Media file upload and management APIs for checklist questions and answer options."},
	],
	root_path="/api"
)

# Add CORS middleware to allow OPTIONS calls (for login and others)
app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],  # Adjust as needed for production
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

# Add I18n middleware for automatic language detection and context management
app.add_middleware(I18nMiddleware)

# Global exception handler for translating HTTPExceptions
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    try:
        lang_code = get_current_language()
    except:
        lang_code = "en"
    
    try:
        translated_detail = translate(exc.detail, lang_code)
    except:
        translated_detail = exc.detail
    
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": translated_detail}
    )

app.include_router(api_router, prefix=settings.api_v1_prefix)


def custom_openapi() -> dict:
	if app.openapi_schema:
		return app.openapi_schema

	openapi_schema = get_openapi(
		title=app.title,
		version="0.1.0",
		description="Checklist App API",
		routes=app.routes,
	)

	components = openapi_schema.setdefault("components", {}).setdefault("schemas", {})
	models = [
		MessageResponse,
		HealthResponse,
		AuthUserResponse,
		AuthResponse,
		LoginRequest,
		MfaChallengeVerifyRequest,
		RegistrationRequest,
		RoleAssignment,
		MfaVerifyRequest,
		MfaVerifyResponse,
		MfaSetupDetailsResponse,
		StartAssessmentRequest,
		AssessmentSessionResponse,
		AssessmentAnswerUpsertRequest,
		AssessmentAnswerResponse,
		AssessmentSubmitResponse,
		AdminChecklistCreateRequest,
		AdminChecklistUpdateRequest,
		AdminChecklistResponse,
		AdminSectionCreateRequest,
		AdminSectionResponse,
		AdminQuestionCreateRequest,
		EvidenceRuleResponse,
		AdminQuestionResponse,
		PaymentState,
		AdminPaymentStatusUpdateRequest,
		PaymentSetupRequest,
		PaymentSetupResponse,
		StripeWebhookAck,
		GenerateDraftReportRequest,
		ReviewActionRequest,
		PublishReportRequest,
		UpsertReportSummaryRequest,
		ReportSummaryItem,
		ReportFindingItem,
		ReportResponse,
		AccessWindowResponse,
		UserCreate,
		UserRead,
		PaymentCreate,
		PaymentRead,
		AccessWindowCreate,
		AccessWindowRead,
		PermissionResponse,
		RoleResponse,
		RoleDetailResponse,
		UserRoleResponse,
		UserPermissionResponse,
		PermissionCheckResponse,
		MultiPermissionCheckResponse,
		# User Management Schemas
		AdminProfileResponse,
		AdminProfileUpdateRequest,
		AdminChangePasswordRequest,
		UserResponse,
		UserDetailResponse,
		UserListResponse,
		UserChangeRoleRequest,
		UserAssignPermissionsRequest,
		UserResetPermissionsRequest,
		UserPasswordResetRequest,
		UserPasswordResetResponse,
		CustomerResponse,
		CustomerDetailResponse,
		CustomerListResponse,
		CustomerBanRequest,
		CustomerActivateRequest,
		AdminRoleSwitchRequest,
		AdminRoleSwitchResponse,
		AdminRoleSwitchEndRequest,
		CustomerDashboardAccessRequest,
		DashboardDataResponse,
		AdminPasswordResetRequest,
		AdminPasswordResetResponse,
		SupportTicketCreateRequest,
		SupportTicketListResponse,
		SupportTicketMessageResponse,
		SupportTicketReplyRequest,
		SupportTicketResponse,
		SupportTicketStatusUpdateRequest,
		# Media schemas
		MediaResponse,
		MediaUploadResponse,
	]

	for model in models:
		schema = model.model_json_schema(ref_template="#/components/schemas/{model}")
		for def_name, def_schema in schema.pop("$defs", {}).items():
			components.setdefault(def_name, def_schema)
		components.setdefault(model.__name__, schema)

	app.openapi_schema = openapi_schema
	return app.openapi_schema


app.openapi = custom_openapi

# # --- CLI commands for user creation ---
import typer
from app.db.session import SessionLocal
from app.services.user_management import UserManagementService
from app.core.security import hash_password

cli = typer.Typer()

@cli.command()
def createsuperuser(email: str, password: str, role: str = "admin"):
    """
    Create a superuser (admin or auditor) from the command line.
    Usage: python -m app.main createsuperuser --email user@example.com --password pass --role admin
    """
    if role not in ("admin", "auditor"):
        typer.echo("Role must be 'admin' or 'auditor'.")
        raise typer.Exit(code=1)
    db = SessionLocal()
    try:
        user = UserManagementService.create_user_with_role(
            db,
            email=email,
            password_hash=hash_password(password),
            role_code=role,
        )
        typer.echo(f"Created {role} user: {user.email}")
    finally:
        db.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        cli()
    else:
        pass
