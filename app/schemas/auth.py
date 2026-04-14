from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRole(StrEnum):
    admin = "admin"
    auditor = "auditor"
    customer = "customer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    mfa_code: str | None = Field(default=None, min_length=6, max_length=6)


class RegistrationRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12)


class RoleAssignment(BaseModel):
    role: UserRole


class MfaSetupRequest(BaseModel):
    pass


class MfaSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class MfaVerifyRequest(BaseModel):
    code: str


class MfaVerifyResponse(BaseModel):
    verified: bool


class AuthUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    role: UserRole
    is_active: bool


class AuthResponse(BaseModel):
    user: AuthUserResponse
    access_token: str | None = None
    token_type: str = "bearer"
    mfa_required: bool = False
    mfa_enabled: bool = False


class MfaSetupDetailsResponse(BaseModel):
    secret: str
    provisioning_uri: str
    verified: bool = False


class RoleUpdateResponse(BaseModel):
    user: AuthUserResponse