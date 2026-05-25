from enum import IntEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserRoleCode(IntEnum):
    admin = 0
    auditor = 1
    customer = 2


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordWithTokenRequest(BaseModel):
    token: str = Field(min_length=12)
    new_password: str = Field(min_length=8)
    confirm_password: str = Field(min_length=8)


class RegistrationRequest(BaseModel):
    """Customer sign-up request with required organization name."""

    # Required
    email: EmailStr
    password: str = Field(min_length=8)
    company_name: str = Field(..., max_length=255, description="User's company or organization name")

    # Optional: User profile
    full_name: str | None = Field(None, max_length=255, description="User's full name")
    username: str | None = Field(None, max_length=100, description="Unique username")
    job_title: str | None = Field(None, max_length=255, description="Job title")
    department: str | None = Field(None, max_length=255, description="Department")

    # Optional: Company context for audit
    company_industry: str | None = Field(None, max_length=50, description="Industry (finance, healthcare, tech, etc.)")
    company_size: str | None = Field(None, max_length=50, description="Company size (startup, small, medium, large, enterprise)")
    company_region: str | None = Field(None, max_length=100, description="Geographic region (EU, US, APAC, etc.)")

    @field_validator("company_name", mode="before")
    @classmethod
    def validate_company_name(cls, value: object) -> str:
        if value is None:
            raise ValueError("company_name_required")
        stripped = str(value).strip()
        if not stripped:
            raise ValueError("company_name_required")
        return stripped


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
    mfa_required: bool = True
    preferred_language: str = "en"
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
    preferred_language: str = "en"
    notifications_enabled: bool = True
    reports_alert: bool = True
    payment_success_alert: bool = True
    assessment_submitted_alert: bool = True
    assessment_started_alert: bool = True
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
    billing_contact_name: str | None = None
    billing_email: str | None = None
    billing_phone: str | None = None
    billing_address_line1: str | None = None
    billing_address_line2: str | None = None
    billing_city: str | None = None
    billing_state: str | None = None
    billing_postal_code: str | None = None
    billing_country: str | None = None
    billing_tax_id: str | None = None


class UpdateProfileRequest(BaseModel):
    """Update customer profile data."""
    
    full_name: str | None = Field(None, max_length=255, description="Full name")
    username: str | None = Field(None, max_length=100, description="Unique username")
    job_title: str | None = Field(None, max_length=255, description="Job title")
    department: str | None = Field(None, max_length=255, description="Department")
    preferred_language: str | None = Field(None, pattern="^(en|cs)$", description="Preferred language")
    notifications_enabled: bool | None = Field(None, description="Master email notifications toggle")
    reports_alert: bool | None = Field(None, description="Report-related email alerts")
    payment_success_alert: bool | None = Field(None, description="Payment success email alerts")
    assessment_submitted_alert: bool | None = Field(None, description="Assessment submitted email alerts")
    assessment_started_alert: bool | None = Field(None, description="Assessment started/expired email alerts")
    
    # Company fields (auto-create/update if provided)
    company_name: str | None = Field(None, max_length=255, description="Company name")
    company_slug: str | None = Field(None, max_length=100, description="Company slug")
    company_email: str | None = Field(None, description="Company email")
    company_website: str | None = Field(None, description="Company website")
    company_industry: str | None = Field(None, max_length=255, description="Industry")
    company_country: str | None = Field(None, max_length=255, description="Country")
    company_size: str | None = Field(None, max_length=100, description="Company size")
    company_description: str | None = Field(None, description="Company description")
    billing_contact_name: str | None = Field(None, max_length=255, description="Billing contact name")
    billing_email: str | None = Field(None, max_length=320, description="Billing contact email")
    billing_phone: str | None = Field(None, max_length=50, description="Billing contact phone")
    billing_address_line1: str | None = Field(None, max_length=255, description="Billing address line 1")
    billing_address_line2: str | None = Field(None, max_length=255, description="Billing address line 2")
    billing_city: str | None = Field(None, max_length=100, description="Billing city")
    billing_state: str | None = Field(None, max_length=100, description="Billing state/region")
    billing_postal_code: str | None = Field(None, max_length=50, description="Billing postal code")
    billing_country: str | None = Field(None, max_length=100, description="Billing country")
    billing_tax_id: str | None = Field(None, max_length=100, description="Billing tax/VAT ID")


class ChangePasswordRequest(BaseModel):
    """Change user password."""
    
    current_password: str = Field(min_length=1, description="Current password for verification")
    new_password: str = Field(min_length=8, description="New password (must be strong)")
    confirm_password: str = Field(min_length=8, description="Confirm new password")


class ProfileCompletionItem(BaseModel):
    section: str
    field: str
    label: str
    completed: bool


class ProfileCompletionResponse(BaseModel):
    completion_percent: float
    is_complete: bool
    missing_fields: list[ProfileCompletionItem]
    completed_fields: list[ProfileCompletionItem]


class EmailPreferencesResponse(BaseModel):
    notifications_enabled: bool
    reports_alert: bool
    payment_success_alert: bool
    assessment_submitted_alert: bool
    assessment_started_alert: bool


class EmailPreferencesUpdateRequest(BaseModel):
    notifications_enabled: bool | None = None
    reports_alert: bool | None = None
    payment_success_alert: bool | None = None
    assessment_submitted_alert: bool | None = None
    assessment_started_alert: bool | None = None