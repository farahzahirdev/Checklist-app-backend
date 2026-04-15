from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import UserRole
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    MfaChallengeVerifyRequest,
    MfaSetupDetailsResponse,
    MfaVerifyRequest,
    RegistrationRequest,
    RoleAssignment,
)
from app.schemas.common import MessageResponse
from app.services.auth import (
    authenticate_user,
    confirm_mfa_enrollment,
    register_user,
    serialize_user,
    start_mfa_enrollment,
    update_user_role,
    verify_mfa_challenge,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=AuthResponse,
    summary="Register User",
    description="Creates a new customer account, hashes the password, and returns a signed bearer token.",
)
def register(request: RegistrationRequest, db: Session = Depends(get_db)) -> AuthResponse:
    return register_user(db, email=request.email, password=request.password)


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
def login(request: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    return authenticate_user(db, email=request.email, password=request.password)


@router.post(
    "/mfa/challenge/verify",
    response_model=AuthResponse,
    summary="Verify MFA Login Challenge",
    description="Verifies login-time challenge_token plus TOTP code and returns the final bearer access token.",
)
def verify_login_mfa_challenge(request: MfaChallengeVerifyRequest, db: Session = Depends(get_db)) -> AuthResponse:
    return verify_mfa_challenge(db, challenge_token=request.challenge_token, code=request.code)


@router.get(
    "/me",
    response_model=AuthResponse,
    summary="Get Current User",
    description="Validates bearer token and returns authenticated user profile and MFA status.",
)
def me(current_user=Depends(get_current_user)) -> AuthResponse:
    return AuthResponse(user=serialize_user(current_user), mfa_enabled=bool(current_user.mfa_totp and current_user.mfa_totp.is_verified))


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout",
    description="Stateless logout acknowledgement. Client should delete the stored bearer token.",
)
def logout() -> MessageResponse:
    return MessageResponse(message="logged_out")


@router.post(
    "/mfa/setup",
    response_model=MfaSetupDetailsResponse,
    summary="Start MFA Setup",
    description="Requires bearer auth. Generates a new TOTP shared secret and otpauth URI to enroll an authenticator app.",
)
def setup_mfa(current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> MfaSetupDetailsResponse:
    return start_mfa_enrollment(db, user=current_user)


@router.post(
    "/mfa/verify",
    response_model=AuthResponse,
    summary="Verify MFA Enrollment",
    description="Requires bearer auth. Confirms a TOTP code to activate MFA on the authenticated account.",
)
def verify_mfa(request: MfaVerifyRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> AuthResponse:
    return confirm_mfa_enrollment(db, user=current_user, code=request.code)


@router.patch(
    "/admin/users/{user_id}/role",
    response_model=AuthResponse,
    summary="Assign User Role",
    description="Admin-only endpoint to change a target user's role using numeric codes: 0 admin, 1 auditor, 2 customer.",
)
def assign_role(
    user_id: UUID,
    request: RoleAssignment,
    current_user=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AuthResponse:
    return update_user_role(db, actor_user=current_user, user_id=user_id, role_code=request.role)