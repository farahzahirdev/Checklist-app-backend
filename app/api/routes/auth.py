from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import UserRole
from app.schemas.auth import (
    AuthResponse,
    EmailVerificationConfirmRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MfaChallengeVerifyRequest,
    MfaSetupDetailsResponse,
    MfaVerifyRequest,
    ResetPasswordWithTokenRequest,
    RegistrationRequest,
    RoleAssignment,
)
from app.schemas.common import MessageResponse
from app.services.auth import (
    authenticate_user,
    confirm_email_verification,
    confirm_mfa_enrollment,
    issue_forgot_password_reset,
    issue_email_verification_request,
    issue_session_auth_response,
    register_user,
    reset_password_with_token,
    serialize_user,
    start_mfa_enrollment,
    update_user_role,
    verify_mfa_challenge,
)
from app.utils.i18n import get_language_code
from app.utils.i18n_messages import translate
from app.services.audit_log import create_audit_log

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=AuthResponse,
    summary="Register User",
    description="Creates a new customer account. Email, password, and company/organization name are required; industry, size, and region are optional.",
)
def register(request: RegistrationRequest, http_request: Request, db: Session = Depends(get_db),
) -> AuthResponse:
    
    lang_code = get_language_code(http_request, db)
    try:
        return register_user(
            db,
            email=request.email,
            password=request.password,
            full_name=request.full_name,
            username=request.username,
            company_name=request.company_name,
            job_title=request.job_title,
            department=request.department,
            company_industry=request.company_industry,
            company_size=request.company_size,
            company_region=request.company_region,
            lang_code=lang_code
        )
    except HTTPException as exc:
        exc.detail = translate(exc.detail, lang_code)
        raise


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Sign In",
    description=(
        "Authenticates user credentials. "
        "If MFA is enabled, this returns mfa_required=true and a short-lived challenge_token; "
        "client must call /auth/mfa/challenge/verify with a TOTP code to receive bearer token. "
        "If MFA is not enabled, this endpoint returns access_token directly."
    ),
)
def login(request: LoginRequest, http_request: Request, db: Session = Depends(get_db),
) -> AuthResponse:
    lang_code = get_language_code(http_request, db)
    try:
        result = authenticate_user(db, email=request.email, password=request.password, lang_code=lang_code)
        
        # Log successful login action
        create_audit_log(
            db=db,
            action="auth_login",
            target_entity="auth",
            actor_user_id=result.user.id,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent"),
            changes_summary=f"User {result.user.email} logged in",
            success=True
        )
        
        return result
    except HTTPException as exc:
        # Log failed login attempt
        try:
            # Try to get user by email for the audit log
            from app.models.user import User
            user = db.query(User).filter(User.email == request.email).first()
            
            create_audit_log(
                db=db,
                action="auth_login",
                target_entity="auth",
                actor_user_id=user.id if user else None,
                ip_address=http_request.client.host if http_request.client else None,
                user_agent=http_request.headers.get("user-agent"),
                changes_summary=f"Failed login attempt for {request.email}",
                success=False,
                error_message=exc.detail
            )
        except:
            # Don't let audit logging fail the login attempt
            pass
        
        exc.detail = translate(exc.detail, lang_code)
        raise


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request Password Reset",
    description="Issues a password reset token and sends an email if the account exists.",
)
def forgot_password(request: ForgotPasswordRequest, http_request: Request, db: Session = Depends(get_db)) -> MessageResponse:
    lang_code = get_language_code(http_request, db)
    frontend_base_url = (http_request.headers.get("origin") or str(http_request.base_url)).rstrip("/")
    issue_forgot_password_reset(
        db,
        email=request.email,
        lang_code=lang_code,
        production_base_url=frontend_base_url,
    )
    return MessageResponse(message=translate("password_reset_email_sent_if_exists", lang_code))


