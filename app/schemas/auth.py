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
    email: EmailStr
    password: str = Field(min_length=12)


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
    role: UserRoleCode
    is_active: bool


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