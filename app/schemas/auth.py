from enum import IntEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRoleCode(IntEnum):
    admin = 0
    auditor = 1
    customer = 2


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegistrationRequest(BaseModel):
    """Customer sign-up request with optional profile and company info."""
    
    # Required
    email: EmailStr
    password: str = Field(min_length=8)
    
    # Optional: User profile
    full_name: str | None = Field(None, max_length=255, description="User's full name")
    username: str | None = Field(None, max_length=100, description="Unique username")
    
    # Optional: Company/Organization context
    company_name: str | None = Field(None, max_length=255, description="User's company name")
    job_title: str | None = Field(None, max_length=255, description="Job title")
    department: str | None = Field(None, max_length=255, description="Department")
    
    # Optional: Company context for audit
    company_industry: str | None = Field(None, max_length=50, description="Industry (finance, healthcare, tech, etc.)")
    company_size: str | None = Field(None, max_length=50, description="Company size (startup, small, medium, large, enterprise)")
    company_region: str | None = Field(None, max_length=100, description="Geographic region (EU, US, APAC, etc.)")


class RoleAssignment(BaseModel):
    role: UserRoleCode


class MfaSetupRequest(BaseModel):
    pass


class MfaSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class MfaVerifyRequest(BaseModel):
    code: str = Field(min_length=1)


class MfaChallengeVerifyRequest(BaseModel):
    challenge_token: str
    code: str = Field(min_length=1)


class MfaVerifyResponse(BaseModel):
    verified: bool


class AuthUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str | None = None
    username: str | None = None
    role: UserRoleCode
    is_active: bool
    primary_company_id: UUID | None = None
    job_title: str | None = None
    department: str | None = None
    company_name: str | None = None
    company_slug: str | None = None
    company_industry: str | None = None
    company_size: str | None = None
    company_region: str | None = None
    company_email: str | None = None
    company_website: str | None = None
    company_country: str | None = None
    company_description: str | None = None


class AuthResponse(BaseModel):
    user: AuthUserResponse
    access_token: str | None = None
    challenge_token: str | None = None
    token_type: str = "bearer"
    mfa_required: bool = True
    mfa_enabled: bool = False


class MfaSetupDetailsResponse(BaseModel):
    secret: str
    provisioning_uri: str
    svg_qr: str
    verified: bool = False


class RoleUpdateResponse(BaseModel):
    user: AuthUserResponse


class CustomerProfileResponse(BaseModel):
    """Customer profile view with company context."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str | None = None
    username: str | None = None
    job_title: str | None = None
    department: str | None = None
    primary_company_id: UUID | None = None
    is_active: bool
    created_at: str | None = None
    updated_at: str | None = None
    
    # Company context
    company_name: str | None = None
    company_industry: str | None = None
    company_size: str | None = None
    company_region: str | None = None
    company_email: str | None = None
    company_website: str | None = None
    company_slug: str | None = None
    company_country: str | None = None
    company_description: str | None = None


class UpdateProfileRequest(BaseModel):
    """Update customer profile data."""
    
    full_name: str | None = Field(None, max_length=255, description="Full name")
    username: str | None = Field(None, max_length=100, description="Unique username")
    job_title: str | None = Field(None, max_length=255, description="Job title")
    department: str | None = Field(None, max_length=255, description="Department")
    
    # Company fields (auto-create/update if provided)
    company_name: str | None = Field(None, max_length=255, description="Company name")
    company_slug: str | None = Field(None, max_length=100, description="Company slug")
    company_email: str | None = Field(None, description="Company email")
    company_website: str | None = Field(None, description="Company website")
    company_industry: str | None = Field(None, max_length=255, description="Industry")
    company_country: str | None = Field(None, max_length=255, description="Country")
    company_size: str | None = Field(None, max_length=100, description="Company size")
    company_description: str | None = Field(None, description="Company description")


class ChangePasswordRequest(BaseModel):
    """Change user password."""
    
    current_password: str = Field(min_length=1, description="Current password for verification")
    new_password: str = Field(min_length=8, description="New password (must be strong)")
    confirm_password: str = Field(min_length=8, description="Confirm new password")