@router.post(
    "/email-verification/request",
    response_model=MessageResponse,
    summary="Request Email Verification",
    description="Requires bearer auth. Sends a bilingual verification email to the authenticated user.",
)
def request_email_verification(
    http_request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> MessageResponse:
    lang_code = get_language_code(http_request, db, current_user)
    frontend_base_url = (http_request.headers.get("origin") or str(http_request.base_url)).rstrip("/")
    issue_email_verification_request(
        db,
        user=current_user,
        lang_code=lang_code,
        production_base_url=frontend_base_url,
    )
    return MessageResponse(message=translate("verification_email_sent", lang_code))


@router.post(
    "/email-verification/confirm",
    response_model=AuthResponse,
    summary="Confirm Email Verification",
    description="Confirms a one-time email verification token.",
)
def confirm_email_verification_token(
    request: EmailVerificationConfirmRequest,
    http_request: Request,
    db: Session = Depends(get_db),

) -> AuthResponse:
    lang_code = get_language_code(http_request, db)
    return confirm_email_verification(db, token=request.token, lang_code=lang_code)


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset Password With Token",
    description="Resets account password using a valid password-reset token.",
)
def reset_password(request: ResetPasswordWithTokenRequest, http_request: Request, db: Session = Depends(get_db)) -> MessageResponse:
    lang_code = get_language_code(http_request, db)
    reset_password_with_token(
        db,
        token=request.token,
        new_password=request.new_password,
        confirm_password=request.confirm_password,
        lang_code=lang_code,
    )
    return MessageResponse(message=translate("password_changed", lang_code))


@router.post(
    "/mfa/challenge/verify",
    response_model=AuthResponse,
    summary="Verify MFA Login Challenge",
    description="Verifies login-time challenge_token plus TOTP code and returns the final bearer access token.",
)
def verify_login_mfa_challenge(request: MfaChallengeVerifyRequest, http_request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    lang_code = get_language_code(http_request, db)
    try:
        return verify_mfa_challenge(db, challenge_token=request.challenge_token, code=request.code, lang_code=lang_code)
    except HTTPException as exc:
        exc.detail = translate(exc.detail, lang_code)
        raise


@router.get(
    "/me",
    response_model=AuthResponse,
    summary="Get Current User",
    description="Validates bearer token and returns authenticated user profile and MFA status.",
)
def me(http_request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> AuthResponse:
    db.refresh(current_user)
    return issue_session_auth_response(db, user=current_user)


@router.post(
    "/refresh",
    response_model=AuthResponse,
    summary="Refresh Session",
    description="Validates the current bearer token and returns a renewed access token for active sessions.",
)
def refresh_session(
    http_request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> AuthResponse:
    db.refresh(current_user)
    return issue_session_auth_response(db, user=current_user)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout",
    description="Stateless logout acknowledgement. Client should delete the stored bearer token.",
)
def logout(http_request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> MessageResponse:
    lang_code = get_language_code(http_request, db, current_user)
    
    # Log logout action
    create_audit_log(
        db=db,
        action="auth_logout",
        target_entity="auth",
        actor_user_id=current_user.id,
        ip_address=http_request.client.host if http_request.client else None,
        user_agent=http_request.headers.get("user-agent"),
        changes_summary=f"User {current_user.email} logged out"
    )
    
    return MessageResponse(message=translate("logged_out", lang_code))


@router.post(
    "/mfa/setup",
    response_model=MfaSetupDetailsResponse,
    summary="Start MFA Setup",
    description="Requires bearer auth. Generates a new TOTP shared secret and otpauth URI to enroll an authenticator app.",
)
def setup_mfa(http_request: Request, current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> MfaSetupDetailsResponse:
    lang_code = get_language_code(http_request, db, current_user)
    return start_mfa_enrollment(db, user=current_user, lang_code=lang_code)


@router.post(
    "/mfa/verify",
    response_model=AuthResponse,
    summary="Verify MFA Enrollment",
    description="Requires bearer auth. Confirms a TOTP code to activate MFA on the authenticated account.",
)
def verify_mfa(request: MfaVerifyRequest, http_request: Request, current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> AuthResponse:
    lang_code = get_language_code(http_request, db, current_user)
    return confirm_mfa_enrollment(db, user=current_user, code=request.code, lang_code=lang_code)


@router.patch(
    "/admin/users/{user_id}/role",
    response_model=AuthResponse,
    summary="Assign User Role",
    description="Admin-only endpoint to change a target user's role using numeric codes: 0 admin, 1 auditor, 2 customer.",
)
def assign_role(
    user_id: UUID,
    request: RoleAssignment,
    http_request: Request,
    current_user=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AuthResponse:
    lang_code = get_language_code(http_request, db, current_user)
    return update_user_role(db, actor_user=current_user, user_id=user_id, role_code=request.role, lang_code=lang_code)